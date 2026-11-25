"""Fleet host inventory and safe mission-lease reassignment across environments."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import EffectStatus, LeaseStatus, load_contract, utc_now
from plugins.mission_control.store import MissionNotFoundError, MissionStore
from plugins.mission_control.workers import WorkerLeaseService
from plugins.plugin_storage import plugin_data_dir


def default_fleet_root() -> Path:
    return plugin_data_dir("mission-control") / "fleet"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fleet_hosts (
            host_id TEXT PRIMARY KEY, endpoint TEXT NOT NULL, environment TEXT NOT NULL,
            capabilities_json TEXT NOT NULL, labels_json TEXT NOT NULL, status TEXT NOT NULL,
            last_heartbeat TEXT NOT NULL, registered_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fleet_assignments (
            assignment_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, task_id TEXT NOT NULL,
            host_id TEXT NOT NULL, lease_id TEXT NOT NULL, required_json TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fleet_handoffs (
            handoff_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, task_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL, content_hash TEXT NOT NULL, stored_path TEXT NOT NULL,
            from_host TEXT NOT NULL, to_host TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL
        );
    """)
    conn.execute("PRAGMA user_version=1")
    conn.commit()


class FleetCoordinator:
    def __init__(self, root: Path | str, missions: MissionStore):
        self.root = Path(root)
        self.db_path = self.root / "fleet.db"
        self.missions = missions
        self.leases = WorkerLeaseService(missions)

    @classmethod
    def open_default(cls) -> FleetCoordinator:
        root = default_fleet_root()
        return cls(root, MissionStore.open_default())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.db_path, db_label="plugin-data/mission-control/fleet/fleet.db",
            synchronous_full=True, initialize=_initialize)

    def register_host(
        self, host_id: str, endpoint: str, environment: str, capabilities: Iterable[str],
        *, labels: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                """INSERT INTO fleet_hosts VALUES (?, ?, ?, ?, ?, 'online', ?, ?)
                   ON CONFLICT(host_id) DO UPDATE SET endpoint=excluded.endpoint,
                   environment=excluded.environment, capabilities_json=excluded.capabilities_json,
                   labels_json=excluded.labels_json, status='online', last_heartbeat=excluded.last_heartbeat""",
                (host_id, endpoint, environment, json.dumps(sorted(set(capabilities))),
                 json.dumps(labels or {}, sort_keys=True), now, now))
        return self.host(host_id)

    def host(self, host_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM fleet_hosts WHERE host_id = ?", (host_id,)).fetchone()
        if row is None:
            raise KeyError(host_id)
        return {
            **dict(row), "capabilities": json.loads(row["capabilities_json"]),
            "labels": json.loads(row["labels_json"]),
        }

    def heartbeat(self, host_id: str, *, status: str = "online") -> dict[str, Any]:
        with transaction(self._connect(), immediate=True) as conn:
            result = conn.execute(
                "UPDATE fleet_hosts SET status = ?, last_heartbeat = ? WHERE host_id = ?",
                (status, utc_now(), host_id))
            if result.rowcount != 1:
                raise KeyError(host_id)
        return self.host(host_id)

    def hosts(self, *, status: str | None = None) -> list[dict[str, Any]]:
        clause = "WHERE status = ?" if status else ""
        params = (status,) if status else ()
        with transaction(self._connect()) as conn:
            ids = [row["host_id"] for row in conn.execute(
                f"SELECT host_id FROM fleet_hosts {clause} ORDER BY host_id", params).fetchall()]
        return [self.host(host_id) for host_id in ids]

    def select_host(self, required: Iterable[str], *, exclude: Iterable[str] = ()) -> dict[str, Any]:
        required_set = set(required)
        excluded = set(exclude)
        eligible = [host for host in self.hosts(status="online") if (
            host["host_id"] not in excluded and required_set <= set(host["capabilities"]))]
        if not eligible:
            raise ValueError(f"no online fleet host satisfies: {sorted(required_set)}")
        return min(eligible, key=lambda item: item["host_id"])

    def assign(
        self, mission_id: str, task_id: str, required: Iterable[str], *, ttl_seconds: int = 300,
        exclude_hosts: Iterable[str] = (),
    ) -> dict[str, Any]:
        host = self.select_host(required, exclude=exclude_hosts)
        lease = self.leases.claim(
            mission_id, task_id, f"host:{host['host_id']}", ttl_seconds=ttl_seconds,
            lease_id=f"fleet:{task_id}:{uuid.uuid4().hex[:12]}")
        now = utc_now()
        identity = uuid.uuid4().hex
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT INTO fleet_assignments VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)",
                (identity, mission_id, task_id, host["host_id"], lease.lease_id,
                 json.dumps(sorted(set(required))), now, now))
        return self.assignment(identity)

    def assignment(self, assignment_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM fleet_assignments WHERE assignment_id = ?", (assignment_id,)).fetchone()
        if row is None:
            raise KeyError(assignment_id)
        return {**dict(row), "required_capabilities": json.loads(row["required_json"])}

    def put_handoff(
        self, mission_id: str, task_id: str, artifact_id: str, content: bytes, *, from_host: str,
    ) -> dict[str, Any]:
        digest = hashlib.sha256(content).hexdigest()
        destination = self.root / "handoffs" / digest[:2] / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            with NamedTemporaryFile("wb", dir=destination.parent, delete=False) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            temporary.replace(destination)
        identity = hashlib.sha256(
            f"{mission_id}\0{task_id}\0{artifact_id}\0{digest}".encode()).hexdigest()[:24]
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO fleet_handoffs VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'ready', ?)",
                (identity, mission_id, task_id, artifact_id, digest, str(destination), from_host, utc_now()))
        return self.handoff(identity)

    def handoff(self, handoff_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM fleet_handoffs WHERE handoff_id = ?", (handoff_id,)).fetchone()
        if row is None:
            raise KeyError(handoff_id)
        return dict(row)

    def _receipt_state(self, mission_id: str, task_id: str) -> tuple[list[str], list[str]]:
        mission = self.missions.get(mission_id)
        if mission is None:
            raise MissionNotFoundError(mission_id)
        confirmed, uncertain = [], []
        for payload in mission.receipts.values():
            receipt = load_contract(payload)
            if getattr(receipt, "task_id", None) != task_id:
                continue
            if receipt.effect_status is EffectStatus.CONFIRMED:
                confirmed.append(receipt.receipt_id)
            elif receipt.effect_status in {EffectStatus.UNKNOWN, EffectStatus.PENDING}:
                uncertain.append(receipt.receipt_id)
        return confirmed, uncertain

    def lose_host(self, host_id: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
        self.heartbeat(host_id, status="offline")
        moment = (now or datetime.now(UTC)).astimezone(UTC)
        affected = []
        with transaction(self._connect(), immediate=True) as conn:
            rows = conn.execute(
                "SELECT assignment_id FROM fleet_assignments WHERE host_id = ? AND status = 'active'",
                (host_id,)).fetchall()
            conn.execute(
                "UPDATE fleet_assignments SET status = 'host_lost', updated_at = ? WHERE host_id = ? AND status = 'active'",
                (moment.isoformat(), host_id))
        for row in rows:
            assignment = self.assignment(row["assignment_id"])
            lease = self.leases.get(assignment["mission_id"], assignment["lease_id"])
            if lease.status in {LeaseStatus.ACTIVE, LeaseStatus.CLAIMED}:
                expired = replace(lease, status=LeaseStatus.EXPIRED, heartbeat_at=moment.isoformat())
                self.missions.record_lease(
                    expired, idempotency_key=f"fleet-host-lost:{lease.lease_id}:{moment.isoformat()}")
            affected.append(assignment)
        return affected

    def reclaim(self, assignment_id: str) -> dict[str, Any]:
        previous = self.assignment(assignment_id)
        confirmed, uncertain = self._receipt_state(previous["mission_id"], previous["task_id"])
        if uncertain:
            return {
                "status": "reconcile_required", "assignment_id": assignment_id,
                "uncertain_receipt_ids": uncertain, "confirmed_receipt_ids": confirmed,
            }
        replacement = self.assign(
            previous["mission_id"], previous["task_id"], previous["required_capabilities"],
            exclude_hosts=[previous["host_id"]])
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "UPDATE fleet_handoffs SET to_host = ?, status = 'assigned' WHERE mission_id = ? AND task_id = ? AND status = 'ready'",
                (replacement["host_id"], previous["mission_id"], previous["task_id"]))
        return {
            "status": "reassigned", "previous_assignment_id": assignment_id,
            "replacement": replacement, "confirmed_receipt_ids_to_skip": confirmed,
        }

    def status(self) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            assignments = [dict(row) for row in conn.execute(
                "SELECT * FROM fleet_assignments ORDER BY created_at").fetchall()]
        return {"hosts": self.hosts(), "assignments": assignments}


FLEET_STATUS_SCHEMA = {
    "name": "nara_fleet_status",
    "description": "Inspect fleet hosts, capabilities, heartbeats, assignments, and recovery state.",
    "parameters": {"type": "object", "properties": {}},
}


def fleet_status_tool(**_: Any) -> dict[str, Any]:
    return FleetCoordinator.open_default().status()
