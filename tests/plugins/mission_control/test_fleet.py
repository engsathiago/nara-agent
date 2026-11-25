from __future__ import annotations

from datetime import UTC, datetime, timedelta

from plugins.mission_control.contracts import Mission, Receipt
from plugins.mission_control.fleet import FleetCoordinator
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.workers import WorkerLeaseService


def _fleet(tmp_path):
    missions = MissionStore(tmp_path / "missions.db")
    missions.create(Mission(
        mission_id="mission-a", objective="remote work", completion_criteria=["work verified"]))
    missions.request_task("mission-a", "remote", {"title": "remote"})
    missions.link_task("mission-a", "remote", "task-a", "todo")
    fleet = FleetCoordinator(tmp_path / "fleet", missions)
    fleet.register_host("host-a", "ssh://a", "linux-arm64", ["terminal", "python"])
    fleet.register_host("host-b", "ssh://b", "linux-x86_64", ["terminal", "python", "browser"])
    return missions, fleet


def test_host_loss_reassigns_lease_and_preserves_handoff(tmp_path):
    missions, fleet = _fleet(tmp_path)
    assignment = fleet.assign("mission-a", "task-a", ["terminal", "python"], ttl_seconds=30)
    handoff = fleet.put_handoff(
        "mission-a", "task-a", "sha256:partial", b"partial-state", from_host="host-a")
    future = datetime.now(UTC) + timedelta(seconds=31)
    fleet.lose_host("host-a", now=future)
    result = fleet.reclaim(assignment["assignment_id"])

    assert result["status"] == "reassigned"
    assert result["replacement"]["host_id"] == "host-b"
    assert fleet.handoff(handoff["handoff_id"])["to_host"] == "host-b"
    assert fleet.host("host-a")["status"] == "offline"
    assert len([
        lease for lease in WorkerLeaseService(missions).leases("mission-a")
        if lease.status.value == "active"
    ]) == 1


def test_uncertain_effect_blocks_reassignment_but_confirmed_is_skip_list(tmp_path):
    missions, fleet = _fleet(tmp_path)
    assignment = fleet.assign("mission-a", "task-a", ["terminal"])
    receipts = ReceiptStore(missions)
    receipts.prepare(Receipt(
        receipt_id="confirmed", mission_id="mission-a", task_id="task-a", intention="write once",
        agent_id="host-a", tool="api.write", target="record", idempotency_key="write"))
    receipts.settle("mission-a", "confirmed", "confirmed", idempotency_key="write-done")
    receipts.prepare(Receipt(
        receipt_id="unknown", mission_id="mission-a", task_id="task-a", intention="publish",
        agent_id="host-a", tool="api.publish", target="post", idempotency_key="publish"))
    receipts.settle("mission-a", "unknown", "unknown", idempotency_key="publish-unknown")
    fleet.lose_host("host-a")

    result = fleet.reclaim(assignment["assignment_id"])

    assert result["status"] == "reconcile_required"
    assert result["uncertain_receipt_ids"] == ["unknown"]
    assert result["confirmed_receipt_ids"] == ["confirmed"]


def test_incompatible_environment_is_explicit(tmp_path):
    _missions, fleet = _fleet(tmp_path)

    try:
        fleet.select_host(["cuda"])
    except ValueError as exc:
        assert "cuda" in str(exc)
    else:
        raise AssertionError("missing fleet capability should not silently schedule")
