"""Durable worker leases projected into the owning mission."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from plugins.mission_control.contracts import LeaseStatus, WorkerLease, load_contract, utc_now
from plugins.mission_control.store import MissionNotFoundError, MissionStore, MissionStoreError


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


class WorkerLeaseService:
    def __init__(self, missions: MissionStore):
        self.missions = missions

    def leases(self, mission_id: str) -> list[WorkerLease]:
        mission = self.missions.get(mission_id)
        if mission is None:
            raise MissionNotFoundError(mission_id)
        result = []
        for payload in mission.leases.values():
            lease = load_contract(payload)
            if isinstance(lease, WorkerLease):
                result.append(lease)
        return result

    def claim(
        self,
        mission_id: str,
        task_id: str,
        worker_id: str,
        *,
        ttl_seconds: int = 300,
        lease_id: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        now: datetime | None = None,
    ) -> WorkerLease:
        current_time = (now or datetime.now(UTC)).astimezone(UTC)
        self.expire(mission_id, now=current_time)
        for existing in self.leases(mission_id):
            if existing.task_id == task_id and existing.status in {LeaseStatus.CLAIMED, LeaseStatus.ACTIVE}:
                if existing.worker_id == worker_id:
                    return existing
                raise MissionStoreError(f"task {task_id} already has active lease {existing.lease_id}")
        lease = WorkerLease(
            lease_id=lease_id or uuid.uuid4().hex,
            mission_id=mission_id,
            task_id=task_id,
            worker_id=worker_id,
            status=LeaseStatus.ACTIVE,
            claimed_at=current_time.isoformat(),
            heartbeat_at=current_time.isoformat(),
            expires_at=(current_time + timedelta(seconds=max(1, ttl_seconds))).isoformat(),
            model=model,
            provider=provider,
        )
        self.missions.record_lease(lease, idempotency_key=f"lease-claim:{lease.lease_id}")
        return lease

    def get(self, mission_id: str, lease_id: str) -> WorkerLease:
        lease = next((item for item in self.leases(mission_id) if item.lease_id == lease_id), None)
        if lease is None:
            raise MissionStoreError(f"unknown worker lease: {lease_id}")
        return lease

    def heartbeat(
        self,
        mission_id: str,
        lease_id: str,
        *,
        ttl_seconds: int = 300,
        now: datetime | None = None,
    ) -> WorkerLease:
        lease = self.get(mission_id, lease_id)
        if lease.status is not LeaseStatus.ACTIVE:
            raise MissionStoreError(f"cannot heartbeat {lease.status.value} lease")
        current_time = (now or datetime.now(UTC)).astimezone(UTC)
        if _parse(lease.expires_at) <= current_time:
            self.expire(mission_id, now=current_time)
            raise MissionStoreError("cannot heartbeat an expired lease")
        updated = replace(
            lease,
            heartbeat_at=current_time.isoformat(),
            expires_at=(current_time + timedelta(seconds=max(1, ttl_seconds))).isoformat(),
        )
        self.missions.record_lease(
            updated, idempotency_key=f"lease-heartbeat:{lease_id}:{updated.heartbeat_at}")
        return updated

    def release(
        self,
        mission_id: str,
        lease_id: str,
        *,
        status: LeaseStatus | str = LeaseStatus.RELEASED,
    ) -> WorkerLease:
        lease = self.get(mission_id, lease_id)
        target = LeaseStatus(status)
        if target not in {LeaseStatus.RELEASED, LeaseStatus.CANCELLED}:
            raise MissionStoreError("release status must be released or cancelled")
        if lease.status in {LeaseStatus.RELEASED, LeaseStatus.CANCELLED}:
            return lease
        updated = replace(lease, status=target, heartbeat_at=utc_now())
        self.missions.record_lease(
            updated, idempotency_key=f"lease-terminal:{lease_id}:{target.value}")
        return updated

    def expire(self, mission_id: str, *, now: datetime | None = None) -> list[WorkerLease]:
        current_time = (now or datetime.now(UTC)).astimezone(UTC)
        expired = []
        for lease in self.leases(mission_id):
            if (
                lease.status in {LeaseStatus.CLAIMED, LeaseStatus.ACTIVE}
                and _parse(lease.expires_at) <= current_time
            ):
                updated = replace(lease, status=LeaseStatus.EXPIRED, heartbeat_at=current_time.isoformat())
                self.missions.record_lease(
                    updated, idempotency_key=f"lease-expired:{lease.lease_id}:{lease.expires_at}")
                expired.append(updated)
        return expired


def claim_from_kanban(
    *, task_id: str, assignee: str, run_id: int | None = None, store: MissionStore | None = None,
    **_: object,
) -> None:
    missions = store or MissionStore.open_default()
    mission = missions.mission_for_task(task_id)
    if mission is None:
        return
    WorkerLeaseService(missions).claim(
        mission.mission_id,
        task_id,
        assignee or "kanban-worker",
        lease_id=f"kanban:{task_id}:{run_id if run_id is not None else 'no-run'}",
    )


def release_from_kanban(
    *, task_id: str, run_id: int | None = None, store: MissionStore | None = None, **_: object,
) -> None:
    missions = store or MissionStore.open_default()
    mission = missions.mission_for_task(task_id)
    if mission is None:
        return
    lease_id = f"kanban:{task_id}:{run_id if run_id is not None else 'no-run'}"
    service = WorkerLeaseService(missions)
    try:
        service.release(mission.mission_id, lease_id)
    except MissionStoreError:
        return


def expire_from_kanban(
    *, task_id: str, run_id: int | None = None, store: MissionStore | None = None, **_: object,
) -> None:
    missions = store or MissionStore.open_default()
    mission = missions.mission_for_task(task_id)
    if mission is None:
        return
    lease_id = f"kanban:{task_id}:{run_id if run_id is not None else 'no-run'}"
    service = WorkerLeaseService(missions)
    try:
        lease = service.get(mission.mission_id, lease_id)
    except MissionStoreError:
        return
    if lease.status in {LeaseStatus.ACTIVE, LeaseStatus.CLAIMED}:
        updated = replace(lease, status=LeaseStatus.EXPIRED, heartbeat_at=utc_now())
        missions.record_lease(
            updated, idempotency_key=f"lease-stale:{lease_id}:{updated.heartbeat_at}")
