import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from extensions.nara_temporal_memory.nara_temporal import TemporalMemoryStore
from nara_constants import set_nara_home_override, reset_nara_home_override
from plugins.mission_control.cli import register_cli, mission_command
from plugins.mission_control.learning import LearningLab
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_github_source import _check_cited_source
from plugins.mission_control import learning_retention as retention
from plugins.mission_control.store import MissionStore


def _source(fabric, tmp_path, *, keep=False):
    original = tmp_path / "lesson.mp4"
    original.write_bytes(b"media original evidence")
    transcript = tmp_path / "transcript.txt"
    transcript.write_text("Check the output after editing.", encoding="utf-8")
    return original, fabric.ingest_file(original, modality="video", transcript_path=transcript,
                                       retain_original=keep)


def test_expiry_cli_preserves_candidate_evaluation_and_reingestion(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("NARA_HOME", str(home))
    token = set_nara_home_override(home)
    try:
        fabric = LearningFabric.open_default()
        original, source = _source(fabric, tmp_path)
        lab = LearningLab(MissionStore(home / "missions.db"),
                          TemporalMemoryStore(home / "memory.db"), home / "candidates",
                          home / "skills", source_fabric=fabric)
        candidate = lab.propose_from_media(source["source_id"], None, "Check output",
                                          ["Check the output"], ["Check the output"])
        expiry = source["metadata"]["original_retention"]["expires_at"]
        monkeypatch.setattr(retention, "time", SimpleNamespace(time=lambda: expiry + 1))
        parser = argparse.ArgumentParser()
        register_cli(parser)
        assert mission_command(parser.parse_args(["learn-media-retention", "--expire"])) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["expired"] == [source["source_id"]] and not report["errors"]
        assert not Path(source["stored_path"]).exists()
        assert original.exists()
        reopened = LearningFabric(fabric.root)
        _check_cited_source(reopened.source(source["source_id"]))
        report = lab.evaluate_transfer(candidate.candidate_id, [{"case_id": "reserved"}],
                                       lambda candidate, case: float(candidate is not None),
                                       development_case_ids=set())
        assert report["passed"]  # Integration seam only; not a real-learning claim.
        Path(source["transcript_path"]).write_text("changed", encoding="utf-8")
        with pytest.raises(ValueError, match="transcript archive has changed"):
            lab.evaluate_transfer(candidate.candidate_id, [{"case_id": "reserved"}],
                                  lambda *a: 1, development_case_ids=set())
        restored = reopened.ingest_file(original, modality="video")
        assert Path(restored["stored_path"]).exists()
        assert restored["metadata"]["original_retention"]["status"] == "active"
    finally:
        reset_nara_home_override(token)


def test_interrupted_expiry_resumes_and_keep_policy_is_honored(tmp_path, monkeypatch):
    fabric = LearningFabric(tmp_path / "fabric")
    _, source = _source(fabric, tmp_path)
    expiry = source["metadata"]["original_retention"]["expires_at"] + 1
    original_unlink = Path.unlink

    def interrupted(path, *args, **kwargs):
        if str(path) == source["stored_path"]:
            raise OSError("interrupted unlink")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", interrupted)
        assert retention.expire_originals(fabric, now=expiry)["errors"]
    assert fabric.source(source["source_id"])["metadata"]["original_retention"]["status"] == "expiring"
    assert retention.retention_status(fabric)["state"] == "degraded"
    assert retention.expire_originals(LearningFabric(fabric.root), now=expiry)["expired"] == [source["source_id"]]
    assert retention.expire_originals(fabric, now=expiry)["expired"] == []
    assert retention.retention_status(fabric)["state"] == "available"
    kept_root = tmp_path / "kept"
    kept_root.mkdir()
    _, kept = _source(LearningFabric(kept_root / "fabric"), kept_root, keep=True)
    assert retention.expire_originals(LearningFabric(kept_root / "fabric"), now=expiry)["expired"] == []
    assert Path(kept["stored_path"]).exists()


def test_gateway_expires_media_without_a_mission_store(tmp_path, monkeypatch):
    from plugins.mission_control.consolidation import maybe_run_gateway_consolidation

    monkeypatch.setenv("NARA_HOME", str(tmp_path / "home"))
    token = set_nara_home_override(tmp_path / "home")
    try:
        fabric = LearningFabric.open_default()
        _, source = _source(fabric, tmp_path)
        expiry = source["metadata"]["original_retention"]["expires_at"]
        monkeypatch.setattr(retention, "time", SimpleNamespace(time=lambda: expiry + 1))
        maybe_run_gateway_consolidation()
        assert not Path(source["stored_path"]).exists()
        assert fabric.source(source["source_id"])["metadata"]["original_retention"]["status"] == "expired"
    finally:
        reset_nara_home_override(token)


def test_expiry_preserves_bytes_shared_with_derived_evidence(tmp_path):
    fabric = LearningFabric(tmp_path / "fabric")
    original, source = _source(fabric, tmp_path)
    other = tmp_path / "other.txt"
    other.write_text("Separate source", encoding="utf-8")
    fabric.ingest_file(other, modality="document", transcript_path=original)
    report = retention.expire_originals(fabric, now=source["metadata"]["original_retention"]["expires_at"] + 1)
    assert report["shared_evidence"] == [source["source_id"]]
    assert Path(source["stored_path"]).exists()
