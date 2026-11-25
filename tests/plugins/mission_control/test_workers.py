from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from plugins.mission_control.contracts import LeaseStatus, Mission
from plugins.mission_control.store import MissionStore, MissionStoreError
from plugins.mission_control.workers import WorkerLeaseService, claim_from_kanban, release_from_kanban


def _store(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-1", objective="build", completion_criteria=["built"],
    ))
    store.request_task("mission-1", "build", {"title": "build"})
    store.link_task("mission-1", "build", "task-1", "todo")
    return store


def test_only_one_live_worker_can_hold_a_task_lease(tmp_path):
    store = _store(tmp_path)
    service = WorkerLeaseService(store)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    lease = service.claim(
        "mission-1", "task-1", "worker-1", lease_id="lease-1", now=now)

    with pytest.raises(MissionStoreError, match="already has active lease"):
        service.claim("mission-1", "task-1", "worker-2", lease_id="lease-2", now=now)

    assert lease.status is LeaseStatus.ACTIVE


def test_expired_lease_can_be_reclaimed_once(tmp_path):
    store = _store(tmp_path)
    service = WorkerLeaseService(store)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    first = service.claim(
        "mission-1", "task-1", "worker-1", lease_id="lease-1", ttl_seconds=10, now=now)
    second = service.claim(
        "mission-1", "task-1", "worker-2", lease_id="lease-2",
        now=now + timedelta(seconds=11),
    )

    assert service.get("mission-1", first.lease_id).status is LeaseStatus.EXPIRED
    assert second.status is LeaseStatus.ACTIVE


def test_kanban_hooks_project_claim_and_release(tmp_path):
    store = _store(tmp_path)

    claim_from_kanban(task_id="task-1", assignee="worker-1", run_id=7, store=store)
    lease = WorkerLeaseService(store).get("mission-1", "kanban:task-1:7")
    release_from_kanban(task_id="task-1", run_id=7, store=store)

    assert lease.worker_id == "worker-1"
    assert WorkerLeaseService(store).get("mission-1", lease.lease_id).status is LeaseStatus.RELEASED
