"""Video frame OCR preserves screen evidence and partial speech outcomes."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control.cli import mission_command, register_cli
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_video_ocr import extract_video_local, extract_video_screen_text


pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg/ffprobe unavailable",
)


def _video(path: Path, *, silent: bool = False) -> None:
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
               "-f", "lavfi", "-i", "color=c=white:s=320x180:r=2:d=2"]
    if not silent:
        command += ["-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "aac"]
    subprocess.run(
        [*command, "-c:v", "mpeg4", str(path)],
        check=True, capture_output=True, timeout=20,
    )


def _ocr_rows(frames):
    return "fixture_ocr", [
        {"path": str(frame), "text": "github.com/example/project", "confidence": 0.99}
        for frame in frames
    ]


def test_video_screen_text_archives_frame_and_supports_exact_quote(tmp_path, monkeypatch):
    video = tmp_path / "lesson.mp4"
    _video(video)
    fabric = LearningFabric(tmp_path / "fabric")
    source = fabric.ingest_file(video, modality="video")
    monkeypatch.setattr(
        "tools.transcription_tools.transcribe_audio_local_fallback",
        lambda path, **kwargs: {"success": True, "transcript": "Veja o projeto na tela.", "provider": "fixture_stt"},
    )
    monkeypatch.setattr("plugins.mission_control.learning_video_ocr._ocr_backend", _ocr_rows)
    result = extract_video_local(fabric, source["source_id"])
    assert result["extraction_status"] == "transcribed_local"
    assert "Veja o projeto na tela." in result["extracted_text"]
    assert "github.com/example/project" in result["extracted_text"]
    evidence = result["metadata"]["frame_ocr"]["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["seconds"] == 0
    assert hashlib.sha256(Path(evidence[0]["frame_path"]).read_bytes()).hexdigest() == evidence[0]["frame_hash"]
    assert fabric.propose_claim(
        source["source_id"], "The project appeared on screen", "github.com/example/project"
    )["status"] == "candidate"
    assert extract_video_screen_text(fabric, source["source_id"])["metadata"]["frame_ocr"] == result["metadata"]["frame_ocr"]


def test_silent_video_keeps_screen_evidence_and_speech_error(tmp_path, monkeypatch):
    video = tmp_path / "silent.mp4"
    _video(video, silent=True)
    fabric = LearningFabric(tmp_path / "fabric")
    source = fabric.ingest_file(video, modality="video")
    monkeypatch.setattr("plugins.mission_control.learning_video_ocr._ocr_backend", _ocr_rows)
    result = extract_video_local(fabric, source["source_id"])
    assert result["extraction_status"] == "screen_text_local"
    assert "github.com/example/project" in result["extracted_text"]
    assert result["metadata"]["local_extraction_error"]


def test_ocr_failure_keeps_speech_and_reports_error(tmp_path, monkeypatch):
    video = tmp_path / "lesson.mp4"
    _video(video)
    fabric = LearningFabric(tmp_path / "fabric")
    source = fabric.ingest_file(video, modality="video")
    monkeypatch.setattr(
        "tools.transcription_tools.transcribe_audio_local_fallback",
        lambda path, **kwargs: {"success": True, "transcript": "Spoken only.", "provider": "fixture_stt"},
    )
    monkeypatch.setattr(
        "plugins.mission_control.learning_video_ocr._ocr_backend",
        lambda frames: (_ for _ in ()).throw(ValueError("OCR backend unavailable")),
    )
    result = extract_video_local(fabric, source["source_id"])
    assert result["extraction_status"] == "transcribed_local"
    assert result["extracted_text"] == "Spoken only."
    assert "OCR backend unavailable" in result["metadata"]["frame_ocr_error"]


def test_speech_after_screen_text_preserves_claim_offsets(tmp_path, monkeypatch):
    video = tmp_path / "lesson.mp4"
    _video(video)
    fabric = LearningFabric(tmp_path / "fabric")
    source = fabric.ingest_file(video, modality="video")
    monkeypatch.setattr("plugins.mission_control.learning_video_ocr._ocr_backend", _ocr_rows)
    screened = extract_video_screen_text(fabric, source["source_id"])
    claim = fabric.propose_claim(
        source["source_id"], "Project shown", "github.com/example/project",
    )
    monkeypatch.setattr(
        "tools.transcription_tools.transcribe_audio_local_fallback",
        lambda path, **kwargs: {"success": True, "transcript": "Listen too.", "provider": "fixture_stt"},
    )
    result = extract_video_local(fabric, source["source_id"])
    assert result["extracted_text"].startswith(screened["extracted_text"])
    assert result["extracted_text"].endswith("Listen too.")
    assert result["extracted_text"][claim["start_offset"]:claim["end_offset"]] == claim["quote"]


def test_completed_ocr_rejects_tampered_frame(tmp_path, monkeypatch):
    video = tmp_path / "lesson.mp4"
    _video(video, silent=True)
    fabric = LearningFabric(tmp_path / "fabric")
    source = fabric.ingest_file(video, modality="video")
    monkeypatch.setattr("plugins.mission_control.learning_video_ocr._ocr_backend", _ocr_rows)
    result = extract_video_screen_text(fabric, source["source_id"])
    Path(result["metadata"]["frame_ocr"]["evidence"][0]["frame_path"]).write_bytes(b"altered")
    with pytest.raises(ValueError, match="archived OCR frame has changed"):
        extract_video_screen_text(fabric, source["source_id"])


def test_video_cli_ingest_and_frame_retry_share_source(tmp_path, monkeypatch, capsys):
    video = tmp_path / "lesson.mp4"
    _video(video, silent=True)
    profile = tmp_path / "profile"
    monkeypatch.setenv("NARA_HOME", str(profile))
    token = set_nara_home_override(profile)
    try:
        monkeypatch.setattr("plugins.mission_control.learning_video_ocr._ocr_backend", _ocr_rows)
        parser = argparse.ArgumentParser()
        register_cli(parser)
        assert mission_command(parser.parse_args([
            "learn-media-ingest", str(video), "--modality", "video", "--extract-local",
        ])) == 0
        ingested = json.loads(capsys.readouterr().out)
        assert ingested["extraction_status"] == "screen_text_local"
        assert mission_command(parser.parse_args([
            "learn-media-frames", ingested["source_id"],
        ])) == 0
        repeated = json.loads(capsys.readouterr().out)
        assert repeated["metadata"]["frame_ocr"] == ingested["metadata"]["frame_ocr"]
    finally:
        reset_nara_home_override(token)


def test_supplied_transcript_after_screen_ocr_preserves_claim_offsets(tmp_path, monkeypatch):
    video = tmp_path / "lesson.mp4"
    transcript = tmp_path / "lesson.txt"
    _video(video, silent=True)
    transcript.write_text("Human transcript.")
    fabric = LearningFabric(tmp_path / "fabric")
    source = fabric.ingest_file(video, modality="video")
    monkeypatch.setattr("plugins.mission_control.learning_video_ocr._ocr_backend", _ocr_rows)
    screened = extract_video_screen_text(fabric, source["source_id"])
    claim = fabric.propose_claim(
        source["source_id"], "Project shown", "github.com/example/project",
    )
    result = fabric.ingest_file(video, modality="video", transcript_path=transcript)
    assert result["extraction_status"] == "transcript_supplied"
    assert result["extracted_text"].startswith(screened["extracted_text"])
    assert result["extracted_text"].endswith("Human transcript.")
    assert result["extracted_text"][claim["start_offset"]:claim["end_offset"]] == claim["quote"]
    assert extract_video_screen_text(fabric, source["source_id"])["source_id"] == source["source_id"]
