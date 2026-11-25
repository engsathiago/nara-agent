"""Content-addressed artifact storage linked to durable missions."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from plugins.mission_control.contracts import Artifact, load_contract
from plugins.mission_control.store import MissionNotFoundError, MissionStore, MissionStoreError
from plugins.plugin_storage import plugin_data_dir


class ArtifactStore:
    def __init__(self, missions: MissionStore, root: Path | str):
        self.missions = missions
        self.root = Path(root)

    @classmethod
    def open_default(cls) -> ArtifactStore:
        return cls(MissionStore.open_default(), plugin_data_dir("mission-control") / "artifacts")

    def put_bytes(
        self,
        mission_id: str,
        content: bytes,
        *,
        producer_id: str,
        media_type: str = "application/octet-stream",
        metadata: dict[str, Any] | None = None,
        retention: str = "mission",
    ) -> Artifact:
        if self.missions.get(mission_id) is None:
            raise MissionNotFoundError(mission_id)
        digest = hashlib.sha256(content).hexdigest()
        artifact_id = f"sha256:{digest}"
        destination = self.root / digest[:2] / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise MissionStoreError(f"artifact path failed hash verification: {destination}")
        else:
            with NamedTemporaryFile("wb", dir=destination.parent, delete=False) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            temporary.replace(destination)
        artifact = Artifact(
            artifact_id=artifact_id,
            sha256=digest,
            media_type=media_type,
            size_bytes=len(content),
            producer_id=producer_id,
            mission_id=mission_id,
            location=str(destination),
            metadata=metadata or {},
            retention=retention,
        )
        self.missions.register_artifact(artifact)
        return artifact

    def put_file(
        self, mission_id: str, path: Path | str, *, producer_id: str,
        media_type: str = "application/octet-stream", metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        source = Path(path)
        return self.put_bytes(
            mission_id, source.read_bytes(), producer_id=producer_id, media_type=media_type,
            metadata={"source_name": source.name, **(metadata or {})},
        )

    def get(self, mission_id: str, artifact_id: str) -> Artifact | None:
        mission = self.missions.get(mission_id)
        if mission is None:
            raise MissionNotFoundError(mission_id)
        payload = mission.artifacts.get(artifact_id)
        contract = load_contract(payload) if payload else None
        return contract if isinstance(contract, Artifact) else None

    def read_bytes(self, mission_id: str, artifact_id: str) -> bytes:
        artifact = self.get(mission_id, artifact_id)
        if artifact is None:
            raise MissionStoreError(f"unknown artifact: {artifact_id}")
        content = Path(artifact.location).read_bytes()
        if len(content) != artifact.size_bytes or hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise MissionStoreError(f"artifact verification failed: {artifact_id}")
        return content

    def verify(self, mission_id: str, artifact_id: str) -> bool:
        self.read_bytes(mission_id, artifact_id)
        return True

