from __future__ import annotations

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.contracts import Mission
from plugins.mission_control.store import MissionStore


def _store(tmp_path):
    missions = MissionStore(tmp_path / "missions.db")
    missions.create(Mission(
        mission_id="mission-1", objective="Write report", completion_criteria=["report exists"],
    ))
    return missions, ArtifactStore(missions, tmp_path / "artifacts")


def test_artifact_is_content_addressed_and_recoverable_after_restart(tmp_path):
    missions, artifacts = _store(tmp_path)
    first = artifacts.put_bytes(
        "mission-1", b"verified report\n", producer_id="worker-1", media_type="text/plain",
    )
    replay = artifacts.put_bytes(
        "mission-1", b"verified report\n", producer_id="worker-1", media_type="text/plain",
    )

    restarted = ArtifactStore(MissionStore(missions.path), tmp_path / "artifacts")

    assert replay == first
    assert first.artifact_id == f"sha256:{first.sha256}"
    assert restarted.read_bytes("mission-1", first.artifact_id) == b"verified report\n"
    assert len([event for event in missions.events("mission-1")
                if event.event_type == "mission.artifact_registered"]) == 1


def test_put_file_preserves_source_name_as_metadata(tmp_path):
    _, artifacts = _store(tmp_path)
    source = tmp_path / "report.txt"
    source.write_text("content", encoding="utf-8")

    artifact = artifacts.put_file(
        "mission-1", source, producer_id="worker-1", media_type="text/plain",
    )

    assert artifact.metadata["source_name"] == "report.txt"
    assert artifacts.verify("mission-1", artifact.artifact_id) is True
