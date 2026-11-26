"""Idempotently turn verified completed missions into inactive learning candidates."""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nara_cli.sqlite_util import open_db, transaction
from nara_constants import get_nara_home
from plugins.memory import import_provider_module
from plugins.mission_control.contracts import MissionStatus
from plugins.mission_control.learning import LearningLab
from plugins.mission_control.store import MissionStore


INTERVAL_SECONDS = 600


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS processed_missions (
            mission_id TEXT PRIMARY KEY,
            mission_version INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            candidate_id TEXT,
            error TEXT,
            processed_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cadence (
            name TEXT PRIMARY KEY,
            claimed_at REAL NOT NULL
        );
    """)
    conn.commit()


class MissionConsolidator:
    def __init__(self, missions: MissionStore, lab: LearningLab, state_path: Path | str):
        self.missions = missions
        self.lab = lab
        self.state_path = Path(state_path)

    @classmethod
    def open_default(cls) -> MissionConsolidator:
        missions = MissionStore.open_default()
        home = get_nara_home()
        candidates = missions.path.parent / "learning" / "candidates"
        provider = import_provider_module("nara_temporal")
        lab = LearningLab(
            missions,
            provider.TemporalMemoryStore(home / "memories" / "nara-temporal.db"),
            candidates,
            home / "skills",
        )
        return cls(missions, lab, missions.path.parent / "learning" / "consolidation.db")

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.state_path,
            db_label="plugin-data/mission-control/learning/consolidation.db",
            synchronous_full=True,
            initialize=_initialize,
        )

    def status(self) -> dict[str, Any]:
        completed = self.missions.list(status=MissionStatus.COMPLETED)
        known: dict[str, sqlite3.Row] = {}
        last_claimed = None
        if self.state_path.exists():
            with transaction(self._connect()) as conn:
                known = {
                    row["mission_id"]: row for row in conn.execute("SELECT * FROM processed_missions")
                }
                last_claimed = conn.execute(
                    "SELECT claimed_at FROM cadence WHERE name = 'consolidation'"
                ).fetchone()
        pending = [
            mission.mission_id for mission in completed
            if mission.mission_id not in known
            or known[mission.mission_id]["mission_version"] != mission.version
            or known[mission.mission_id]["outcome"] == "error"
        ]
        errors = [
            {"mission_id": row["mission_id"], "error": row["error"]}
            for row in known.values() if row["outcome"] == "error"
        ]
        counts = {name: sum(row["outcome"] == name for row in known.values())
                  for name in ("candidate", "skipped", "error")}
        return {
            "state": "degraded" if errors else "available",
            "completed_missions": len(completed),
            "processed": counts,
            "pending": len(pending),
            "pending_mission_ids": pending[:20],
            "errors": errors[:20],
            "last_claimed_at": (
                datetime.fromtimestamp(last_claimed["claimed_at"], UTC).isoformat()
                if last_claimed else None
            ),
        }

    def run_once(self, *, limit: int = 100) -> dict[str, Any]:
        if limit < 1:
            raise ValueError("consolidation limit must be positive")
        result: dict[str, Any] = {"created": [], "unchanged": 0, "skipped": [], "errors": []}
        completed = self.missions.list(status=MissionStatus.COMPLETED)
        with transaction(self._connect()) as conn:
            known = {
                row["mission_id"]: row for row in conn.execute("SELECT * FROM processed_missions")
            }
        pending = [
            mission for mission in completed
            if mission.mission_id not in known
            or known[mission.mission_id]["mission_version"] != mission.version
            or known[mission.mission_id]["outcome"] == "error"
        ]
        result["unchanged"] = len(completed) - len(pending)
        result["remaining"] = max(0, len(pending) - limit)
        for mission in pending[:limit]:
            candidate_id = None
            error = None
            try:
                candidate = self.lab.extract(mission.mission_id)
                candidate_id = candidate.candidate_id
                outcome = "candidate"
                result["created"].append({"mission_id": mission.mission_id, "candidate_id": candidate_id})
            except ValueError as exc:
                error = str(exc)
                if "no reusable observed procedure" in error:
                    outcome = "skipped"
                    result["skipped"].append({"mission_id": mission.mission_id, "reason": error})
                else:
                    outcome = "error"
                    result["errors"].append({"mission_id": mission.mission_id, "error": error})
            except Exception as exc:
                logging.getLogger(__name__).exception(
                    "Could not consolidate completed mission %s", mission.mission_id,
                )
                outcome = "error"
                error = f"{type(exc).__name__}: {exc}"
                result["errors"].append({"mission_id": mission.mission_id, "error": error})
            with transaction(self._connect(), immediate=True) as conn:
                conn.execute(
                    """INSERT INTO processed_missions VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mission_id) DO UPDATE SET
                      mission_version=excluded.mission_version,
                      outcome=excluded.outcome,
                      candidate_id=excluded.candidate_id,
                      error=excluded.error,
                      processed_at=excluded.processed_at""",
                    (mission.mission_id, mission.version, outcome, candidate_id, error, time.time()),
                )
        return result

    def run_due(self, *, now: float | None = None) -> dict[str, Any] | None:
        stamp = time.time() if now is None else now
        with transaction(self._connect(), immediate=True) as conn:
            last = conn.execute("SELECT claimed_at FROM cadence WHERE name = 'consolidation'").fetchone()
            if last is not None and stamp - last["claimed_at"] < INTERVAL_SECONDS:
                return None
            conn.execute(
                """INSERT INTO cadence VALUES ('consolidation', ?)
                ON CONFLICT(name) DO UPDATE SET claimed_at=excluded.claimed_at""",
                (stamp,),
            )
        return self.run_once()


def maybe_run_gateway_consolidation(log: logging.Logger | None = None) -> dict[str, Any] | None:
    """Gateway housekeeping entry: per-profile, due-gated, and safe when unused."""
    missions = MissionStore.open_default()
    if not missions.path.exists():
        return None
    logger = log or logging.getLogger(__name__)
    try:
        report = MissionConsolidator.open_default().run_due()
    except Exception:
        logger.exception("Mission learning consolidation failed")
        return None
    if report and (report["created"] or report["errors"]):
        logger.info("Mission learning consolidation: %s", report)
    return report


LEARNING_STATUS_SCHEMA = {
    "name": "nara_learning_status",
    "description": "Check automatic mission learning availability, pending work, and failures.",
    "parameters": {"type": "object", "properties": {}},
}


def learning_status_tool(**_: Any) -> dict[str, Any]:
    missions = MissionStore.open_default()
    if not missions.path.exists():
        return {"state": "unavailable", "reason": "no mission store exists in this profile"}
    try:
        return MissionConsolidator.open_default().status()
    except (FileNotFoundError, ImportError, RuntimeError) as exc:
        return {"state": "unavailable", "reason": str(exc)}
