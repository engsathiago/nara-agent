from __future__ import annotations

import pytest

from plugins.mission_control.contracts import (
    Artifact,
    ContractError,
    EffectStatus,
    Mission,
    MissionStatus,
    Receipt,
    Verification,
    VerificationStatus,
    assert_mission_transition,
    load_contract,
)


def test_mission_round_trip_preserves_versioned_contract():
    mission = Mission(
        mission_id="mission-1",
        objective="Produce a verified report",
        completion_criteria=["report exists", "hash matches"],
        constraints={"network": "offline"},
    )

    restored = load_contract(mission.to_dict())

    assert restored == mission
    assert restored.status is MissionStatus.DRAFT


def test_v0_mission_migrates_aliases_before_validation():
    mission = load_contract({
        "kind": "mission",
        "id": "mission-old",
        "goal": "Resume safely",
        "criteria": ["no duplicate effect"],
    })

    assert mission.schema_version == 1
    assert mission.mission_id == "mission-old"
    assert mission.objective == "Resume safely"


def test_receipt_keeps_unknown_effect_distinct_from_failure():
    receipt = Receipt(
        receipt_id="receipt-1",
        mission_id="mission-1",
        task_id="task-1",
        intention="Write report",
        agent_id="worker-1",
        tool="file.write",
        target="report.txt",
        idempotency_key="mission-1:report-v1",
        effect_status=EffectStatus.UNKNOWN,
    )

    assert load_contract(receipt.to_dict()).effect_status is EffectStatus.UNKNOWN


def test_pass_verification_requires_independent_verifier_and_evidence():
    with pytest.raises(ContractError, match="differ"):
        Verification(
            verification_id="verify-1", mission_id="mission-1", criterion="report exists",
            verifier_id="worker-1", executor_id="worker-1", method="sha256",
        )

    with pytest.raises(ContractError, match="evidence"):
        Verification(
            verification_id="verify-2", mission_id="mission-1", criterion="report exists",
            verifier_id="judge-1", executor_id="worker-1", method="sha256",
            status=VerificationStatus.PASS,
        )


def test_artifact_rejects_non_sha256_identifier():
    with pytest.raises(ContractError, match="sha256"):
        Artifact(
            artifact_id="artifact-1", sha256="not-a-digest", producer_id="worker-1",
            mission_id="mission-1", location="artifacts/report.txt",
        )


@pytest.mark.parametrize("source,target", [
    (MissionStatus.DRAFT, MissionStatus.PLANNED),
    (MissionStatus.PLANNED, MissionStatus.RUNNING),
    (MissionStatus.RUNNING, MissionStatus.VERIFYING),
    (MissionStatus.VERIFYING, MissionStatus.COMPLETED),
])
def test_valid_mission_lifecycle(source, target):
    assert_mission_transition(source, target)


def test_terminal_mission_cannot_return_to_running():
    with pytest.raises(ContractError, match="completed -> running"):
        assert_mission_transition(MissionStatus.COMPLETED, MissionStatus.RUNNING)
