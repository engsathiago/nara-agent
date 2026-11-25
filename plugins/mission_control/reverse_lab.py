"""Evidence-first routing for authorized reverse-engineering investigations."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import utc_now
from plugins.plugin_storage import plugin_data_dir


REA_PACKAGE = "rea-agents@6.7.0"
MUTABLE_STEPS = frozenset({
    "execute_target", "attach_debugger", "instrument", "install_apk",
    "modify_device", "capture_live_network", "overwrite_file",
})


def default_reverse_path() -> Path:
    return plugin_data_dir("mission-control") / "reverse-lab.db"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reverse_investigations (
            investigation_id TEXT PRIMARY KEY, target_path TEXT NOT NULL,
            target_hash TEXT NOT NULL, target_type TEXT NOT NULL, route TEXT NOT NULL,
            provider TEXT NOT NULL, scope_statement TEXT NOT NULL,
            authorized INTEGER NOT NULL, read_only INTEGER NOT NULL,
            plan_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE (target_hash, target_type, scope_statement, read_only)
        );
    """)
    conn.execute("PRAGMA user_version=1")
    conn.commit()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _target_hash(path: Path) -> str:
    if path.is_file():
        return _file_hash(path)
    digest = hashlib.sha256()
    for item in sorted(entry for entry in path.rglob("*") if entry.is_file()):
        relative = item.relative_to(path).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(_file_hash(item).encode())
        digest.update(b"\0")
    return digest.hexdigest()


def _magic(path: Path) -> bytes:
    if not path.is_file():
        return b""
    with path.open("rb") as handle:
        return handle.read(16)


def classify_target(path: Path) -> tuple[str, str, str, list[str]]:
    suffix = path.suffix.casefold()
    magic = _magic(path)
    if path.is_dir():
        files = {item.name.casefold() for item in path.iterdir()}
        if "package.json" in files or any(path.rglob("app.asar")):
            return "electron", "rea_static", "rea", ["inventory", "extract_javascript", "trace_modules"]
        return "source_repository", "source_tools", "nara", ["inventory", "search_source", "run_tests"]
    if suffix == ".asar":
        return "electron", "rea_static", "rea", ["inventory", "extract_javascript", "trace_modules"]
    if suffix in {".dll", ".exe"} and magic.startswith(b"MZ"):
        return "dotnet_or_pe", "rea_static", "rea", ["inventory", "inspect_pe", "decompile"]
    if suffix == ".apk" or magic.startswith(b"PK\x03\x04") and suffix == ".apk":
        return "android_apk", "rea_android_static", "rea", ["inventory", "unpack_apk", "inspect_manifest"]
    if suffix in {".bin", ".img", ".fw", ".rom"}:
        return "firmware", "rea_firmware_static", "rea", ["inventory", "entropy_map", "extract_filesystems"]
    if magic.startswith(b"\x7fELF") or magic[:4] in {
        b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe",
    }:
        return "native_binary", "ghidra_static", "rea+ghidra", ["inventory", "strings", "decompile"]
    return "opaque_file", "rea_static", "rea", ["inventory", "strings", "identify_format"]


class ReverseEngineeringLab:
    def __init__(self, path: Path | str, *, plugin_root: Path | str | None = None):
        self.path = Path(path)
        self.plugin_root = Path(plugin_root or Path.home() / ".nara" / "plugins" / "rea")

    @classmethod
    def open_default(cls) -> ReverseEngineeringLab:
        return cls(default_reverse_path())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.path, db_label="plugin-data/mission-control/reverse-lab.db",
            synchronous_full=True, initialize=_initialize)

    def provider_status(self) -> dict[str, Any]:
        mcp_path = self.plugin_root / "mcp.json"
        configured = False
        package = None
        if mcp_path.exists():
            payload = json.loads(mcp_path.read_text(encoding="utf-8-sig"))
            server = payload.get("mcpServers", {}).get("rea", {})
            args = server.get("args", [])
            configured = server.get("command") == "npx" and REA_PACKAGE in args
            package = next((item for item in args if item.startswith("rea-agents@")), None)
        ghidra_root = Path(os.environ.get("GHIDRA_INSTALL_DIR", ""))
        candidates = [ghidra_root / "support" / "analyzeHeadless"] if str(ghidra_root) else []
        candidates.extend(Path.home().glob("tools/ghidra*/support/analyzeHeadless"))
        ghidra = (
            shutil.which("ghidra") or shutil.which("analyzeHeadless")
            or next((str(item) for item in candidates if item.is_file()), None)
        )
        return {
            "rea_installed": self.plugin_root.is_dir(), "rea_configured": configured,
            "rea_package": package, "mcp_path": str(mcp_path),
            "ghidra_command": ghidra, "default_read_only": True,
        }

    def route(
        self, target_path: Path | str, *, scope_statement: str,
        user_attested_authorized: bool, read_only: bool = True,
    ) -> dict[str, Any]:
        target = Path(target_path).expanduser().resolve()
        if not target.exists():
            raise FileNotFoundError(target)
        if not scope_statement.strip() or not user_attested_authorized:
            raise ValueError("an explicit authorized scope statement is required")
        target_type, route, provider, capabilities = classify_target(target)
        if not read_only:
            raise ValueError(
                "mutable/runtime investigation requires a separately approved assisted mission")
        digest = _target_hash(target)
        plan = {
            "target_type": target_type, "route": route, "provider": provider,
            "capabilities": capabilities, "read_only": True,
            "excluded_mutable_steps": sorted(MUTABLE_STEPS),
            "sequence": [
                "preserve target hash", "inventory without modification",
                "collect addressable evidence", "separate observation from hypothesis",
                "repeat critical findings in a fresh session",
            ],
        }
        evidence = {
            "target_sha256": digest, "canonical_path": str(target),
            "size_bytes": target.stat().st_size if target.is_file() else None,
            "mode_before": oct(os.stat(target).st_mode & 0o777),
        }
        with transaction(self._connect()) as conn:
            existing = conn.execute(
                """SELECT investigation_id FROM reverse_investigations
                   WHERE target_hash = ? AND target_type = ? AND scope_statement = ? AND read_only = 1""",
                (digest, target_type, scope_statement.strip())).fetchone()
        if existing:
            return self.investigation(existing["investigation_id"])
        identity = uuid.uuid4().hex
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT INTO reverse_investigations VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, 'planned', ?)",
                (identity, str(target), digest, target_type, route, provider,
                 scope_statement.strip(), json.dumps(plan, sort_keys=True),
                 json.dumps(evidence, sort_keys=True), utc_now()))
        return self.investigation(identity)

    def investigation(self, investigation_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM reverse_investigations WHERE investigation_id = ?",
                (investigation_id,)).fetchone()
        if row is None:
            raise KeyError(investigation_id)
        return {
            **dict(row), "authorized": bool(row["authorized"]),
            "read_only": bool(row["read_only"]), "plan": json.loads(row["plan_json"]),
            "evidence": json.loads(row["evidence_json"]),
        }

    def status(self) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            rows = conn.execute(
                "SELECT investigation_id FROM reverse_investigations ORDER BY created_at").fetchall()
        return {
            "provider": self.provider_status(),
            "investigations": [self.investigation(row["investigation_id"]) for row in rows],
        }


REA_ROUTE_SCHEMA = {
    "name": "nara_rea_route",
    "description": "Route an authorized artifact to a read-only evidence-first REA investigation.",
    "parameters": {"type": "object", "properties": {
        "target_path": {"type": "string"}, "scope_statement": {"type": "string"},
        "user_attested_authorized": {"type": "boolean"}, "read_only": {"type": "boolean"},
    }, "required": ["target_path", "scope_statement", "user_attested_authorized"]},
}
REA_STATUS_SCHEMA = {
    "name": "nara_rea_status", "description": "Inspect REA provider and investigation state.",
    "parameters": {"type": "object", "properties": {}},
}


def rea_route_tool(**kwargs: Any) -> dict[str, Any]:
    return ReverseEngineeringLab.open_default().route(**kwargs)


def rea_status_tool(**_: Any) -> dict[str, Any]:
    return ReverseEngineeringLab.open_default().status()
