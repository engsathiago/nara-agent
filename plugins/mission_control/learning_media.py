"""Local audio/video extraction for the provenance-first Learning Fabric."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

from nara_cli.sqlite_util import transaction
from plugins.mission_control.contracts import utc_now
from plugins.mission_control.learning_speech_timing import archive_speech_timing, check_speech_timing

if TYPE_CHECKING:
    from plugins.mission_control.learning_fabric import LearningFabric


MAX_MEDIA_BYTES = 500_000_000
MAX_MEDIA_SECONDS = 900.0


class LearningEvidenceIntegrityError(ValueError):
    """Archived source or extraction evidence no longer matches its recorded hash."""


def _media_binary(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    if name == "ffmpeg":
        # Bundled Desktop venvs have the pinned FFmpeg tool beside the venv,
        # while a GUI launch may have only /usr/bin on PATH.
        payload = Path(sys.executable).absolute().parents[2]
        for candidate in sorted((payload / "tools").glob("ffmpeg-*/ffmpeg")):
            if candidate.is_file():
                return str(candidate)
    return None


def _duration(source: Path, ffprobe: str | None) -> float:
    if ffprobe:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
            capture_output=True, text=True, check=False, timeout=20, stdin=subprocess.DEVNULL,
        )
        if result.returncode:
            raise ValueError(f"ffprobe could not read media: {result.stderr[-300:]}")
        try:
            duration = float(result.stdout.strip())
        except ValueError as exc:
            raise ValueError("media has no readable duration") from exc
    else:
        try:
            import av

            with av.open(str(source)) as container:
                if container.duration is not None:
                    duration = float(container.duration) / 1_000_000
                else:
                    durations = [
                        float(stream.duration * stream.time_base)
                        for stream in container.streams if stream.duration is not None
                    ]
                    duration = max(durations) if durations else 0.0
        except ImportError as exc:
            raise ValueError("media duration needs ffprobe or the optional PyAV backend") from exc
        except Exception as exc:
            raise ValueError(f"PyAV could not read media duration: {exc}") from exc
    if not 0 < duration <= MAX_MEDIA_SECONDS:
        raise ValueError(f"media duration must be between 0 and {MAX_MEDIA_SECONDS:g} seconds")
    return duration


def _record_error(fabric: LearningFabric, source_id: str, metadata: dict[str, Any], error: str) -> None:
    metadata["local_extraction_error"] = error
    metadata["local_extraction_attempted_at"] = utc_now()
    with transaction(fabric._connect(), immediate=True) as conn:
        conn.execute(
            "UPDATE learning_sources SET metadata_json = ? WHERE source_id = ?",
            (json.dumps(metadata, sort_keys=True, ensure_ascii=False), source_id),
        )


def extract_local_media(
    fabric: LearningFabric, source_id: str, *, language: str = "pt",
) -> dict[str, Any]:
    """Transcribe a bounded local media source without remote STT or invented text."""
    source = fabric.source(source_id)
    if source["modality"] not in {"audio", "video"}:
        raise ValueError("local extraction requires an audio or video source")
    stored = Path(source["stored_path"])
    if not stored.exists() and source["metadata"].get("original_retention", {}).get("status") in {"expired", "expiring"}:
        from plugins.mission_control.learning_github_source import _check_cited_source

        _check_cited_source(source)
        if source["extraction_status"] == "transcribed_local":
            return source
        raise ValueError("original media expired; reingest the original to extract speech")
    if not stored.is_file() or stored.stat().st_size > MAX_MEDIA_BYTES:
        raise LearningEvidenceIntegrityError("stored source is missing, oversized, or changed")
    digest = hashlib.sha256()
    with stored.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != source["source_hash"]:
        raise LearningEvidenceIntegrityError("stored source is missing or changed")
    if source["extraction_status"] == "transcript_supplied":
        raise ValueError("source already has a supplied transcript")
    transcript_path = source.get("transcript_path")
    if source["extraction_status"] == "transcribed_local":
        check_speech_timing(source)
        transcript = Path(transcript_path) if transcript_path else None
        if transcript and transcript.is_file() and hashlib.sha256(transcript.read_bytes()).hexdigest() == source["transcript_hash"]:
            return source
        raise LearningEvidenceIntegrityError("stored transcript has changed")
    metadata = dict(source["metadata"])
    try:
        ffmpeg, ffprobe = _media_binary("ffmpeg"), _media_binary("ffprobe")
        if not ffmpeg:
            raise ValueError("ffmpeg is required for local media extraction")
        duration = _duration(stored, ffprobe)
        with TemporaryDirectory(prefix="nara-learning-media-") as temp:
            audio = Path(temp) / "audio.wav"
            result = subprocess.run(
                [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                 "-i", str(stored), "-vn", "-ac", "1", "-ar", "16000",
                 "-c:a", "pcm_s16le", str(audio)],
                capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
                timeout=min(300, max(30, duration * 2)),
            )
            if result.returncode or not audio.is_file() or audio.stat().st_size == 0:
                raise ValueError(f"ffmpeg could not extract audio: {result.stderr[-300:]}")
            from tools.transcription_tools import transcribe_audio_local_fallback

            transcription = transcribe_audio_local_fallback(str(audio), language=language)
            if not transcription.get("success") or not str(transcription.get("transcript") or "").strip():
                raise ValueError(str(transcription.get("error") or "local STT returned an empty transcript"))
        content = str(transcription["transcript"]).strip().encode("utf-8")
        transcript_hash, archived = fabric._store(content)
        metadata.pop("local_extraction_error", None)
        metadata["local_extraction"] = {
            "provider": transcription.get("provider"),
            "language_requested": language,
            "source_hash": source["source_hash"],
            "duration_seconds": duration,
            "extracted_at": utc_now(),
            "timing": archive_speech_timing(fabric, source, transcription, duration),
        }
        extracted_text = content.decode("utf-8")
        frame_ocr = metadata.get("frame_ocr", {})
        if source["modality"] == "video" and frame_ocr.get("status") == "complete":
            # Preserve existing screen-quote offsets when speech arrives later.
            extracted_text = "\n".join(part for part in (source["extracted_text"], extracted_text) if part)
            frame_ocr["fused_text_hash"] = hashlib.sha256(extracted_text.encode()).hexdigest()
        with transaction(fabric._connect(), immediate=True) as conn:
            conn.execute(
                """UPDATE learning_sources SET extraction_status = 'transcribed_local',
                   extracted_text = ?, transcript_hash = ?, transcript_path = ?, metadata_json = ?
                   WHERE source_id = ?""",
                (extracted_text, transcript_hash, str(archived),
                 json.dumps(metadata, sort_keys=True, ensure_ascii=False), source_id),
            )
        return fabric.source(source_id)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        _record_error(fabric, source_id, metadata, str(exc))
        raise ValueError(f"local media extraction failed: {exc}") from exc
