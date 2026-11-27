"""Immutable, profile-local preparation of native delegation calls.

A binding proves which instructions were prepared, not that a child executed them.
"""

from __future__ import annotations

from contextlib import closing
import hashlib
import json
from typing import Callable
import uuid

from plugins.plugin_storage import plugin_data_dir, plugin_db


MAX_BINDING_BYTES = 1024 * 1024


def canonical(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > MAX_BINDING_BYTES:
        raise ValueError("specialist binding exceeds 1 MiB")
    return encoded


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def freeze_call(args: dict, session_id: str, tool_call_id: str, build: Callable[[], dict]) -> dict:
    """Serialize first preparation; replays never re-resolve a changed catalog."""
    request_hash = digest(canonical(args))
    identity = [session_id, tool_call_id] if session_id and tool_call_id else [uuid.uuid4().hex]
    binding_id = digest(canonical(identity))
    root = plugin_data_dir("mission-control")
    root.chmod(0o700)
    with closing(plugin_db("mission-control", "specialist-bindings.db")) as db:
        (root / "specialist-bindings.db").chmod(0o600)
        db.execute("PRAGMA busy_timeout=1000")
        db.execute("CREATE TABLE IF NOT EXISTS bindings (id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, "
                   "payload TEXT NOT NULL, payload_hash TEXT NOT NULL)")
        with db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT request_hash, payload, payload_hash FROM bindings WHERE id=?",
                             (binding_id,)).fetchone()
            if row is not None:
                if row[0] != request_hash:
                    raise ValueError("delegation arguments changed for an existing specialist binding")
                if digest(row[1]) != row[2]:
                    raise ValueError("specialist binding hash mismatch")
                payload = json.loads(row[1])
                if not isinstance(payload, dict) or not isinstance(payload.get("args"), dict):
                    raise ValueError("invalid specialist binding payload")
                return payload
            payload = build()
            encoded = canonical(payload)
            db.execute("INSERT INTO bindings VALUES (?, ?, ?, ?)",
                       (binding_id, request_hash, encoded, digest(encoded)))
            return payload
