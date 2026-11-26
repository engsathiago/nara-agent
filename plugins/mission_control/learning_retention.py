"""Expire original media while retaining a verifiable extraction receipt."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from nara_cli.sqlite_util import transaction

DEFAULT_RETENTION_SECONDS = 86400
MEDIA_MODALITIES = {"audio", "video", "image"}


def original_policy(*, keep: bool = False) -> dict[str, Any]:
    return {"status": "retained" if keep else "active",
            "expires_at": None if keep else time.time() + DEFAULT_RETENTION_SECONDS}


def _extraction_snapshot(source: dict[str, Any]) -> dict[str, Any]:
    return {"source_hash": source["source_hash"],
            "text_hash": hashlib.sha256((source["extracted_text"] or "").encode()).hexdigest(),
            "transcript_hash": source["transcript_hash"],
            "frame_ocr": source["metadata"].get("frame_ocr"),
            "local_extraction": source["metadata"].get("local_extraction")}


def check_expiry_receipt(source: dict[str, Any]) -> bool:
    policy = source["metadata"].get("original_retention", {})
    if policy.get("status") not in {"expiring", "expired"}:
        return False
    path = Path(policy["receipt_path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != policy["receipt_hash"]:
        raise ValueError("original expiry receipt is missing or changed")
    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    if receipt.get("evidence") != _extraction_snapshot(source):
        raise ValueError("extraction evidence differs from original expiry receipt")
    return True


def _decode(row):
    return {**dict(row), "metadata": json.loads(row["metadata_json"])}


def _sources(fabric):
    if not fabric.db_path.exists():
        return []
    with transaction(fabric._connect()) as conn:
        rows = conn.execute("SELECT * FROM learning_sources").fetchall()
    return [_decode(row) for row in rows]


def retention_status(fabric) -> dict[str, Any]:
    rows = _sources(fabric)
    counts: dict[str, int] = {}
    errors = []
    due = 0
    for source in rows:
        if source["modality"] not in MEDIA_MODALITIES:
            continue
        policy = source["metadata"].get("original_retention", {"status": "legacy_retained"})
        status = policy["status"]
        if policy.get("last_error"):
            errors.append({"source_id": source["source_id"], "error": policy["last_error"]})
        counts[status] = counts.get(status, 0) + 1
        due += status == "expiring" or (status == "active" and policy["expires_at"] <= time.time())
    return {"state": "degraded" if errors else "available", "default_seconds": DEFAULT_RETENTION_SECONDS,
            "counts": counts, "due": due, "errors": errors}


def _shared_evidence(conn, source) -> bool:
    digest = source["source_hash"]
    for row in conn.execute("SELECT * FROM learning_sources"):
        other = _decode(row)
        metadata = other["metadata"]
        # A source byte stream may also be a transcript or a retained OCR frame.
        hashes = {other["transcript_hash"],
                  metadata.get("local_extraction", {}).get("timing", {}).get("sha256")}
        hashes.update(item.get("frame_hash") for item in metadata.get("frame_ocr", {}).get("evidence", []))
        hashes.update(item.get("snapshot_hash") for item in metadata.get("primary_sources", []))
        if digest in hashes:
            return True
    return False


def _expire_one(fabric, source_id: str, now: float) -> str:
    from plugins.mission_control.learning_github_source import _check_cited_source

    # Serialize the decision with extraction metadata writes. An interrupted
    # unlink resumes from the durable expiring receipt on the next pass.
    with transaction(fabric._connect(), immediate=True) as conn:
        source = _decode(conn.execute("SELECT * FROM learning_sources WHERE source_id=?", (source_id,)).fetchone())
        policy = source["metadata"].get("original_retention", {})
        if policy.get("status") == "active" and policy["expires_at"] > now:
            return "not_due"
        if policy.get("status") not in {"active", "expiring"}:
            return "not_due"
        if _shared_evidence(conn, source):
            return "shared_evidence"
        archive = fabric.root / "sources" / source["source_hash"][:2] / source["source_hash"]
        if archive.resolve() != Path(source["stored_path"]).resolve():
            raise ValueError("original archive path differs from content address")
        if policy["status"] == "active":
            _check_cited_source(source)
            receipt = {"kind": "original_media_expiry", "schema_version": 1,
                       "expired_at": now, "evidence": _extraction_snapshot(source)}
            digest, path = fabric._store(json.dumps(receipt, sort_keys=True, ensure_ascii=False).encode())
            policy.update(status="expiring", receipt_hash=digest, receipt_path=str(path))
            conn.execute("UPDATE learning_sources SET metadata_json=? WHERE source_id=?",
                         (json.dumps(source["metadata"], sort_keys=True), source_id))
        else:
            check_expiry_receipt(source)
    with transaction(fabric._connect(), immediate=True) as conn:
        fresh = _decode(conn.execute("SELECT * FROM learning_sources WHERE source_id=?", (source_id,)).fetchone())
        current = fresh["metadata"].get("original_retention", {})
        if current.get("receipt_hash") != policy["receipt_hash"]:
            raise ValueError("original retention changed during expiry; reingest required")
        _check_cited_source(fresh)
        if _shared_evidence(conn, fresh):
            return "shared_evidence"
        archive.unlink(missing_ok=True)
        current["status"] = "expired"
        current.pop("last_error", None)
        conn.execute("UPDATE learning_sources SET metadata_json=? WHERE source_id=?",
                     (json.dumps(fresh["metadata"], sort_keys=True), source_id))
    return "expired"


def expire_originals(fabric, *, now: float | None = None, limit: int = 100) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("expiry limit must be positive")
    stamp = time.time() if now is None else now
    report: dict[str, Any] = {"expired": [], "shared_evidence": [], "errors": []}
    due = [source for source in _sources(fabric)
           if (policy := source["metadata"].get("original_retention", {})).get("status") == "expiring"
           or (policy.get("status") == "active" and policy["expires_at"] <= stamp)]
    for source in due[:limit]:
        try:
            outcome = _expire_one(fabric, source["source_id"], stamp)
            if outcome in report:
                report[outcome].append(source["source_id"])
        except (OSError, ValueError) as exc:
            report["errors"].append({"source_id": source["source_id"], "error": str(exc)})
            with transaction(fabric._connect(), immediate=True) as conn:
                fresh = _decode(conn.execute("SELECT * FROM learning_sources WHERE source_id=?",
                                             (source["source_id"],)).fetchone())
                fresh["metadata"]["original_retention"]["last_error"] = str(exc)
                conn.execute("UPDATE learning_sources SET metadata_json=? WHERE source_id=?",
                             (json.dumps(fresh["metadata"], sort_keys=True), source["source_id"]))
    report["remaining"] = max(0, len(due) - limit)
    return report


def expire_gateway_media(**_: Any) -> dict[str, Any] | None:
    from plugins.mission_control.learning_fabric import LearningFabric

    fabric = LearningFabric.open_default()
    if not fabric.db_path.exists():
        return None
    report = expire_originals(fabric)
    if report["errors"]:
        logging.getLogger(__name__).error("Media expiry failed: %s", report["errors"])
    return report
