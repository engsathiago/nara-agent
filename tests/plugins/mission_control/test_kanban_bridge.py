from __future__ import annotations

import json

import pytest

from plugins.mission_control.contracts import Mission
from plugins.mission_control.kanban_bridge import create_mission_task, sync_task_status
from plugins.mission_control.store import MissionStore, MissionStoreError


def _store(tmp_path) -> MissionStore:
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-1", objective="Build report", completion_criteria=["report exists"],
    ))
    return store


def test_bridge_persists_intent_then_links_public_kanban_result(tmp_path):
    store = _store(tmp_path)
    observed = []

    def dispatch(name, args):
        observed.append((name, args, store.get("mission-1").task_requests["research"]["status"]))
        return json.dumps({"ok": True, "task_id": "task-1", "status": "ready"})

    result = create_mission_task(
        store, dispatch, mission_id="mission-1", request_key="research", title="Research",
        assignee="sol", body="Find sources",
    )

    assert result["task_id"] == "task-1"
    assert observed[0][0] == "kanban_create"
    assert observed[0][1]["idempotency_key"] == "mission:mission-1:task:research"
    assert observed[0][2] == "requested"
    assert store.get("mission-1").task_states == {"task-1": "ready"}


def test_retry_after_unknown_result_reuses_request_and_kanban_key(tmp_path):
    store = _store(tmp_path)
    calls = []

    def dispatch(name, args):
        calls.append(args["idempotency_key"])
        if len(calls) == 1:
            return "not-json"
        return json.dumps({"ok": True, "task_id": "task-1", "status": "ready"})

    with pytest.raises(MissionStoreError, match="non-JSON"):
        create_mission_task(
            store, dispatch, mission_id="mission-1", request_key="research", title="Research",
            assignee="sol",
        )
    create_mission_task(
        store, dispatch, mission_id="mission-1", request_key="research", title="Research",
        assignee="sol",
    )

    assert calls == ["mission:mission-1:task:research"] * 2
    assert [event.event_type for event in store.events("mission-1")].count("mission.task_requested") == 1


def test_lifecycle_hook_updates_only_a_linked_task(tmp_path):
    store = _store(tmp_path)
    store.request_task("mission-1", "research", {"title": "Research"})
    store.link_task("mission-1", "research", "task-1", "running")

    sync_task_status(task_id="task-1", status="done", run_id=7, store=store)
    sync_task_status(task_id="unrelated", status="done", run_id=8, store=store)

    assert store.get("mission-1").task_states == {"task-1": "done"}
