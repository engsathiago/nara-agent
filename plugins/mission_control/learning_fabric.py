"""Provenance-first multimodal ingestion; extraction is explicit and never invented."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import sqlite3
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import utc_now
from plugins.plugin_storage import plugin_data_dir


MODALITIES = frozenset({"document", "site", "audio", "video", "image"})


def default_fabric_root() -> Path:
    return plugin_data_dir("mission-control") / "learning-fabric"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS learning_sources (
            source_id TEXT PRIMARY KEY, modality TEXT NOT NULL, source_uri TEXT NOT NULL,
            source_hash TEXT NOT NULL, media_type TEXT NOT NULL, stored_path TEXT NOT NULL,
            version TEXT, license TEXT, extraction_status TEXT NOT NULL,
            extracted_text TEXT, transcript_hash TEXT, transcript_path TEXT,
            metadata_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS learning_claims (
            claim_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, claim TEXT NOT NULL,
            quote TEXT NOT NULL, start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
            confidence REAL NOT NULL, status TEXT NOT NULL, verifier_id TEXT,
            evidence_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES learning_sources(source_id)
        );
        CREATE INDEX IF NOT EXISTS learning_claim_source ON learning_claims (source_id, status);
    """)
    conn.execute("PRAGMA user_version=1")
    conn.commit()


class LearningFabric:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.db_path = self.root / "learning-fabric.db"

    @classmethod
    def open_default(cls) -> LearningFabric:
        return cls(default_fabric_root())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.db_path, db_label="plugin-data/mission-control/learning-fabric.db",
            foreign_keys=True, synchronous_full=True, initialize=_initialize)

    def _store(self, content: bytes) -> tuple[str, Path]:
        digest = hashlib.sha256(content).hexdigest()
        destination = self.root / "sources" / digest[:2] / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            with destination.open("rb") as handle:
                archived_digest = hashlib.file_digest(handle, "sha256").hexdigest()
            if archived_digest != digest:
                raise ValueError(f"archived learning evidence {digest} has changed")
        else:
            with NamedTemporaryFile("wb", dir=destination.parent, delete=False) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            temporary.replace(destination)
        return digest, destination

    def ingest_file(
        self,
        path: Path | str,
        *,
        modality: str,
        source_uri: str | None = None,
        version: str | None = None,
        license_name: str | None = None,
        transcript_path: Path | str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if modality not in MODALITIES:
            raise ValueError(f"unsupported modality: {modality}")
        source_path = Path(path).resolve()
        if modality in {"audio", "video"} and source_path.stat().st_size > 500_000_000:
            raise ValueError("media source exceeds 500 MB local ingestion limit")
        content = source_path.read_bytes()
        digest, stored = self._store(content)
        media_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        extracted_text: str | None = None
        transcript_hash: str | None = None
        stored_transcript: str | None = None
        status = "needs_extraction"
        if modality in {"document", "site"} and media_type.startswith("text/"):
            extracted_text = content.decode("utf-8", errors="replace")
            status = "extracted"
        if transcript_path is not None:
            transcript = Path(transcript_path).read_bytes()
            transcript_hash, transcript_store = self._store(transcript)
            extracted_text = transcript.decode("utf-8", errors="replace")
            stored_transcript = str(transcript_store)
            status = "transcript_supplied"
        identity = f"source:{digest}"
        try:
            existing = self.source(identity)
        except KeyError:
            existing = None
        if existing is not None:
            if existing["modality"] != modality:
                raise ValueError("source bytes are already registered with a different modality")
            if transcript_path is not None and existing["transcript_hash"] != transcript_hash:
                if existing["extraction_status"] not in {"needs_extraction", "screen_text_local"}:
                    raise ValueError("source already has different extraction evidence")
                preserved_text = "\n".join(
                    part for part in (existing["extracted_text"], extracted_text) if part
                )
                existing_metadata = dict(existing["metadata"])
                frame_ocr = existing_metadata.get("frame_ocr", {})
                if frame_ocr.get("status") == "complete":
                    frame_ocr["fused_text_hash"] = hashlib.sha256(preserved_text.encode()).hexdigest()
                with transaction(self._connect(), immediate=True) as conn:
                    conn.execute(
                        """UPDATE learning_sources SET extraction_status = ?, extracted_text = ?,
                           transcript_hash = ?, transcript_path = ?, metadata_json = ?
                           WHERE source_id = ?""",
                        (status, preserved_text, transcript_hash, stored_transcript,
                         json.dumps(existing_metadata, sort_keys=True, ensure_ascii=False), identity),
                    )
                return self.source(identity)
            return existing
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO learning_sources VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""",
                (identity, modality, source_uri or source_path.as_uri(), digest, media_type,
                 str(stored), version, license_name, status, extracted_text, transcript_hash,
                 stored_transcript, json.dumps(metadata or {}, sort_keys=True), utc_now()))
        return self.source(identity)

    def source(self, source_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM learning_sources WHERE source_id = ?", (source_id,)).fetchone()
        if row is None:
            raise KeyError(source_id)
        return {**dict(row), "metadata": json.loads(row["metadata_json"])}

    def propose_claim(
        self, source_id: str, claim: str, quote: str, *, confidence: float = 0.7,
    ) -> dict[str, Any]:
        source = self.source(source_id)
        text = source["extracted_text"] or ""
        start = text.find(quote)
        if not quote or start < 0:
            raise ValueError("claim quote is not present in the extracted source")
        identity = hashlib.sha256(
            f"{source_id}\0{claim}\0{quote}\0{start}".encode()).hexdigest()[:24]
        now = utc_now()
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO learning_claims VALUES (?, ?, ?, ?, ?, ?, ?, 'candidate', NULL, '[]', ?, ?)",
                (identity, source_id, claim.strip(), quote, start, start + len(quote),
                 max(0.0, min(1.0, float(confidence))), now, now))
        return self.claim(identity)

    def verify_claim(
        self, claim_id: str, *, verifier_id: str, evidence_artifact_ids: list[str], accepted: bool,
    ) -> dict[str, Any]:
        if not evidence_artifact_ids:
            raise ValueError("claim verification requires evidence")
        if verifier_id == "github-public-rest-v1":
            self._check_archived_evidence(evidence_artifact_ids)
        with transaction(self._connect(), immediate=True) as conn:
            result = conn.execute(
                """UPDATE learning_claims SET status = ?, verifier_id = ?, evidence_json = ?,
                   updated_at = ? WHERE claim_id = ?""",
                ("verified" if accepted else "rejected", verifier_id,
                 json.dumps(sorted(set(evidence_artifact_ids))), utc_now(), claim_id))
            if result.rowcount != 1:
                raise KeyError(claim_id)
        return self.claim(claim_id)

    def claim(self, claim_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM learning_claims WHERE claim_id = ?", (claim_id,)).fetchone()
        if row is None:
            raise KeyError(claim_id)
        evidence = json.loads(row["evidence_json"])
        if row["verifier_id"] == "github-public-rest-v1":
            self._check_archived_evidence(evidence)
        return {**dict(row), "evidence_artifact_ids": evidence}

    def _check_archived_evidence(self, evidence_ids: list[str]) -> None:
        for artifact_id in evidence_ids:
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", artifact_id):
                raise ValueError("GitHub verification requires a full archived evidence hash")
            digest = artifact_id[7:]
            stored = self.root / "sources" / digest[:2] / digest
            if not stored.is_file() or hashlib.sha256(stored.read_bytes()).hexdigest() != digest:
                raise ValueError("archived claim evidence has changed")

    def search(self, query: str, *, verified_only: bool = True) -> list[dict[str, Any]]:
        tokens = {token.casefold() for token in query.split() if len(token) > 1}
        clause = "WHERE status = 'verified'" if verified_only else ""
        with transaction(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT claim_id FROM learning_claims {clause} ORDER BY updated_at DESC").fetchall()
        claims = [self.claim(row["claim_id"]) for row in rows]
        return [item for item in claims if tokens & set(item["claim"].casefold().split())]

    def status(self) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            sources = [dict(row) for row in conn.execute(
                "SELECT modality, extraction_status, COUNT(*) AS count FROM learning_sources GROUP BY modality, extraction_status").fetchall()]
            claims = [dict(row) for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM learning_claims GROUP BY status").fetchall()]
        return {"sources": sources, "claims": claims}
