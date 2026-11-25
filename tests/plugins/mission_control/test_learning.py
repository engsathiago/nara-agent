from __future__ import annotations

from extensions.nara_temporal_memory.nara_temporal import TemporalMemoryStore
from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.contracts import Mission, Receipt
from plugins.mission_control.learning import LearningLab
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.verification import VerificationService


def _completed_mission(tmp_path):
    missions = MissionStore(tmp_path / "missions.db")
    missions.create(Mission(
        mission_id="mission-a", objective="write report safely",
        completion_criteria=["report hash matches"],
    ))
    receipts = ReceiptStore(missions)
    receipt = receipts.prepare(Receipt(
        receipt_id="write", mission_id="mission-a", task_id="task-a",
        intention="write a report atomically", agent_id="worker-a", tool="file.atomic_write",
        target="report-a.txt", idempotency_key="write-a",
    ))
    artifacts = ArtifactStore(missions, tmp_path / "artifacts")
    artifact = artifacts.put_bytes("mission-a", b"report-a", producer_id="worker-a")
    receipts.settle(
        "mission-a", receipt.receipt_id, "confirmed", artifact_ids=[artifact.artifact_id],
        idempotency_key="write-a-confirmed",
    )
    verifier = VerificationService(missions, artifacts)
    verifier.verify_artifact(
        "mission-a", "report hash matches", artifact.artifact_id,
        verifier_id="judge-a", executor_id="worker-a", verification_id="verify-a",
    )
    missions.transition("mission-a", "planned")
    missions.transition("mission-a", "running")
    missions.transition("mission-a", "verifying")
    missions.transition("mission-a", "completed")
    return missions


def test_verified_mission_becomes_inactive_candidate_then_transfers(tmp_path):
    missions = _completed_mission(tmp_path)
    memory = TemporalMemoryStore(tmp_path / "memory.db")
    lab = LearningLab(missions, memory, tmp_path / "candidates", tmp_path / "skills")

    candidate = lab.extract("mission-a", name="atomic report write")
    before = memory.get(f"procedure:{candidate.candidate_id}")
    report = lab.evaluate_transfer(
        candidate.candidate_id,
        [
            {"case_id": "development-a", "requires": "unseen"},
            {"case_id": "holdout-b", "requires": "file.atomic_write"},
        ],
        lambda procedure, case: (
            1.0 if procedure and case["requires"] in " ".join(procedure.steps) else 0.0),
        development_case_ids={"development-a"},
    )
    skill_path = lab.promote(candidate.candidate_id)

    assert before["status"] == "candidate"
    assert report["holdout_case_ids"] == ["holdout-b"]
    assert report["passed"] is True
    assert (skill_path / "SKILL.md").exists()
    assert memory.get(f"procedure:{candidate.candidate_id}")["status"] == "active"


def test_regression_prevents_promotion_and_rollback_disables_skill(tmp_path):
    missions = _completed_mission(tmp_path)
    memory = TemporalMemoryStore(tmp_path / "memory.db")
    lab = LearningLab(missions, memory, tmp_path / "candidates", tmp_path / "skills")
    candidate = lab.extract("mission-a", name="atomic report write")
    lab.evaluate_transfer(
        candidate.candidate_id,
        [{"case_id": "holdout-b"}],
        lambda procedure, _case: 1.0 if procedure else 0.0,
        development_case_ids=set(),
    )
    skill_path = lab.promote(candidate.candidate_id)
    disabled = lab.rollback(candidate.candidate_id)

    assert not skill_path.exists()
    assert disabled.name.endswith(".disabled")
    assert memory.get(f"procedure:{candidate.candidate_id}")["status"] == "rejected"
