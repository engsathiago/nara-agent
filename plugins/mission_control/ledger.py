"""Privacy-conscious local Experience Ledger for mission execution facts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import utc_now
from plugins.mission_control.store import MissionStore
from plugins.plugin_storage import plugin_data_dir


DB_SCHEMA_VERSION = 1


def default_ledger_path() -> Path:
    return plugin_data_dir("mission-control") / "experience-ledger.db"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS experience_events (
            event_id TEXT PRIMARY KEY,
            mission_id TEXT,
            task_id TEXT,
            session_id TEXT,
            turn_id TEXT,
            agent_id TEXT,
            kind TEXT NOT NULL,
            status TEXT,
            tool TEXT,
            model TEXT,
            provider TEXT,
            duration_ms INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost_usd REAL,
            payload_json TEXT NOT NULL,
            occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS experience_mission_time
            ON experience_events (mission_id, occurred_at, event_id);
        CREATE INDEX IF NOT EXISTS experience_session_time
            ON experience_events (session_id, occurred_at, event_id);
    """)
    current = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if current not in {0, DB_SCHEMA_VERSION}:
        raise RuntimeError(f"unsupported Experience Ledger schema {current}")
    conn.execute(f"PRAGMA user_version={DB_SCHEMA_VERSION}")
    conn.commit()


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class ExperienceLedger:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    @classmethod
    def open_default(cls) -> ExperienceLedger:
        return cls(default_ledger_path())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.path,
            db_label="plugin-data/mission-control/experience-ledger.db",
            synchronous_full=True,
            initialize=_initialize,
        )

    def record(
        self,
        *,
        kind: str,
        event_id: str | None = None,
        mission_id: str | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
        turn_id: str | None = None,
        agent_id: str | None = None,
        status: str | None = None,
        tool: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        duration_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: float | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        identity = event_id or uuid.uuid4().hex
        encoded = json.dumps(payload or {}, sort_keys=True, ensure_ascii=False, default=str)
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO experience_events (
                    event_id, mission_id, task_id, session_id, turn_id, agent_id, kind, status,
                    tool, model, provider, duration_ms, input_tokens, output_tokens, cost_usd,
                    payload_json, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    identity, mission_id, task_id, session_id, turn_id, agent_id, kind, status,
                    tool, model, provider, duration_ms, input_tokens, output_tokens, cost_usd, encoded,
                    utc_now(),
                ),
            )
        return identity

    def events(self, mission_id: str) -> list[dict[str, Any]]:
        with transaction(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM experience_events WHERE mission_id = ? ORDER BY occurred_at, event_id",
                (mission_id,),
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]

    def mission_tree(self, missions: MissionStore, mission_id: str) -> dict[str, Any]:
        mission = missions.get(mission_id)
        if mission is None:
            return {"mission_id": mission_id, "error": "mission not found"}
        experiences = self.events(mission_id)
        tasks = []
        for task_id, status in mission.task_states.items():
            task_events = [item for item in experiences if item["task_id"] == task_id]
            tasks.append({
                "task_id": task_id,
                "status": status,
                "agents": sorted({item["agent_id"] for item in task_events if item["agent_id"]}),
                "turns": sorted({item["turn_id"] for item in task_events if item["turn_id"]}),
                "tools": [item for item in task_events if item["kind"].startswith("tool.")],
            })
        return {
            "mission": mission.to_dict(),
            "mission_events": [event.to_dict() for event in missions.events(mission_id)],
            "tasks": tasks,
            "artifacts": list(mission.artifacts.values()),
            "verifications": list(mission.verifications.values()),
            "experience_events": experiences,
            "totals": {
                "duration_ms": sum(item["duration_ms"] or 0 for item in experiences),
                "input_tokens": sum(item["input_tokens"] or 0 for item in experiences),
                "output_tokens": sum(item["output_tokens"] or 0 for item in experiences),
                "cost_usd": sum(item["cost_usd"] or 0.0 for item in experiences),
                "errors": sum(item["status"] == "error" for item in experiences),
            },
        }


def mission_for_session(store: MissionStore, session_id: str):
    return next((
        mission for mission in store.list()
        if str(mission.goal_ref.get("session_id") or "") == session_id
    ), None)


def record_llm_call(
    session_id: str = "",
    task_id: str = "",
    turn_id: str = "",
    model: str = "",
    provider: str = "",
    duration_ms: int = 0,
    usage: dict[str, Any] | None = None,
    cost_usd: float | None = None,
    status: str = "ok",
    **_: Any,
) -> None:
    if not session_id:
        return
    missions = MissionStore.open_default()
    mission = missions.mission_for_task(task_id) if task_id else mission_for_session(missions, session_id)
    if mission is None:
        return
    token_usage = usage or {}
    signature = hashlib.sha256(
        f"{mission.mission_id}\0{session_id}\0{turn_id}\0{model}\0{duration_ms}".encode()).hexdigest()
    ExperienceLedger.open_default().record(
        event_id=f"llm:{signature}",
        kind="llm.completed",
        mission_id=mission.mission_id,
        task_id=task_id or None,
        session_id=session_id,
        turn_id=turn_id or None,
        agent_id=session_id,
        model=model or None,
        provider=provider or None,
        duration_ms=_safe_int(duration_ms),
        input_tokens=_safe_int(token_usage.get("input_tokens") or token_usage.get("prompt_tokens")),
        output_tokens=_safe_int(token_usage.get("output_tokens") or token_usage.get("completion_tokens")),
        cost_usd=_safe_float(cost_usd),
        status=status,
        payload={"usage_keys": sorted(token_usage)},
    )
