"""Phase-3 fixture: observed failure, study, practice, reserved proof, promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Callable, Sequence

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import Mission, Receipt
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.verification import VerificationService


def _archive(path: Path, members: dict[str, str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as handle:
        for name, content in members.items():
            handle.writestr(name, content)
    return path


def _baseline_inspector(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as handle:
        return {item.filename for item in handle.infolist() if not item.is_dir() and "/" not in item.filename}


def _candidate_inspector(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as handle:
        return {item.filename for item in handle.infolist() if not item.is_dir()}


def _score(inspector: Callable[[Path], set[str]], path: Path, expected: set[str]) -> float:
    observed = inspector(path)
    return len(observed & expected) / len(expected) if expected else float(not observed)


def run_fixture(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    missions = MissionStore(root / "missions.db")
    artifacts = ArtifactStore(missions, root / "artifacts")
    competence = CompetenceRegistry(root / "competence.db")

    failure_id = "archive-failure-v1"
    failure_criterion = "all regular archive members are enumerated"
    missions.create(Mission(
        mission_id=failure_id, objective="Inspect every regular member in an archive",
        completion_criteria=[failure_criterion]))
    missions.transition(failure_id, "planned")
    missions.transition(failure_id, "running")
    archive_a = _archive(root / "cases" / "failure.zip", {
        "README.txt": "visible", "nested/config.yaml": "missed",
    })
    archive_artifact = artifacts.put_file(
        failure_id, archive_a, producer_id="archive-fixture", media_type="application/zip")
    baseline_seen = _baseline_inspector(archive_a)
    expected_a = {"README.txt", "nested/config.yaml"}
    failure_score = len(baseline_seen & expected_a) / len(expected_a)
    receipts = ReceiptStore(missions)
    receipt = receipts.prepare(Receipt(
        receipt_id="inspect-failure", mission_id=failure_id, task_id="archive-inspection-task",
        intention="enumerate all regular members", agent_id="baseline-inspector",
        tool="archive.inspect", target=str(archive_a), idempotency_key="archive-failure-v1"))
    receipts.settle(
        failure_id, receipt.receipt_id, "failed",
        observed_result={"members": sorted(baseline_seen), "score": failure_score},
        artifact_ids=[archive_artifact.artifact_id], error="nested member was not enumerated",
        idempotency_key="archive-failure-settled")
    missions.transition(failure_id, "failed", reason="observed nested-member miss")
    gap = competence.record_gap(
        "archives.enumerate", "Enumerate nested archive members",
        "baseline inspection only enumerated root-level regular files", impact=4,
        source_mission_id=failure_id, source_task_id="archive-inspection-task",
        evidence_artifact_ids=[archive_artifact.artifact_id])

    plan = competence.create_study_plan(
        gap["gap_id"], "learn complete ZIP member enumeration without extracting untrusted paths",
        sources=[{
            "uri": "https://docs.python.org/3.14/library/zipfile.html#zipfile.ZipFile.infolist",
            "version": "Python 3.14.9",
            "license": "PSF-2.0",
        }],
        development_case_ids=["practice-one-level", "practice-directory-entry"],
        holdout_case_ids=["holdout-two-level", "holdout-mixed", "holdout-empty"])
    competence.transition_gap(gap["gap_id"], "practicing")

    # Practice archives are separate and never reused in the proof set.
    practice = _archive(root / "cases" / "practice.zip", {
        "folder/": "", "folder/item.txt": "practice",
    })
    practice_score = _score(_candidate_inspector, practice, {"folder/item.txt"})
    if practice_score != 1.0:
        raise RuntimeError("candidate failed its development exercise")
    competence.transition_gap(gap["gap_id"], "proving")

    cases = {
        "holdout-two-level": {"a/b/c.txt": "deep", "root.txt": "root"},
        "holdout-mixed": {"x/one.txt": "1", "y/two.txt": "2", "top.txt": "3"},
        "holdout-empty": {},
    }
    baseline_scores: dict[str, float] = {}
    candidate_scores: dict[str, float] = {}
    case_hashes: dict[str, str] = {}
    for case_id, members in cases.items():
        case_path = _archive(root / "cases" / f"{case_id}.zip", members)
        expected = set(members)
        baseline_scores[case_id] = _score(_baseline_inspector, case_path, expected)
        candidate_scores[case_id] = _score(_candidate_inspector, case_path, expected)
        case_hashes[case_id] = hashlib.sha256(case_path.read_bytes()).hexdigest()

    proof_id = "archive-study-proof-v1"
    proof_criterion = "reserved archive cases improve without regression"
    missions.create(Mission(
        mission_id=proof_id, objective="Prove archive competence on unseen cases",
        completion_criteria=[proof_criterion]))
    missions.transition(proof_id, "planned")
    missions.transition(proof_id, "running")
    proof_path = root / "proof.json"
    proof_path.write_text(json.dumps({
        "plan_id": plan.plan_id, "development_case_ids": plan.development_case_ids,
        "holdout_case_ids": plan.holdout_case_ids, "case_hashes": case_hashes,
        "baseline_scores": baseline_scores, "candidate_scores": candidate_scores,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    proof_artifact = artifacts.put_file(
        proof_id, proof_path, producer_id="archive-study-runner", media_type="application/json")
    result = competence.evaluate_study(
        plan.plan_id, baseline_scores=baseline_scores, candidate_scores=candidate_scores,
        system={
            "skill": "zip-infolist@1", "template": "archive-inspection@1",
            "model": "deterministic-python", "tools": ["zipfile.ZipFile.infolist"],
            "environment": "python-3.14.9",
        },
        evidence_artifact_ids=[proof_artifact.artifact_id], mission_id=proof_id)
    VerificationService(missions, artifacts).verify_artifact(
        proof_id, proof_criterion, proof_artifact.artifact_id,
        verifier_id="archive-independent-judge", executor_id="archive-study-runner",
        verification_id="archive-study-proof")
    missions.transition(proof_id, "verifying")
    completed = missions.transition(proof_id, "completed")

    if not result["passed"] or completed.status.value != "completed":
        raise RuntimeError("archive study did not pass its independent proof")
    return {
        "schema_version": 1,
        "fixture_id": "phase3-competence-study-v1",
        "status": "passed",
        "failure": {
            "mission_id": failure_id, "score": failure_score,
            "artifact_id": archive_artifact.artifact_id,
        },
        "gap": competence.gap(gap["gap_id"]),
        "study_plan": competence.study_plan(plan.plan_id).to_dict(),
        "practice_score": practice_score,
        "evaluation": result,
        "proof_mission_status": completed.status.value,
        "competence": competence.current("archives.enumerate"),
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
