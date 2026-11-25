from __future__ import annotations

from plugins.mission_control import goal_bridge
from plugins.mission_control.contracts import Mission
from plugins.mission_control.store import MissionStore


def test_mission_contract_is_projected_into_existing_goal_runtime(tmp_path, monkeypatch):
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-1",
        objective="Produce report",
        completion_criteria=["report exists", "tests pass"],
    ))
    saved = {}
    monkeypatch.setattr(goal_bridge, "load_goal", lambda session_id: None)
    monkeypatch.setattr(goal_bridge, "save_goal", lambda session_id, state: saved.update({session_id: state}))

    state = goal_bridge.bind_mission_goal(store, "mission-1", "session-1")

    assert state.goal == "Produce report"
    assert state.subgoals == ["report exists", "tests pass"]
    assert saved["session-1"] is state
    assert store.get("mission-1").goal_ref["authority"] == "mission_control"
