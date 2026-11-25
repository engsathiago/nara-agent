"""WP-05 vertical continuity fixture with a real process crash and restart.

The worker process applies a file effect and exits before it can settle its
receipt.  A fresh coordinator process view then reconciles by hash, stores the
artifact, observes it through a controlled browser probe, verifies the evidence
independently, and crosses the completion gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.contracts import (
    EffectStatus,
    Mission,
    Receipt,
    Verification,
    VerificationStatus,
)
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.verification import VerificationService


FAULT_EXIT = 86
REPORT_CONTENT = b"<html><body><main data-status='complete'>Nara continuity report</main></body></html>"


class _CompletionMarkerParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.complete = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "main" and dict(attrs).get("data-status") == "complete":
            self.complete = True


def _effect_worker(target: Path, counter: Path, content_hex: str) -> int:
    """Apply an idempotent file effect, then emulate an ungraceful worker death."""
    content = bytes.fromhex(content_hex)
    expected = hashlib.sha256(content).hexdigest()
    if target.exists():
        observed = hashlib.sha256(target.read_bytes()).hexdigest()
        if observed != expected:
            return 2
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        count = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
        counter.write_text(str(count + 1), encoding="utf-8")
    return FAULT_EXIT


def _observe_page(path: Path) -> dict[str, object]:
    parser = _CompletionMarkerParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return {"url": path.as_uri(), "completion_marker": parser.complete}


def run_fixture(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    db_path = root / "missions.db"
    target = root / "workspace" / "report.html"
    counter = root / "effect-count.txt"
    mission_id = "continuity-file-effect-v1"
    expected_hash = hashlib.sha256(REPORT_CONTENT).hexdigest()

    missions = MissionStore(db_path)
    mission = Mission(
        mission_id=mission_id,
        objective="Survive a worker crash and deliver a verified report",
        completion_criteria=[
            "report bytes match the expected SHA-256",
            "controlled browser observes the completion marker",
        ],
        runtime_version="wp05-v1",
    )
    missions.create(mission, actor_id="fixture", idempotency_key="fixture:create")
    missions.transition(mission_id, "planned", idempotency_key="fixture:planned")
    missions.transition(mission_id, "running", idempotency_key="fixture:running")

    receipts = ReceiptStore(missions)
    file_receipt = receipts.prepare(Receipt(
        receipt_id="file-effect",
        mission_id=mission_id,
        task_id="worker-file-task",
        intention="write the continuity report exactly once",
        agent_id="worker-process-1",
        tool="file.write",
        target=str(target),
        idempotency_key="continuity:report:v1",
    ))

    worker = subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.mission_continuity.run_fixture",
            "--effect-worker",
            str(target),
            str(counter),
            REPORT_CONTENT.hex(),
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
    )
    if worker.returncode != FAULT_EXIT:
        raise RuntimeError(f"fault worker exited {worker.returncode}, expected {FAULT_EXIT}")

    # Fresh service objects are the restart boundary.  No in-memory mission state
    # from before the worker death is reused below this line.
    missions = MissionStore(db_path)
    receipts = ReceiptStore(missions)
    reconstructed = missions.reconstruct(mission_id)
    if receipts.get(mission_id, file_receipt.receipt_id).effect_status is not EffectStatus.PENDING:
        raise RuntimeError("crash boundary did not preserve a pending effect")
    observed_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    if observed_hash != expected_hash:
        raise RuntimeError("reconciliation found unexpected report bytes")
    receipts.settle(
        mission_id,
        file_receipt.receipt_id,
        EffectStatus.CONFIRMED,
        observed_result={"sha256": observed_hash, "reconciled_after_restart": True},
        idempotency_key="fixture:file-reconciled",
    )

    artifacts = ArtifactStore(missions, root / "artifacts")
    report = artifacts.put_file(
        mission_id,
        target,
        producer_id="worker-process-1",
        media_type="text/html",
        metadata={"fixture": "continuity-file-effect-v1"},
    )
    browser_receipt = receipts.prepare(Receipt(
        receipt_id="browser-observation",
        mission_id=mission_id,
        task_id="browser-probe-task",
        intention="observe the completion marker through a controlled browser probe",
        agent_id="browser-worker-1",
        tool="browser.controlled.open",
        target=target.as_uri(),
        idempotency_key="continuity:browser:v1",
    ))
    browser_observation = _observe_page(target)
    receipts.settle(
        mission_id,
        browser_receipt.receipt_id,
        EffectStatus.CONFIRMED if browser_observation["completion_marker"] else EffectStatus.FAILED,
        observed_result=browser_observation,
        artifact_ids=[report.artifact_id],
        idempotency_key="fixture:browser-observed",
    )

    verifier = VerificationService(missions, artifacts)
    verifier.verify_artifact(
        mission_id,
        "report bytes match the expected SHA-256",
        report.artifact_id,
        verifier_id="independent-judge-1",
        executor_id="worker-process-1",
        verification_id="verify-report-hash",
    )
    evidence_parser = _CompletionMarkerParser()
    evidence_parser.feed(artifacts.read_bytes(mission_id, report.artifact_id).decode("utf-8"))
    verifier.record(Verification(
        verification_id="verify-browser-evidence",
        mission_id=mission_id,
        criterion="controlled browser observes the completion marker",
        verifier_id="independent-judge-1",
        executor_id="browser-worker-1",
        status=(VerificationStatus.PASS if evidence_parser.complete else VerificationStatus.FAIL),
        evidence_artifact_ids=[report.artifact_id],
        method="reopen content-addressed HTML and parse data-status marker",
        explanation="independent parser observed the completion marker",
    ))
    missions.transition(mission_id, "verifying", idempotency_key="fixture:verifying")
    completed = missions.transition(mission_id, "completed", idempotency_key="fixture:completed")
    effect_count = int(counter.read_text(encoding="utf-8"))
    if effect_count != 1:
        raise RuntimeError(f"file effect occurred {effect_count} times")

    return {
        "schema_version": 1,
        "fixture_id": "continuity-file-effect-v1",
        "status": "passed",
        "mission_id": mission_id,
        "mission_status": completed.status.value,
        "reconstructed_version": reconstructed.version,
        "effect_count": effect_count,
        "fault_exit_code": worker.returncode,
        "receipt_status": receipts.get(mission_id, file_receipt.receipt_id).effect_status.value,
        "artifact_id": report.artifact_id,
        "artifact_verified": artifacts.verify(mission_id, report.artifact_id),
        "browser_observation": browser_observation,
        "completion_blockers": verifier.blockers(mission_id),
        "event_count": len(missions.events(mission_id)),
        "run_id": uuid.uuid4().hex,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Nara WP-05 continuity fixture")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--effect-worker", nargs=3, metavar=("TARGET", "COUNTER", "CONTENT_HEX"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.effect_worker:
        target, counter, content_hex = args.effect_worker
        return _effect_worker(Path(target), Path(counter), content_hex)
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
