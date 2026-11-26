"""Real ffmpeg audio/video decode and Learning Fabric transcript provenance."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_fabric_tool import learning_ingest_tool
from plugins.mission_control.learning_media import extract_local_media
from plugins.mission_control.cli import mission_command, register_cli


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg/ffprobe unavailable",
)


def _media(path: Path, modality: str) -> None:
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    if modality == "video":
        command += ["-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-shortest", "-c:v", "mpeg4", "-c:a", "aac", str(path)]
    else:
        command += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-ac", "1", "-ar", "16000", str(path)]
    subprocess.run(command, check=True, capture_output=True, timeout=20)


@pytest.mark.parametrize("modality,suffix", [("audio", "wav"), ("video", "mp4")])
def test_local_media_extraction_archives_real_decode_and_quote(tmp_path, monkeypatch, modality, suffix):
    monkeypatch.setenv("NARA_HOME", str(tmp_path / "profile"))
    token = set_nara_home_override(tmp_path / "profile")
    try:
        media = tmp_path / f"source.{suffix}"
        _media(media, modality)
        monkeypatch.setattr(
            "tools.transcription_tools.transcribe_audio_local_fallback",
            lambda path, **kwargs: {"success": True, "transcript": "A Nara verifica resultados.", "provider": "fixture-stt"},
        )
        source = learning_ingest_tool(str(media), modality, extract_local=True)
        original = LearningFabric.open_default().source(source["source_id"])
        assert original["extraction_status"] == "transcribed_local"
        assert original["source_hash"] == hashlib.sha256(media.read_bytes()).hexdigest()
        assert Path(original["stored_path"]).read_bytes() == media.read_bytes()
        assert Path(original["transcript_path"]).read_text() == "A Nara verifica resultados."
        assert original["metadata"]["local_extraction"]["duration_seconds"] > 0
        assert original["metadata"]["local_extraction"]["language_requested"] == "pt"
        assert LearningFabric.open_default().propose_claim(
            source["source_id"], "Nara verifies results", "verifica resultados"
        )["status"] == "candidate"
        assert extract_local_media(LearningFabric.open_default(), source["source_id"])["transcript_hash"] == original["transcript_hash"]
    finally:
        reset_nara_home_override(token)


def test_local_stt_failure_keeps_original_and_reports_error(tmp_path, monkeypatch):
    monkeypatch.setenv("NARA_HOME", str(tmp_path / "profile"))
    token = set_nara_home_override(tmp_path / "profile")
    try:
        media = tmp_path / "source.wav"
        _media(media, "audio")
        monkeypatch.setattr(
            "tools.transcription_tools.transcribe_audio_local_fallback",
            lambda path, **kwargs: {"success": False, "transcript": "", "error": "local model unavailable"},
        )
        fabric = LearningFabric.open_default()
        source = fabric.ingest_file(media, modality="audio")
        with pytest.raises(ValueError, match="local model unavailable"):
            extract_local_media(fabric, source["source_id"])
        after = fabric.source(source["source_id"])
        assert after["extraction_status"] == "needs_extraction"
        assert after["metadata"]["local_extraction_error"] == "local model unavailable"
        assert Path(after["stored_path"]).read_bytes() == media.read_bytes()
    finally:
        reset_nara_home_override(token)


def test_media_cli_ingest_show_and_propose_use_same_store(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NARA_HOME", str(tmp_path / "profile"))
    token = set_nara_home_override(tmp_path / "profile")
    try:
        media = tmp_path / "lesson.wav"
        _media(media, "audio")
        monkeypatch.setattr(
            "tools.transcription_tools.transcribe_audio_local_fallback",
            lambda path, **kwargs: {"success": True, "transcript": "Nara confirma o resultado.", "provider": "fixture-stt"},
        )
        parser = argparse.ArgumentParser()
        register_cli(parser)
        assert mission_command(parser.parse_args([
            "learn-media-ingest", str(media), "--modality", "audio", "--extract-local",
        ])) == 0
        source = json.loads(capsys.readouterr().out)
        assert source["extracted_text"] == "Nara confirma o resultado."
        assert mission_command(parser.parse_args(["learn-media-show", source["source_id"]])) == 0
        assert json.loads(capsys.readouterr().out)["source_hash"] == source["source_hash"]
        assert mission_command(parser.parse_args([
            "learn-media-propose", source["source_id"], "Nara checks the outcome",
            "--quote", "confirma o resultado",
        ])) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "candidate"
    finally:
        reset_nara_home_override(token)


def test_oversized_video_is_rejected_before_loading_bytes(tmp_path):
    huge = tmp_path / "huge.mp4"
    with huge.open("wb") as handle:
        handle.truncate(500_000_001)
    with pytest.raises(ValueError, match="exceeds 500 MB"):
        LearningFabric(tmp_path / "fabric").ingest_file(huge, modality="video")


def test_reingest_preserves_extraction_and_claim_evidence(tmp_path, monkeypatch):
    media = tmp_path / "lesson.wav"
    _media(media, "audio")
    fabric = LearningFabric(tmp_path / "fabric")
    source = fabric.ingest_file(media, modality="audio")
    monkeypatch.setattr(
        "tools.transcription_tools.transcribe_audio_local_fallback",
        lambda path, **kwargs: {"success": True, "transcript": "Nara confirma o resultado.", "provider": "fixture-stt"},
    )
    extracted = extract_local_media(fabric, source["source_id"])
    claim = fabric.propose_claim(source["source_id"], "Nara confirms", "confirma o resultado")
    repeated = fabric.ingest_file(media, modality="audio")
    assert repeated["transcript_hash"] == extracted["transcript_hash"]
    assert repeated["extracted_text"] == extracted["extracted_text"]
    assert fabric.claim(claim["claim_id"])["status"] == "candidate"


def test_supplied_transcript_cannot_be_overwritten_by_local_stt(tmp_path):
    media = tmp_path / "lesson.wav"
    transcript = tmp_path / "lesson.txt"
    _media(media, "audio")
    transcript.write_text("Human supplied transcript.")
    fabric = LearningFabric(tmp_path / "fabric")
    source = fabric.ingest_file(media, modality="audio", transcript_path=transcript)
    with pytest.raises(ValueError, match="supplied transcript"):
        extract_local_media(fabric, source["source_id"])
    assert fabric.source(source["source_id"])["extracted_text"] == "Human supplied transcript."
