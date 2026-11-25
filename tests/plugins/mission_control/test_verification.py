from __future__ import annotations

import pytest

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.contracts import Mission, Verification, VerificationStatus
from plugins.mission_control.store import MissionStore, MissionStoreError
from plugins.mission_control.verification import VerificationService


def _services(tmp_path):
    missions = MissionStore(tmp_path / "missions.db")
    missions.create(Mission(
        mission_id="mission-1",
        objective="Write report",
        completion_criteria=["report exists", "report hash matches"],
    ))
    artifacts = ArtifactStore(missions, tmp_path / "artifacts")
    return missions, artifacts, VerificationService(missions, artifacts)


def test_completion_requires_pass_for_every_criterion(tmp_path):
    missions, artifacts, verifier = _services(tmp_path)
    artifact = artifacts.put_bytes(
        "mission-1", b"report", producer_id="worker-1", media_type="text/plain")
    missions.transition("mission-1", "planned")
    missions.transition("mission-1", "running")
    missions.transition("mission-1", "verifying")

    verifier.verify_artifact(
        "mission-1", "report exists", artifact.artifact_id,
        verifier_id="judge-1", executor_id="worker-1", verification_id="verify-exists",
    )
    with pytest.raises(MissionStoreError, match="report hash matches.*no verification"):
        missions.transition("mission-1", "completed")

    verifier.verify_artifact(
        "mission-1", "report hash matches", artifact.artifact_id,
        verifier_id="judge-1", executor_id="worker-1", verification_id="verify-hash",
    )
    completed = missions.transition("mission-1", "completed")

    assert completed.status.value == "completed"
    assert verifier.blockers("mission-1") == []


def test_executor_claim_without_evidence_cannot_complete(tmp_path):
    missions, _, verifier = _services(tmp_path)
    missions.transition("mission-1", "planned")
    missions.transition("mission-1", "running")
    missions.transition("mission-1", "verifying")

    with pytest.raises(MissionStoreError, match="no verification"):
        missions.transition("mission-1", "completed")
    assert len(missions.events("mission-1")) == 4
    assert verifier.blockers("mission-1") == [
        "'report exists' has no verification",
        "'report hash matches' has no verification",
    ]


def test_latest_failure_overrides_older_pass(tmp_path):
    _, artifacts, verifier = _services(tmp_path)
    artifact = artifacts.put_bytes("mission-1", b"report", producer_id="worker-1")
    verifier.verify_artifact(
        "mission-1", "report exists", artifact.artifact_id,
        verifier_id="judge-1", executor_id="worker-1", verification_id="pass-1",
    )
    verifier.record(Verification(
        verification_id="fail-2",
        mission_id="mission-1",
        criterion="report exists",
        verifier_id="judge-2",
        executor_id="worker-1",
        status=VerificationStatus.FAIL,
        evidence_artifact_ids=[artifact.artifact_id],
        method="manual review",
        observed_at="9999-01-01T00:00:00+00:00",
        explanation="injected regression",
    ))

    assert verifier.blockers("mission-1") == [
        "'report exists' is fail",
        "'report hash matches' has no verification",
    ]


def test_pass_reopens_and_hashes_evidence(tmp_path):
    _, artifacts, verifier = _services(tmp_path)
    artifact = artifacts.put_bytes("mission-1", b"report", producer_id="worker-1")
    artifacts_path = artifact.location
    with open(artifacts_path, "wb") as handle:
        handle.write(b"tampered")

    verification = verifier.verify_artifact(
        "mission-1", "report exists", artifact.artifact_id,
        verifier_id="judge-1", executor_id="worker-1", verification_id="tampered",
    )

    assert verification.status is VerificationStatus.FAIL
