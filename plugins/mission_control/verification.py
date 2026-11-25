"""Independent, evidence-backed completion verification for durable missions."""

from __future__ import annotations

import uuid
from pathlib import Path

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.contracts import Verification, VerificationStatus
from plugins.mission_control.store import (
    MissionNotFoundError,
    MissionStore,
    MissionStoreError,
    completion_blockers,
)


class VerificationService:
    def __init__(self, missions: MissionStore, artifacts: ArtifactStore):
        self.missions = missions
        self.artifacts = artifacts

    @classmethod
    def open_default(cls) -> VerificationService:
        missions = MissionStore.open_default()
        return cls(missions, ArtifactStore(missions, missions.path.parent / "artifacts"))

    def record(self, verification: Verification) -> Verification:
        mission = self.missions.get(verification.mission_id)
        if mission is None:
            raise MissionNotFoundError(verification.mission_id)
        if verification.criterion not in mission.completion_criteria:
            raise MissionStoreError(
                f"verification criterion is not in the mission contract: {verification.criterion}")
        for artifact_id in verification.evidence_artifact_ids:
            if self.artifacts.get(verification.mission_id, artifact_id) is None:
                raise MissionStoreError(f"unknown evidence artifact: {artifact_id}")
            if verification.status is VerificationStatus.PASS:
                self.artifacts.verify(verification.mission_id, artifact_id)
        self.missions.record_verification(verification)
        return verification

    def verify_artifact(
        self,
        mission_id: str,
        criterion: str,
        artifact_id: str,
        *,
        verifier_id: str,
        executor_id: str,
        method: str = "sha256",
        verification_id: str | None = None,
    ) -> Verification:
        status = VerificationStatus.PASS
        explanation = "artifact size and SHA-256 match the durable contract"
        try:
            self.artifacts.verify(mission_id, artifact_id)
        except (OSError, MissionStoreError) as exc:
            status = VerificationStatus.FAIL
            explanation = str(exc)
        verification = Verification(
            verification_id=verification_id or uuid.uuid4().hex,
            mission_id=mission_id,
            criterion=criterion,
            verifier_id=verifier_id,
            executor_id=executor_id,
            status=status,
            evidence_artifact_ids=[artifact_id],
            method=method,
            explanation=explanation,
        )
        return self.record(verification)

    def blockers(self, mission_id: str) -> list[str]:
        mission = self.missions.get(mission_id)
        if mission is None:
            raise MissionNotFoundError(mission_id)
        return completion_blockers(mission)


def default_verification_service(path: Path | str) -> VerificationService:
    missions = MissionStore(path)
    return VerificationService(missions, ArtifactStore(missions, missions.path.parent / "artifacts"))
