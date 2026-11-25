"""Versioned, explainable Policy Decision Point with an inert default profile."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import utc_now
from plugins.plugin_storage import plugin_data_dir


EFFECTS = frozenset({"allow", "require_confirmation", "deny"})
MODES = frozenset({"observe_only", "enforce"})
CONTROL_TOOLS = frozenset({
    "nara_policy_status", "nara_policy_explain", "nara_policy_confirm",
    "nara_policy_rollback",
})


def default_policy_path() -> Path:
    return plugin_data_dir("mission-control") / "policy.db"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS policy_versions (
            version_id TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL,
            rules_json TEXT NOT NULL, rules_hash TEXT NOT NULL, status TEXT NOT NULL,
            parent_version_id TEXT, created_at TEXT NOT NULL, promoted_at TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_policy
            ON policy_versions(status) WHERE status = 'active';
        CREATE TABLE IF NOT EXISTS policy_decisions (
            decision_id TEXT PRIMARY KEY, version_id TEXT NOT NULL,
            action TEXT NOT NULL, target_hash TEXT NOT NULL, target_kind TEXT NOT NULL,
            surface TEXT NOT NULL, actor_id TEXT NOT NULL, effect TEXT NOT NULL,
            would_effect TEXT NOT NULL, rule_id TEXT, reason TEXT NOT NULL,
            fingerprint TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE (version_id, fingerprint)
        );
        CREATE TABLE IF NOT EXISTS policy_approvals (
            approval_id TEXT PRIMARY KEY, decision_id TEXT NOT NULL UNIQUE,
            approved_by TEXT NOT NULL, approved_at TEXT NOT NULL, consumed_at TEXT
        );
    """)
    active = conn.execute(
        "SELECT version_id FROM policy_versions WHERE status = 'active'").fetchone()
    if active is None:
        now = utc_now()
        rules: list[dict[str, Any]] = []
        conn.execute(
            "INSERT INTO policy_versions VALUES (?, ?, 'observe_only', '[]', ?, 'active', NULL, ?, ?)",
            ("default-observe-only-v1", "Default observe-only", _hash_json(rules), now, now))
    conn.execute("PRAGMA user_version=1")
    conn.commit()


def _hash_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _target(args: dict[str, Any]) -> tuple[str, str]:
    for key in ("path", "file_path", "url", "target", "command", "cmd", "query"):
        value = args.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return key, str(value).strip()[:4000]
    return "arguments", json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)[:4000]


@dataclass(frozen=True)
class PolicyDecision:
    decision_id: str
    version_id: str
    action: str
    target_hash: str
    target_kind: str
    surface: str
    actor_id: str
    effect: str
    would_effect: str
    rule_id: str | None
    reason: str
    fingerprint: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return vars(self)


class PolicyEngine:
    """Evaluates one active immutable version and stores redacted decision receipts."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    @classmethod
    def open_default(cls) -> PolicyEngine:
        return cls(default_policy_path())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.path, db_label="plugin-data/mission-control/policy.db",
            synchronous_full=True, initialize=_initialize)

    def active(self) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM policy_versions WHERE status = 'active'").fetchone()
        if row is None:
            raise RuntimeError("no active policy version")
        return {**dict(row), "rules": json.loads(row["rules_json"])}

    @staticmethod
    def _normalize_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        seen = set()
        for index, source in enumerate(rules):
            rule = {
                "rule_id": str(source.get("rule_id") or f"rule-{index + 1}"),
                "action_pattern": str(source.get("action_pattern") or "*"),
                "target_pattern": str(source.get("target_pattern") or "*"),
                "surface_pattern": str(source.get("surface_pattern") or "*"),
                "effect": str(source.get("effect") or "allow"),
                "reason": str(source.get("reason") or "configured rule"),
                "priority": int(source.get("priority", 100)),
            }
            if rule["rule_id"] in seen or rule["effect"] not in EFFECTS:
                raise ValueError("policy rules need unique ids and a valid effect")
            seen.add(rule["rule_id"])
            normalized.append(rule)
        return sorted(normalized, key=lambda item: (item["priority"], item["rule_id"]))

    def stage(
        self, name: str, rules: list[dict[str, Any]], *, mode: str = "enforce",
    ) -> dict[str, Any]:
        if not name.strip() or mode not in MODES:
            raise ValueError("policy name and valid mode are required")
        normalized = self._normalize_rules(rules)
        parent = self.active()["version_id"]
        digest = _hash_json({"mode": mode, "rules": normalized})
        identity = f"policy-{digest[:20]}"
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO policy_versions VALUES (
                    ?, ?, ?, ?, ?, 'staged', ?, ?, NULL
                )""",
                (identity, name.strip(), mode, json.dumps(normalized, sort_keys=True), digest,
                 parent, utc_now()))
        return self.version(identity)

    def version(self, version_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM policy_versions WHERE version_id = ?", (version_id,)).fetchone()
        if row is None:
            raise KeyError(version_id)
        return {**dict(row), "rules": json.loads(row["rules_json"])}

    def promote(self, version_id: str) -> dict[str, Any]:
        candidate = self.version(version_id)
        if candidate["status"] not in {"staged", "retired"}:
            raise ValueError("only a staged or retired policy can be promoted")
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute("UPDATE policy_versions SET status = 'retired' WHERE status = 'active'")
            conn.execute(
                "UPDATE policy_versions SET status = 'active', promoted_at = ? WHERE version_id = ?",
                (utc_now(), version_id))
        return self.active()

    def rollback(self) -> dict[str, Any]:
        active = self.active()
        parent = active["parent_version_id"]
        if not parent:
            raise ValueError("active policy has no rollback parent")
        return self.promote(parent)

    def decide(
        self, action: str, args: dict[str, Any] | None = None, *,
        surface: str = "runtime", actor_id: str = "runtime-agent",
    ) -> PolicyDecision:
        args = args if isinstance(args, dict) else {}
        version = self.active()
        target_kind, raw_target = _target(args)
        target_hash = hashlib.sha256(raw_target.encode()).hexdigest()
        matched = None
        for rule in version["rules"]:
            if (
                fnmatch.fnmatchcase(action, rule["action_pattern"])
                and fnmatch.fnmatchcase(raw_target, rule["target_pattern"])
                and fnmatch.fnmatchcase(surface, rule["surface_pattern"])
            ):
                matched = rule
                break
        would_effect = matched["effect"] if matched else "allow"
        effect = "allow" if version["mode"] == "observe_only" else would_effect
        reason = (
            "observe-only profile recorded the matching rule without enforcement"
            if version["mode"] == "observe_only" and would_effect != "allow"
            else matched["reason"] if matched else "no policy rule matched"
        )
        if action in CONTROL_TOOLS:
            effect = "allow"
            reason = "policy control path remains available to prevent lockout"
        fingerprint = _hash_json({
            "action": action, "target_hash": target_hash, "target_kind": target_kind,
            "surface": surface, "actor_id": actor_id,
        })
        identity = hashlib.sha256(
            f"{version['version_id']}\0{fingerprint}".encode()).hexdigest()[:32]
        decision = PolicyDecision(
            decision_id=identity, version_id=version["version_id"], action=action,
            target_hash=target_hash, target_kind=target_kind, surface=surface,
            actor_id=actor_id, effect=effect, would_effect=would_effect,
            rule_id=matched["rule_id"] if matched else None, reason=reason,
            fingerprint=fingerprint, created_at=utc_now())
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO policy_decisions VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""",
                (decision.decision_id, decision.version_id, decision.action,
                 decision.target_hash, decision.target_kind, decision.surface,
                 decision.actor_id, decision.effect, decision.would_effect,
                 decision.rule_id, decision.reason, decision.fingerprint,
                 decision.created_at))
        return self.decision(identity)

    def decision(self, decision_id: str) -> PolicyDecision:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM policy_decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        if row is None:
            raise KeyError(decision_id)
        return PolicyDecision(**dict(row))

    def approve(self, decision_id: str, *, approved_by: str) -> dict[str, Any]:
        decision = self.decision(decision_id)
        if decision.effect != "require_confirmation":
            raise ValueError("only a confirmation decision can be approved")
        identity = uuid.uuid4().hex
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO policy_approvals VALUES (?, ?, ?, ?, NULL)",
                (identity, decision_id, approved_by or "user", utc_now()))
            row = conn.execute(
                "SELECT * FROM policy_approvals WHERE decision_id = ?", (decision_id,)).fetchone()
        return dict(row)

    def consume_approval(self, decision_id: str) -> bool:
        with transaction(self._connect(), immediate=True) as conn:
            row = conn.execute(
                "SELECT approval_id FROM policy_approvals WHERE decision_id = ? AND consumed_at IS NULL",
                (decision_id,)).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE policy_approvals SET consumed_at = ? WHERE approval_id = ?",
                (utc_now(), row["approval_id"]))
        return True

    def guard_tool(
        self, tool_name: str, args: dict[str, Any] | None, *,
        surface: str = "runtime", actor_id: str = "runtime-agent",
    ) -> dict[str, str] | None:
        decision = self.decide(tool_name, args, surface=surface, actor_id=actor_id)
        if decision.effect == "allow":
            return None
        if decision.effect == "require_confirmation" and self.consume_approval(decision.decision_id):
            return None
        return {
            "action": "block",
            "message": (
                f"Nara policy {decision.effect}: {decision.reason}. "
                f"Decision {decision.decision_id}; inspect with nara_policy_explain."
            ),
        }

    def status(self) -> dict[str, Any]:
        active = self.active()
        with transaction(self._connect()) as conn:
            version_count = conn.execute(
                "SELECT COUNT(*) AS count FROM policy_versions").fetchone()["count"]
            decision_count = conn.execute(
                "SELECT COUNT(*) AS count FROM policy_decisions").fetchone()["count"]
        return {
            "active": active, "version_count": version_count,
            "decision_count": decision_count,
        }


POLICY_STATUS_SCHEMA = {
    "name": "nara_policy_status", "description": "Inspect the active versioned Nara policy.",
    "parameters": {"type": "object", "properties": {}},
}
POLICY_EXPLAIN_SCHEMA = {
    "name": "nara_policy_explain", "description": "Explain one redacted policy decision receipt.",
    "parameters": {"type": "object", "properties": {
        "decision_id": {"type": "string"},
    }, "required": ["decision_id"]},
}
POLICY_CONFIRM_SCHEMA = {
    "name": "nara_policy_confirm", "description": "Approve one exact confirmation decision once.",
    "parameters": {"type": "object", "properties": {
        "decision_id": {"type": "string"}, "approved_by": {"type": "string"},
    }, "required": ["decision_id"]},
}
POLICY_STAGE_SCHEMA = {
    "name": "nara_policy_stage", "description": "Stage an immutable policy version for review.",
    "parameters": {"type": "object", "properties": {
        "name": {"type": "string"}, "mode": {"type": "string", "enum": sorted(MODES)},
        "rules": {"type": "array", "items": {"type": "object"}},
    }, "required": ["name", "rules"]},
}
POLICY_PROMOTE_SCHEMA = {
    "name": "nara_policy_promote", "description": "Promote one staged policy version atomically.",
    "parameters": {"type": "object", "properties": {
        "version_id": {"type": "string"},
    }, "required": ["version_id"]},
}
POLICY_ROLLBACK_SCHEMA = {
    "name": "nara_policy_rollback", "description": "Roll back to the active version's parent.",
    "parameters": {"type": "object", "properties": {}},
}


def policy_status_tool(**_: Any) -> dict[str, Any]:
    return PolicyEngine.open_default().status()


def policy_explain_tool(decision_id: str, **_: Any) -> dict[str, Any]:
    return PolicyEngine.open_default().decision(decision_id).to_dict()


def policy_confirm_tool(decision_id: str, approved_by: str = "user", **_: Any) -> dict[str, Any]:
    return PolicyEngine.open_default().approve(decision_id, approved_by=approved_by)


def policy_stage_tool(name: str, rules: list[dict[str, Any]], mode: str = "enforce", **_: Any) -> dict[str, Any]:
    return PolicyEngine.open_default().stage(name, rules, mode=mode)


def policy_promote_tool(version_id: str, **_: Any) -> dict[str, Any]:
    return PolicyEngine.open_default().promote(version_id)


def policy_rollback_tool(**_: Any) -> dict[str, Any]:
    return PolicyEngine.open_default().rollback()
