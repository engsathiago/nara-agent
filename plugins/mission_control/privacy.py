"""Local-first privacy controls and secret-safe audit projections."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import utc_now
from plugins.plugin_storage import plugin_data_dir


SENSITIVE_KEYS = (
    "api_key", "apikey", "authorization", "cookie", "credential", "password",
    "private_key", "secret", "session_token", "token",
)
DEFAULTS = {
    "telemetry_enabled": False,
    "store_sensitive_trace_content": False,
    "voice_transcript_storage": False,
    "camera_enabled": False,
    "biometric_processing": False,
    "media_retention_days": 0,
}
_INLINE_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*([^\s,;]+)")


def default_privacy_path() -> Path:
    return plugin_data_dir("mission-control") / "privacy.db"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS privacy_settings (
            profile_id TEXT PRIMARY KEY, settings_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS privacy_exports (
            export_id TEXT PRIMARY KEY, destination TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL, created_at TEXT NOT NULL
        );
    """)
    conn.execute(
        "INSERT OR IGNORE INTO privacy_settings VALUES ('local', ?, ?)",
        (json.dumps(DEFAULTS, sort_keys=True), utc_now()))
    conn.execute("PRAGMA user_version=1")
    conn.commit()


def _secret_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]


def redact_sensitive(value: Any, *, key: str = "") -> Any:
    """Remove secret values while retaining a stable correlation digest."""
    lowered = key.casefold()
    if any(marker in lowered for marker in SENSITIVE_KEYS):
        return f"[REDACTED sha256:{_secret_digest(value)}]"
    if isinstance(value, dict):
        return {str(item_key): redact_sensitive(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(item, key=key) for item in value]
    if isinstance(value, str):
        return _INLINE_SECRET.sub(
            lambda match: f"{match.group(1)}=[REDACTED sha256:{_secret_digest(match.group(2))}]",
            value,
        )
    return value


class PrivacyControl:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    @classmethod
    def open_default(cls) -> PrivacyControl:
        return cls(default_privacy_path())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.path, db_label="plugin-data/mission-control/privacy.db",
            synchronous_full=True, initialize=_initialize)

    def settings(self, profile_id: str = "local") -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM privacy_settings WHERE profile_id = ?", (profile_id,)).fetchone()
        if row is None:
            raise KeyError(profile_id)
        return {"profile_id": profile_id, **json.loads(row["settings_json"]),
                "updated_at": row["updated_at"]}

    def configure(self, updates: dict[str, Any], *, profile_id: str = "local") -> dict[str, Any]:
        unknown = set(updates) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"unknown privacy settings: {sorted(unknown)}")
        current = self.settings(profile_id)
        merged = {key: current[key] for key in DEFAULTS}
        merged.update(updates)
        for key in DEFAULTS:
            if key == "media_retention_days":
                if not isinstance(merged[key], int) or merged[key] < 0:
                    raise ValueError("media_retention_days must be a non-negative integer")
            elif not isinstance(merged[key], bool):
                raise ValueError(f"{key} must be boolean")
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                """INSERT INTO privacy_settings VALUES (?, ?, ?)
                   ON CONFLICT(profile_id) DO UPDATE SET settings_json=excluded.settings_json,
                   updated_at=excluded.updated_at""",
                (profile_id, json.dumps(merged, sort_keys=True), utc_now()))
        return self.settings(profile_id)

    def export(self, destination: Path | str, *, profile_id: str = "local") -> dict[str, Any]:
        path = Path(destination).expanduser().resolve()
        if path.exists():
            raise FileExistsError(path)
        payload = {
            "schema_version": 1, "kind": "nara_privacy_export",
            "profile": self.settings(profile_id), "exported_at": utc_now(),
        }
        encoded = json.dumps(payload, sort_keys=True, indent=2).encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded)
        digest = hashlib.sha256(encoded).hexdigest()
        export_id = digest[:32]
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO privacy_exports VALUES (?, ?, ?, ?)",
                (export_id, str(path), digest, utc_now()))
        return {"export_id": export_id, "path": str(path), "sha256": digest,
                "size_bytes": len(encoded)}

    def status(self) -> dict[str, Any]:
        settings = self.settings()
        return {
            "settings": settings,
            "telemetry": "opted_in" if settings["telemetry_enabled"] else "disabled",
            "sensitive_trace_content": (
                "enabled" if settings["store_sensitive_trace_content"] else "redacted"),
            "profile_isolation": "NARA_HOME/plugin-data",
        }


PRIVACY_STATUS_SCHEMA = {
    "name": "nara_privacy_status", "description": "Inspect local-first Nara privacy controls.",
    "parameters": {"type": "object", "properties": {}},
}
PRIVACY_CONFIGURE_SCHEMA = {
    "name": "nara_privacy_configure", "description": "Update explicit privacy settings.",
    "parameters": {"type": "object", "properties": {
        "updates": {"type": "object"},
    }, "required": ["updates"]},
}
PRIVACY_EXPORT_SCHEMA = {
    "name": "nara_privacy_export", "description": "Export privacy settings with an integrity hash.",
    "parameters": {"type": "object", "properties": {
        "destination": {"type": "string"},
    }, "required": ["destination"]},
}


def privacy_status_tool(**_: Any) -> dict[str, Any]:
    return PrivacyControl.open_default().status()


def privacy_configure_tool(updates: dict[str, Any], **_: Any) -> dict[str, Any]:
    return PrivacyControl.open_default().configure(updates)


def privacy_export_tool(destination: str, **_: Any) -> dict[str, Any]:
    return PrivacyControl.open_default().export(destination)
