"""Phase-2 fixture: recover, learn, transfer in a fresh session, and correct memory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from evals.mission_continuity.run_fixture import run_fixture as run_continuity_fixture
from extensions.nara_temporal_memory.nara_temporal import (
    NaraTemporalMemoryProvider,
    TemporalMemoryStore,
)
from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.contracts import Mission, Receipt
from plugins.mission_control.learning import LearningLab, ProcedureCandidate
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.verification import VerificationService


def _execute_transfer_case(
    procedure: ProcedureCandidate | None,
    case: dict[str, object],
    root: Path,
) -> float:
    """Run the same unseen file task with or without the learned procedure.

    Both arms produce the requested file.  The learned arm additionally follows
    the recovered evidence-retention step.  Scoring reopens the outputs instead
    of trusting the runner's return value.
    """
    target = root / str(case["case_id"]) / "result.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = str(case["payload"]).encode()
    target.write_bytes(payload)
    procedure_text = " ".join(procedure.steps).casefold() if procedure else ""
    if "retain the evidence artifact" in procedure_text:
        target.with_suffix(".sha256").write_text(
            hashlib.sha256(payload).hexdigest() + "\n", encoding="utf-8")
    score = 0.5 if target.read_bytes() == payload else 0.0
    evidence = target.with_suffix(".sha256")
    if evidence.exists() and evidence.read_text(encoding="utf-8").strip() == hashlib.sha256(payload).hexdigest():
        score += 0.5
    return score


def _complete_transfer_mission(
    root: Path,
    candidate: ProcedureCandidate,
    recalled_context: str,
) -> dict[str, object]:
    missions = MissionStore(root / "session-b" / "missions.db")
    mission_id = "transfer-report-v1"
    criterion = "new report bytes are preserved and independently verified"
    missions.create(Mission(
        mission_id=mission_id,
        objective="Apply a recovered procedure to a different report in a new session",
        completion_criteria=[criterion],
        session_id="fresh-session-b",
    ))
    missions.transition(mission_id, "planned")
    missions.transition(mission_id, "running")
    target = root / "session-b" / "workspace" / "different-report.txt"
    score = _execute_transfer_case(
        candidate,
        {"case_id": "mission-b", "payload": "A different Nara transfer report"},
        target.parent,
    )
    produced = target.parent / "mission-b" / "result.txt"
    receipts = ReceiptStore(missions)
    receipt = receipts.prepare(Receipt(
        receipt_id="transfer-write",
        mission_id=mission_id,
        task_id="transfer-task",
        intention="apply the learned evidence-preserving report procedure",
        agent_id="fresh-session-worker",
        tool="file.write",
        target=str(produced),
        idempotency_key="transfer-report-v1",
    ))
    artifacts = ArtifactStore(missions, root / "session-b" / "artifacts")
    artifact = artifacts.put_file(
        mission_id, produced, producer_id="fresh-session-worker", media_type="text/plain")
    receipts.settle(
        mission_id, receipt.receipt_id, "confirmed", artifact_ids=[artifact.artifact_id],
        observed_result={"transfer_score": score, "recalled_candidate": candidate.candidate_id},
        idempotency_key="transfer-report-confirmed",
    )
    VerificationService(missions, artifacts).verify_artifact(
        mission_id, criterion, artifact.artifact_id,
        verifier_id="fresh-session-judge", executor_id="fresh-session-worker",
        verification_id="transfer-report-verification",
    )
    missions.transition(mission_id, "verifying")
    completed = missions.transition(mission_id, "completed")
    return {
        "mission_id": mission_id,
        "mission_status": completed.status.value,
        "score": score,
        "artifact_id": artifact.artifact_id,
        "artifact_verified": artifacts.verify(mission_id, artifact.artifact_id),
        "memory_recalled": candidate.candidate_id in recalled_context,
    }


def run_fixture(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    continuity_root = root / "session-a"
    continuity = run_continuity_fixture(continuity_root)
    memory = TemporalMemoryStore(root / "profile" / "memories" / "nara-temporal.db")
    lab = LearningLab(
        MissionStore(continuity_root / "missions.db"),
        memory,
        root / "profile" / "learning" / "candidates",
        root / "profile" / "skills",
    )
    candidate = lab.extract(
        str(continuity["mission_id"]), name="recoverable evidence-preserving report")
    cases = [
        {"case_id": "development-sample", "payload": "development"},
        {"case_id": "holdout-invoice", "payload": "invoice bytes"},
        {"case_id": "holdout-audit", "payload": "audit bytes"},
        {"case_id": "holdout-portuguese", "payload": "relatório novo"},
    ]
    evaluation = lab.evaluate_transfer(
        candidate.candidate_id,
        cases,
        lambda procedure, case: _execute_transfer_case(
            procedure, case, root / "transfer-eval" / ("learned" if procedure else "baseline")),
        development_case_ids={"development-sample"},
    )
    skill_path = lab.promote(candidate.candidate_id)

    provider = NaraTemporalMemoryProvider()
    provider.initialize("fresh-session-b", nara_home=str(root / "profile"))
    recalled = provider.prefetch("recoverable report evidence verify", session_id="fresh-session-b")
    transfer = _complete_transfer_mission(root, candidate, recalled)

    old = memory.add(
        "The transfer workspace is session-a", layer="semantic", source_type="fixture",
        source_ref="phase2:old", status="active", confidence=1.0)
    correction = memory.add(
        "The transfer workspace is session-b", layer="semantic", source_type="operator_correction",
        source_ref="phase2:correction", status="candidate", confidence=1.0,
        supersedes_id=old["memory_id"])
    memory.promote(correction["memory_id"])
    current = memory.search("transfer workspace", include_history=False)
    history = memory.search("transfer workspace", include_history=True)

    if not evaluation["passed"] or evaluation["mean_delta"] <= 0:
        raise RuntimeError("reserved transfer evaluation did not improve over baseline")
    if not transfer["memory_recalled"] or transfer["mission_status"] != "completed":
        raise RuntimeError("fresh session did not recall and complete the transfer mission")
    if [item["content"] for item in current["items"]] != ["The transfer workspace is session-b"]:
        raise RuntimeError("temporal correction did not replace the current fact")

    return {
        "schema_version": 1,
        "fixture_id": "phase2-learning-transfer-v1",
        "status": "passed",
        "continuity": continuity,
        "candidate_id": candidate.candidate_id,
        "candidate_status": memory.get(f"procedure:{candidate.candidate_id}")["status"],
        "skill_path": str(skill_path),
        "transfer_evaluation": evaluation,
        "fresh_session": transfer,
        "correction": {
            "current": [item["content"] for item in current["items"]],
            "history_count": len(history["items"]),
            "old_valid_to": memory.get(old["memory_id"])["valid_to"],
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = run_fixture(args.root)
    serialized = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
