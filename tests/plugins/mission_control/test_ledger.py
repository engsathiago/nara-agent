from __future__ import annotations

from plugins.mission_control.contracts import Mission
from plugins.mission_control.ledger import ExperienceLedger
from plugins.mission_control.store import MissionStore


def test_ledger_builds_navigable_tree_without_full_result_content(tmp_path):
    missions = MissionStore(tmp_path / "missions.db")
    missions.create(Mission(
        mission_id="mission-1", objective="build", completion_criteria=["built"],
    ))
    missions.request_task("mission-1", "build", {"title": "build"})
    missions.link_task("mission-1", "build", "task-1", "running")
    ledger = ExperienceLedger(tmp_path / "ledger.db")
    ledger.record(
        event_id="tool-1",
        kind="tool.completed",
        mission_id="mission-1",
        task_id="task-1",
        session_id="session-1",
        turn_id="turn-1",
        agent_id="worker-1",
        status="ok",
        tool="terminal",
        duration_ms=25,
        payload={"result_sha256": "abc", "result_size_bytes": 50000},
    )

    tree = ledger.mission_tree(missions, "mission-1")

    assert tree["tasks"][0]["agents"] == ["worker-1"]
    assert tree["tasks"][0]["turns"] == ["turn-1"]
    assert tree["tasks"][0]["tools"][0]["payload"]["result_sha256"] == "abc"
    assert "result_content" not in tree["tasks"][0]["tools"][0]["payload"]
    assert tree["totals"]["duration_ms"] == 25


def test_ledger_event_ids_are_idempotent(tmp_path):
    ledger = ExperienceLedger(tmp_path / "ledger.db")
    common = {
        "event_id": "same", "kind": "tool.completed", "mission_id": "mission-1",
        "payload": {"result_sha256": "abc"},
    }

    ledger.record(**common)
    ledger.record(**common)

    assert len(ledger.events("mission-1")) == 1
