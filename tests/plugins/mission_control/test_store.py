from __future__ import annotations

import json
import sqlite3

import pytest

from plugins.mission_control.contracts import ContractError, Mission, MissionStatus
from plugins.mission_control.store import IdempotencyConflictError, MissionStore


def _mission(mission_id: str = "mission-1") -> Mission:
    return Mission(
        mission_id=mission_id,
        objective="Create a verified report",
        completion_criteria=["report exists", "hash matches"],
    )


def test_event_log_and_projection_survive_new_store_instance(tmp_path):
    path = tmp_path / "missions.db"
    first = MissionStore(path)
    first.create(_mission(), idempotency_key="create-1")
    first.transition("mission-1", MissionStatus.PLANNED, idempotency_key="plan-1")

    restarted = MissionStore(path)

    assert restarted.get("mission-1").status is MissionStatus.PLANNED
    assert [event.sequence for event in restarted.events("mission-1")] == [1, 2]
    assert restarted.verify_projection("mission-1") is True


def test_idempotent_transition_does_not_append_or_increment_twice(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(_mission())

    first = store.transition("mission-1", "planned", reason="ready", idempotency_key="plan-1")
    replay = store.transition("mission-1", "planned", reason="ready", idempotency_key="plan-1")

    assert replay == first
    assert replay.version == 2
    assert len(store.events("mission-1")) == 2


def test_reusing_idempotency_key_for_different_payload_is_rejected(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(_mission())
    store.transition("mission-1", "planned", reason="ready", idempotency_key="same")

    with pytest.raises(IdempotencyConflictError):
        store.transition("mission-1", "planned", reason="different", idempotency_key="same")


def test_invalid_transition_rolls_back_without_event(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(_mission())

    with pytest.raises(ContractError, match="draft -> completed"):
        store.transition("mission-1", "completed")

    assert store.get("mission-1").status is MissionStatus.DRAFT
    assert len(store.events("mission-1")) == 1


def test_projection_can_be_rebuilt_from_immutable_events(tmp_path):
    path = tmp_path / "missions.db"
    store = MissionStore(path)
    store.create(_mission())
    store.transition("mission-1", "planned")
    store.transition("mission-1", "running")

    conn = sqlite3.connect(path)
    payload = _mission().to_dict()
    conn.execute(
        "UPDATE missions SET projection_json = ? WHERE mission_id = ?",
        (json.dumps(payload), "mission-1"),
    )
    conn.commit()
    conn.close()

    assert store.verify_projection("mission-1") is False
    rebuilt = store.rebuild_projection("mission-1")
    assert rebuilt.status is MissionStatus.RUNNING
    assert rebuilt.version == 3
    assert store.verify_projection("mission-1") is True


def test_task_request_is_persisted_before_link_and_reconstructs(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(_mission())

    requested = store.request_task("mission-1", "research", {"title": "Research", "assignee": "sol"})
    linked = store.link_task("mission-1", "research", "task-123", "ready")
    completed = store.record_task_status(
        "task-123", "done", idempotency_key="kanban:task-123:1:done",
    )

    assert requested.task_requests["research"]["status"] == "requested"
    assert linked.task_requests["research"] == {"status": "linked", "task_id": "task-123",
                                                   "spec": {"title": "Research", "assignee": "sol"}}
    assert completed.task_states == {"task-123": "done"}
    assert store.reconstruct("mission-1") == completed



def test_first_open_tolerates_a_transient_wal_activation_lock(tmp_path, monkeypatch):
    import nara_state_wal

    activate = nara_state_wal.apply_wal_with_fallback
    attempts = []

    def contested(conn, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise sqlite3.OperationalError("database is locked")
        return activate(conn, **kwargs)

    monkeypatch.setattr(nara_state_wal, "apply_wal_with_fallback", contested)
    store = MissionStore(tmp_path / "first-open.db")
    store.create(_mission())
    assert store.get("mission-1").objective == "Create a verified report"
    assert store.verify_projection("mission-1")
