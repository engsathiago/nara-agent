"""Phase-6 local fixture: worker death, artifact handoff, lease reclaim, no repeated effect."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Sequence

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.contracts import Mission, Receipt
from plugins.mission_control.fleet import FleetCoordinator
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.verification import VerificationService


CRASH_EXIT = 87


def _host_a(partial: Path, effect_counter: Path) -> int:
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text("handoff-from-host-a", encoding="utf-8")
    count = int(effect_counter.read_text()) if effect_counter.exists() else 0
    effect_counter.write_text(str(count + 1), encoding="utf-8")
    return CRASH_EXIT


def _host_b(partial: Path, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(partial.read_text(encoding="utf-8") + "\ncompleted-on-host-b\n", encoding="utf-8")
    return 0


def run_fixture(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    missions = MissionStore(root / "missions.db")
    mission_id, task_id = "fleet-failover-v1", "remote-task"
    criterion = "host-b output includes the recovered host-a handoff"
    missions.create(Mission(
        mission_id=mission_id, objective="Resume a remote task after worker loss",
        completion_criteria=[criterion]))
    missions.transition(mission_id, "planned")
    missions.transition(mission_id, "running")
    missions.request_task(mission_id, task_id, {"title": "remote failover"})
    missions.link_task(mission_id, task_id, task_id, "todo")
    fleet = FleetCoordinator(root / "fleet", missions)
    fleet.register_host("host-a", "local://a", "darwin-arm64", ["terminal", "files"])
    fleet.register_host("host-b", "local://b", "darwin-arm64", ["terminal", "files"])
    assignment = fleet.assign(mission_id, task_id, ["terminal", "files"], ttl_seconds=30)
    receipts = ReceiptStore(missions)
    effect = receipts.prepare(Receipt(
        receipt_id="external-effect", mission_id=mission_id, task_id=task_id,
        intention="apply external effect exactly once", agent_id="host-a", tool="fixture.effect",
        target="counter", idempotency_key="external-effect-once"))
    partial = root / "host-a" / "partial.txt"
    counter = root / "effect-count.txt"
    child_a = subprocess.run([
        sys.executable, "-m", "evals.fleet_failover.run_fixture", "--host-a",
        str(partial), str(counter)], cwd=Path(__file__).resolve().parents[2], check=False)
    if child_a.returncode != CRASH_EXIT:
        raise RuntimeError(f"host-a returned {child_a.returncode}")
    receipts.settle(
        mission_id, effect.receipt_id, "confirmed", observed_result={"count": 1},
        idempotency_key="external-effect-observed")
    handoff = fleet.put_handoff(
        mission_id, task_id, "partial:host-a", partial.read_bytes(), from_host="host-a")
    fleet.lose_host("host-a", now=datetime.now(UTC) + timedelta(seconds=31))
    reclaim = fleet.reclaim(assignment["assignment_id"])
    if reclaim["status"] != "reassigned" or reclaim["confirmed_receipt_ids_to_skip"] != [effect.receipt_id]:
        raise RuntimeError("fleet did not preserve the confirmed-effect skip contract")
    handoff_row = fleet.handoff(handoff["handoff_id"])
    output = root / "host-b" / "result.txt"
    child_b = subprocess.run([
        sys.executable, "-m", "evals.fleet_failover.run_fixture", "--host-b",
        handoff_row["stored_path"], str(output)], cwd=Path(__file__).resolve().parents[2], check=False)
    if child_b.returncode != 0:
        raise RuntimeError(f"host-b returned {child_b.returncode}")
    artifacts = ArtifactStore(missions, root / "artifacts")
    result_artifact = artifacts.put_file(
        mission_id, output, producer_id="host-b", media_type="text/plain")
    VerificationService(missions, artifacts).verify_artifact(
        mission_id, criterion, result_artifact.artifact_id,
        verifier_id="fleet-judge", executor_id="host-b", verification_id="fleet-output-proof")
    missions.record_task_status(task_id, "done", idempotency_key="fleet-task-done")
    missions.transition(mission_id, "verifying")
    completed = missions.transition(mission_id, "completed")
    effect_count = int(counter.read_text())
    if effect_count != 1:
        raise RuntimeError(f"confirmed external effect repeated {effect_count} times")
    return {
        "schema_version": 1, "fixture_id": "phase6-local-fleet-failover-v1", "status": "passed",
        "mission_status": completed.status.value, "host_a_exit": child_a.returncode,
        "host_b_exit": child_b.returncode, "effect_count": effect_count,
        "initial_host": assignment["host_id"], "replacement_host": reclaim["replacement"]["host_id"],
        "skip_receipt_ids": reclaim["confirmed_receipt_ids_to_skip"],
        "handoff_hash": handoff_row["content_hash"], "result_artifact_id": result_artifact.artifact_id,
        "artifact_verified": artifacts.verify(mission_id, result_artifact.artifact_id),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--host-a", nargs=2, metavar=("PARTIAL", "COUNTER"))
    parser.add_argument("--host-b", nargs=2, metavar=("PARTIAL", "OUTPUT"))
    args = parser.parse_args(argv)
    if args.host_a:
        return _host_a(Path(args.host_a[0]), Path(args.host_a[1]))
    if args.host_b:
        return _host_b(Path(args.host_b[0]), Path(args.host_b[1]))
    if args.root is None:
        raise SystemExit("--root is required")
    result = run_fixture(args.root)
    serialized = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
