"""Append-only Mission Control event log with a transactional current-state projection."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import (
    Artifact,
    Mission,
    MissionEvent,
    MissionStatus,
    Receipt,
    Verification,
    VerificationStatus,
    WorkerLease,
    assert_mission_transition,
    load_contract,
    utc_now,
)
from plugins.plugin_storage import plugin_data_dir


DB_SCHEMA_VERSION = 1
PLUGIN_DATA_NAME = "mission-control"


class MissionStoreError(RuntimeError):
    """Durable mission state could not be read or changed consistently."""


class MissionNotFoundError(MissionStoreError):
    pass


class IdempotencyConflictError(MissionStoreError):
    pass


def default_store_path() -> Path:
    return plugin_data_dir(PLUGIN_DATA_NAME) / "missions.db"


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS mission_events (
            event_id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            idempotency_key TEXT,
            schema_version INTEGER NOT NULL,
            UNIQUE (mission_id, sequence),
            UNIQUE (mission_id, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS mission_events_mission_sequence
            ON mission_events (mission_id, sequence);
        CREATE TABLE IF NOT EXISTS missions (
            mission_id TEXT PRIMARY KEY,
            projection_json TEXT NOT NULL,
            last_sequence INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL
        );
    """)
    current = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if current not in {0, DB_SCHEMA_VERSION}:
        raise MissionStoreError(f"unsupported Mission Store schema {current}")
    conn.execute(f"PRAGMA user_version={DB_SCHEMA_VERSION}")
    conn.commit()


def _event_from_row(row: sqlite3.Row) -> MissionEvent:
    return MissionEvent(
        event_id=row["event_id"], mission_id=row["mission_id"], sequence=row["sequence"],
        event_type=row["event_type"], occurred_at=row["occurred_at"], actor_id=row["actor_id"],
        payload=json.loads(row["payload_json"]), idempotency_key=row["idempotency_key"],
        schema_version=row["schema_version"],
    )


def _mission_from_row(row: sqlite3.Row) -> Mission:
    mission = load_contract(json.loads(row["projection_json"]))
    if not isinstance(mission, Mission):
        raise MissionStoreError("mission projection contains the wrong contract kind")
    return mission


def reduce_event(current: Mission | None, event: MissionEvent) -> Mission:
    """Pure projection reducer used by live writes and full reconstruction."""
    if event.event_type == "mission.created":
        if current is not None:
            raise MissionStoreError(f"mission {event.mission_id} was created twice")
        mission = load_contract(event.payload["mission"])
        if not isinstance(mission, Mission) or mission.mission_id != event.mission_id:
            raise MissionStoreError("mission.created payload does not match its event")
        return mission
    if current is None:
        raise MissionStoreError(f"{event.event_type} precedes mission.created")
    if event.event_type == "mission.status_changed":
        target = MissionStatus(event.payload["status"])
        assert_mission_transition(current.status, target)
        if target is MissionStatus.COMPLETED:
            blockers = completion_blockers(current)
            if blockers:
                raise MissionStoreError(
                    "mission completion is blocked: " + "; ".join(blockers))
        return replace(current, status=target, updated_at=event.occurred_at, version=current.version + 1)
    if event.event_type == "mission.task_requested":
        request_key = str(event.payload["request_key"])
        requests = dict(current.task_requests)
        requests[request_key] = {"status": "requested", "spec": dict(event.payload["spec"])}
        return replace(current, task_requests=requests, updated_at=event.occurred_at,
                       version=current.version + 1)
    if event.event_type == "mission.task_linked":
        request_key, task_id = str(event.payload["request_key"]), str(event.payload["task_id"])
        if request_key not in current.task_requests:
            raise MissionStoreError(f"task link has no persisted request: {request_key}")
        requests, states = dict(current.task_requests), dict(current.task_states)
        requests[request_key] = {**requests[request_key], "status": "linked", "task_id": task_id}
        states[task_id] = str(event.payload["status"])
        return replace(current, task_requests=requests, task_states=states,
                       updated_at=event.occurred_at, version=current.version + 1)
    if event.event_type == "mission.task_status_changed":
        task_id = str(event.payload["task_id"])
        if task_id not in current.task_states:
            raise MissionStoreError(f"task status has no mission link: {task_id}")
        states = dict(current.task_states)
        states[task_id] = str(event.payload["status"])
        return replace(current, task_states=states, updated_at=event.occurred_at,
                       version=current.version + 1)
    if event.event_type in {"mission.receipt_prepared", "mission.receipt_settled"}:
        receipt = load_contract(event.payload["receipt"])
        if not isinstance(receipt, Receipt) or receipt.mission_id != current.mission_id:
            raise MissionStoreError("receipt event does not match its mission")
        receipts = dict(current.receipts)
        receipts[receipt.receipt_id] = receipt.to_dict()
        return replace(current, receipts=receipts, updated_at=event.occurred_at,
                       version=current.version + 1)
    if event.event_type == "mission.artifact_registered":
        artifact = load_contract(event.payload["artifact"])
        if not isinstance(artifact, Artifact) or artifact.mission_id != current.mission_id:
            raise MissionStoreError("artifact event does not match its mission")
        artifacts = dict(current.artifacts)
        artifacts[artifact.artifact_id] = artifact.to_dict()
        return replace(current, artifacts=artifacts, updated_at=event.occurred_at,
                       version=current.version + 1)
    if event.event_type == "mission.verification_recorded":
        verification = load_contract(event.payload["verification"])
        if not isinstance(verification, Verification) or verification.mission_id != current.mission_id:
            raise MissionStoreError("verification event does not match its mission")
        verifications = dict(current.verifications)
        verifications[verification.verification_id] = verification.to_dict()
        return replace(current, verifications=verifications, updated_at=event.occurred_at,
                       version=current.version + 1)
    if event.event_type == "mission.goal_bound":
        return replace(
            current,
            goal_ref=dict(event.payload),
            updated_at=event.occurred_at,
            version=current.version + 1,
        )
    if event.event_type in {"mission.schedule_requested", "mission.schedule_linked"}:
        schedule_key = str(event.payload["schedule_key"])
        schedules = dict(current.schedules)
        schedules[schedule_key] = dict(event.payload)
        return replace(
            current, schedules=schedules, updated_at=event.occurred_at, version=current.version + 1)
    if event.event_type == "mission.worker_lease_recorded":
        lease = load_contract(event.payload["lease"])
        if not isinstance(lease, WorkerLease) or lease.mission_id != current.mission_id:
            raise MissionStoreError("worker lease event does not match its mission")
        leases = dict(current.leases)
        leases[lease.lease_id] = lease.to_dict()
        return replace(current, leases=leases, updated_at=event.occurred_at,
                       version=current.version + 1)
    if event.event_type == "mission.diagnostic_recorded":
        diagnostic_id = str(event.payload["diagnostic_id"])
        diagnostics = dict(current.diagnostics)
        diagnostics[diagnostic_id] = dict(event.payload)
        return replace(current, diagnostics=diagnostics, updated_at=event.occurred_at,
                       version=current.version + 1)
    if event.event_type == "mission.voice_event_recorded":
        voice_event_id = str(event.payload["voice_event_id"])
        voice_events = dict(current.voice_events)
        voice_events[voice_event_id] = dict(event.payload)
        return replace(current, voice_events=voice_events, updated_at=event.occurred_at,
                       version=current.version + 1)
    raise MissionStoreError(f"unsupported mission event type: {event.event_type}")


def completion_blockers(mission: Mission) -> list[str]:
    """Return criteria that do not have a latest independent PASS."""
    latest: dict[str, Verification] = {}
    for payload in mission.verifications.values():
        verification = load_contract(payload)
        if not isinstance(verification, Verification):
            continue
        previous = latest.get(verification.criterion)
        if previous is None or verification.observed_at >= previous.observed_at:
            latest[verification.criterion] = verification
    blockers = []
    for criterion in mission.completion_criteria:
        verification = latest.get(criterion)
        if verification is None:
            blockers.append(f"{criterion!r} has no verification")
        elif verification.status is not VerificationStatus.PASS:
            blockers.append(f"{criterion!r} is {verification.status.value}")
    return blockers


class MissionStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    @classmethod
    def open_default(cls) -> MissionStore:
        return cls(default_store_path())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.path,
            db_label="plugin-data/mission-control/missions.db",
            foreign_keys=True,
            synchronous_full=True,
            # Background workers and status readers may open a fresh profile together.
            wal_lock_retries=5,
            initialize=_initialize,
        )

    def create(self, mission: Mission, *, actor_id: str = "user", idempotency_key: str | None = None) -> Mission:
        event = MissionEvent(
            event_id=uuid.uuid4().hex,
            mission_id=mission.mission_id,
            sequence=1,
            event_type="mission.created",
            actor_id=actor_id,
            payload={"mission": mission.to_dict()},
            idempotency_key=idempotency_key,
        )
        with transaction(self._connect(), immediate=True) as conn:
            existing = self._idempotent_event(conn, event)
            if existing:
                projected = self._projection(conn, mission.mission_id)
                if projected is None:
                    raise MissionStoreError("idempotent create event has no projection")
                return projected
            if self._projection(conn, mission.mission_id) is not None:
                raise MissionStoreError(f"mission already exists: {mission.mission_id}")
            self._insert_event(conn, event)
            self._write_projection(conn, reduce_event(None, event), event.sequence)
        return mission

    def transition(
        self,
        mission_id: str,
        target: MissionStatus | str,
        *,
        actor_id: str = "user",
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> Mission:
        return self._append(
            mission_id, "mission.status_changed",
            {"status": MissionStatus(target).value, "reason": reason},
            actor_id=actor_id, idempotency_key=idempotency_key,
        )

    def request_task(
        self, mission_id: str, request_key: str, spec: dict[str, Any], *, actor_id: str = "leader",
    ) -> Mission:
        return self._append(
            mission_id, "mission.task_requested", {"request_key": request_key, "spec": spec},
            actor_id=actor_id, idempotency_key=f"task-request:{request_key}",
        )

    def link_task(
        self, mission_id: str, request_key: str, task_id: str, status: str,
        *, actor_id: str = "kanban",
    ) -> Mission:
        return self._append(
            mission_id, "mission.task_linked",
            {"request_key": request_key, "task_id": task_id, "status": status},
            actor_id=actor_id, idempotency_key=f"task-link:{request_key}",
        )

    def record_task_status(
        self, task_id: str, status: str, *, idempotency_key: str, actor_id: str = "kanban",
    ) -> Mission | None:
        mission = self.mission_for_task(task_id)
        if mission is None:
            return None
        return self._append(
            mission.mission_id, "mission.task_status_changed", {"task_id": task_id, "status": status},
            actor_id=actor_id, idempotency_key=idempotency_key,
        )

    def prepare_receipt(self, receipt: Receipt) -> Mission:
        return self._append(
            receipt.mission_id, "mission.receipt_prepared", {"receipt": receipt.to_dict()},
            actor_id=receipt.agent_id, idempotency_key=f"receipt-prepare:{receipt.idempotency_key}",
        )

    def settle_receipt(self, receipt: Receipt, *, idempotency_key: str) -> Mission:
        return self._append(
            receipt.mission_id, "mission.receipt_settled", {"receipt": receipt.to_dict()},
            actor_id=receipt.agent_id, idempotency_key=idempotency_key,
        )

    def register_artifact(self, artifact: Artifact) -> Mission:
        return self._append(
            artifact.mission_id, "mission.artifact_registered", {"artifact": artifact.to_dict()},
            actor_id=artifact.producer_id, idempotency_key=f"artifact:{artifact.artifact_id}",
        )

    def record_verification(self, verification: Verification) -> Mission:
        return self._append(
            verification.mission_id,
            "mission.verification_recorded",
            {"verification": verification.to_dict()},
            actor_id=verification.verifier_id,
            idempotency_key=f"verification:{verification.verification_id}",
        )

    def bind_goal(self, mission_id: str, goal_ref: dict[str, Any]) -> Mission:
        session_id = str(goal_ref.get("session_id") or "")
        return self._append(
            mission_id, "mission.goal_bound", goal_ref, actor_id="mission-leader",
            idempotency_key=f"goal-bind:{session_id}",
        )

    def request_schedule(
        self, mission_id: str, schedule_key: str, spec: dict[str, Any], *, idempotency_key: str,
    ) -> Mission:
        return self._append(
            mission_id, "mission.schedule_requested",
            {"schedule_key": schedule_key, "status": "requested", "spec": spec},
            actor_id="mission-leader", idempotency_key=idempotency_key,
        )

    def link_schedule(
        self, mission_id: str, schedule_key: str, job_id: str, spec: dict[str, Any],
    ) -> Mission:
        return self._append(
            mission_id, "mission.schedule_linked",
            {"schedule_key": schedule_key, "status": "linked", "job_id": job_id, "spec": spec},
            actor_id="scheduler", idempotency_key=f"schedule-link:{schedule_key}",
        )

    def record_lease(self, lease: WorkerLease, *, idempotency_key: str) -> Mission:
        return self._append(
            lease.mission_id, "mission.worker_lease_recorded", {"lease": lease.to_dict()},
            actor_id=lease.worker_id, idempotency_key=idempotency_key,
        )

    def record_diagnostic(
        self, mission_id: str, diagnostic: dict[str, Any], *, idempotency_key: str,
    ) -> Mission:
        return self._append(
            mission_id, "mission.diagnostic_recorded", diagnostic,
            actor_id="mission-supervisor", idempotency_key=idempotency_key,
        )

    def record_voice_event(
        self, mission_id: str, voice_event: dict[str, Any], *, idempotency_key: str,
    ) -> Mission:
        return self._append(
            mission_id, "mission.voice_event_recorded", voice_event,
            actor_id="voice-surface", idempotency_key=idempotency_key,
        )

    def mission_for_task(self, task_id: str) -> Mission | None:
        for mission in self.list():
            if task_id in mission.task_states:
                return mission
        return None

    def _append(
        self, mission_id: str, event_type: str, payload: dict[str, Any], *, actor_id: str,
        idempotency_key: str | None,
    ) -> Mission:
        with transaction(self._connect(), immediate=True) as conn:
            current = self._projection(conn, mission_id)
            if current is None:
                raise MissionNotFoundError(mission_id)
            event = MissionEvent(
                event_id=uuid.uuid4().hex, mission_id=mission_id,
                sequence=self._last_sequence(conn, mission_id) + 1, event_type=event_type,
                actor_id=actor_id, payload=payload, idempotency_key=idempotency_key,
            )
            existing = self._idempotent_event(conn, event)
            if existing:
                projected = self._projection(conn, mission_id)
                if projected is None:
                    raise MissionStoreError("idempotent event has no projection")
                return projected
            projected = reduce_event(current, event)
            self._insert_event(conn, event)
            self._write_projection(conn, projected, event.sequence)
            return projected

    def get(self, mission_id: str) -> Mission | None:
        with transaction(self._connect()) as conn:
            return self._projection(conn, mission_id)

    def list(self, *, status: MissionStatus | str | None = None) -> list[Mission]:
        with transaction(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM missions ORDER BY updated_at DESC, mission_id").fetchall()
        missions = [_mission_from_row(row) for row in rows]
        return [mission for mission in missions if mission.status is MissionStatus(status)] if status else missions

    def events(self, mission_id: str) -> list[MissionEvent]:
        with transaction(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM mission_events WHERE mission_id = ? ORDER BY sequence", (mission_id,),
            ).fetchall()
        return [_event_from_row(row) for row in rows]

    def reconstruct(self, mission_id: str) -> Mission:
        events = self.events(mission_id)
        if not events:
            raise MissionNotFoundError(mission_id)
        current: Mission | None = None
        expected = 1
        for event in events:
            if event.sequence != expected:
                raise MissionStoreError(f"event sequence gap for {mission_id}: expected {expected}, got {event.sequence}")
            current = reduce_event(current, event)
            expected += 1
        if current is None:
            raise MissionStoreError(f"mission {mission_id} reconstructed to empty state")
        return current

    def rebuild_projection(self, mission_id: str) -> Mission:
        reconstructed = self.reconstruct(mission_id)
        events = self.events(mission_id)
        with transaction(self._connect(), immediate=True) as conn:
            self._write_projection(conn, reconstructed, events[-1].sequence)
        return reconstructed

    def verify_projection(self, mission_id: str) -> bool:
        stored = self.get(mission_id)
        if stored is None:
            raise MissionNotFoundError(mission_id)
        return stored == self.reconstruct(mission_id)

    @staticmethod
    def _projection(conn: sqlite3.Connection, mission_id: str) -> Mission | None:
        row = conn.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,)).fetchone()
        return _mission_from_row(row) if row else None

    @staticmethod
    def _last_sequence(conn: sqlite3.Connection, mission_id: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM mission_events WHERE mission_id = ?",
            (mission_id,),
        ).fetchone()
        return int(row["sequence"])

    @staticmethod
    def _insert_event(conn: sqlite3.Connection, event: MissionEvent) -> None:
        conn.execute(
            """INSERT INTO mission_events
               (event_id, mission_id, sequence, event_type, occurred_at, actor_id, payload_json,
                idempotency_key, schema_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event.event_id, event.mission_id, event.sequence, event.event_type, event.occurred_at,
             event.actor_id, _canonical_json(event.payload), event.idempotency_key, event.schema_version),
        )

    @staticmethod
    def _write_projection(conn: sqlite3.Connection, mission: Mission, sequence: int) -> None:
        conn.execute(
            """INSERT INTO missions (mission_id, projection_json, last_sequence, updated_at, schema_version)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(mission_id) DO UPDATE SET
                 projection_json=excluded.projection_json,
                 last_sequence=excluded.last_sequence,
                 updated_at=excluded.updated_at,
                 schema_version=excluded.schema_version""",
            (mission.mission_id, _canonical_json(mission.to_dict()), sequence, mission.updated_at,
             mission.schema_version),
        )

    @staticmethod
    def _idempotent_event(conn: sqlite3.Connection, event: MissionEvent) -> MissionEvent | None:
        if not event.idempotency_key:
            return None
        row = conn.execute(
            "SELECT * FROM mission_events WHERE mission_id = ? AND idempotency_key = ?",
            (event.mission_id, event.idempotency_key),
        ).fetchone()
        if row is None:
            return None
        existing = _event_from_row(row)
        if existing.event_type != event.event_type or existing.payload != event.payload:
            raise IdempotencyConflictError(
                f"idempotency key {event.idempotency_key!r} was already used for another event")
        return existing


def reconstruct_events(events: Iterable[MissionEvent]) -> Mission:
    current: Mission | None = None
    for event in events:
        current = reduce_event(current, event)
    if current is None:
        raise MissionStoreError("cannot reconstruct an empty event stream")
    return current

