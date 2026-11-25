from __future__ import annotations

from datetime import UTC, datetime, timedelta

from plugins.mission_control.contracts import Mission, Receipt
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.supervisor import MissionSupervisor


def test_supervisor_exposes_unknown_effect_without_retrying(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-1", objective="publish", completion_criteria=["published"],
    ))
    receipts = ReceiptStore(store)
    receipts.prepare(Receipt(
        receipt_id="r1", mission_id="mission-1", task_id="t1", intention="publish",
        agent_id="w1", tool="api.publish", target="post-1", idempotency_key="publish-1",
    ))
    receipts.settle("mission-1", "r1", "unknown", idempotency_key="uncertain")

    competence = CompetenceRegistry(tmp_path / "competence.db")
    result = MissionSupervisor(store, competence).diagnose("mission-1", stale_after_seconds=9999)

    assert result["status"] == "attention"
    assert result["issues"][0]["code"] == "effect_unknown"
    assert "before retry" in result["issues"][0]["next_action"]
    assert store.get("mission-1").diagnostics[result["diagnostic_id"]]["status"] == "attention"
    assert competence.gaps()[0]["category"] == "mission.effect_unknown"


def test_supervisor_detects_no_progress_from_durable_timestamp(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    mission = store.create(Mission(
        mission_id="mission-1", objective="publish", completion_criteria=["published"],
        updated_at="2026-01-01T00:00:00+00:00",
    ))
    now = datetime.fromisoformat(mission.updated_at) + timedelta(hours=1)

    result = MissionSupervisor(store).diagnose(
        "mission-1", stale_after_seconds=60, now=now.astimezone(UTC))

    assert any(issue["code"] == "no_progress" for issue in result["issues"])
