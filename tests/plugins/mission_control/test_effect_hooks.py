from __future__ import annotations

from plugins.mission_control import effect_hooks
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import Mission
from plugins.mission_control.ledger import ExperienceLedger
from plugins.mission_control.store import MissionStore


def _linked_store(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-1", objective="write report", completion_criteria=["report exists"],
    ))
    store.request_task("mission-1", "write", {"title": "write report"})
    store.link_task("mission-1", "write", "task-1", "todo")
    return store


def test_real_hook_pair_persists_and_settles_tool_receipt(tmp_path, monkeypatch):
    store = _linked_store(tmp_path)
    monkeypatch.setattr(MissionStore, "open_default", classmethod(lambda cls: store))
    ledger = ExperienceLedger(tmp_path / "ledger.db")
    monkeypatch.setattr(ExperienceLedger, "open_default", classmethod(lambda cls: ledger))

    effect_hooks.pre_tool_call(
        tool_name="write_file",
        args={"path": "/tmp/report.txt", "content": "done"},
        task_id="task-1",
        session_id="worker-1",
        tool_call_id="call-1",
    )
    pending = store.get("mission-1")
    receipt = next(iter(pending.receipts.values()))
    assert receipt["effect_status"] == "pending"

    effect_hooks.post_tool_call(
        tool_name="write_file",
        result={"status": "ok"},
        task_id="task-1",
        session_id="worker-1",
        tool_call_id="call-1",
        status="ok",
        duration_ms=12,
    )

    settled = store.get("mission-1")
    receipt = next(iter(settled.receipts.values()))
    assert receipt["effect_status"] == "confirmed"
    assert receipt["observed_result"]["duration_ms"] == 12
    assert [event["kind"] for event in ledger.events("mission-1")] == [
        "tool.started", "tool.completed",
    ]


def test_large_runtime_result_becomes_content_addressed_artifact(tmp_path, monkeypatch):
    store = _linked_store(tmp_path)
    monkeypatch.setattr(MissionStore, "open_default", classmethod(lambda cls: store))
    monkeypatch.setattr(effect_hooks, "LARGE_RESULT_BYTES", 8)
    monkeypatch.setattr(
        ExperienceLedger, "open_default", classmethod(lambda cls: ExperienceLedger(tmp_path / "ledger.db")))
    common = {
        "tool_name": "terminal",
        "task_id": "task-1",
        "session_id": "worker-1",
        "tool_call_id": "call-large",
    }

    effect_hooks.pre_tool_call(args={"command": "generate"}, **common)
    effect_hooks.post_tool_call(result="large tool output", status="ok", **common)

    mission = store.get("mission-1")
    receipt = next(iter(mission.receipts.values()))
    assert len(receipt["artifact_ids"]) == 1
    assert receipt["artifact_ids"][0] in mission.artifacts


def test_cancelled_runtime_effect_stays_unknown(tmp_path, monkeypatch):
    store = _linked_store(tmp_path)
    monkeypatch.setattr(MissionStore, "open_default", classmethod(lambda cls: store))
    monkeypatch.setattr(
        ExperienceLedger, "open_default", classmethod(lambda cls: ExperienceLedger(tmp_path / "ledger.db")))
    common = {
        "tool_name": "terminal",
        "task_id": "task-1",
        "session_id": "worker-1",
        "tool_call_id": "call-cancelled",
    }

    effect_hooks.pre_tool_call(args={"command": "external write"}, **common)
    effect_hooks.post_tool_call(
        result={"error": "interrupted"}, status="cancelled", error_type="interrupt", **common)

    receipt = next(iter(store.get("mission-1").receipts.values()))
    assert receipt["effect_status"] == "unknown"
    gap = CompetenceRegistry(tmp_path / "competence.db").gaps()[0]
    assert gap["category"] == "tool.terminal"
    assert gap["state"] == "open"


def test_effect_receipt_redacts_secret_targets(tmp_path, monkeypatch):
    store = _linked_store(tmp_path)
    monkeypatch.setattr(MissionStore, "open_default", classmethod(lambda cls: store))
    monkeypatch.setattr(
        ExperienceLedger, "open_default",
        classmethod(lambda cls: ExperienceLedger(tmp_path / "ledger.db")))

    effect_hooks.pre_tool_call(
        tool_name="terminal", args={"command": "API_KEY=super-secret run"},
        task_id="task-1", session_id="worker-1", tool_call_id="secret-call")

    receipt = next(iter(store.get("mission-1").receipts.values()))
    assert "super-secret" not in receipt["target"]
    assert "REDACTED" in receipt["target"]
