"""Bounded local video frame OCR with archived frame evidence."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

from nara_cli.sqlite_util import transaction
from plugins.mission_control.contracts import utc_now
from plugins.mission_control.learning_media import (
    MAX_MEDIA_BYTES, LearningEvidenceIntegrityError, _duration, _media_binary, extract_local_media,
)

if TYPE_CHECKING:
    from plugins.mission_control.learning_fabric import LearningFabric


MAX_FRAMES = 60
MAX_EVIDENCE_FRAMES = 20
MAX_FRAME_WIDTH = 1280


def _ocr_backend(frames: list[Path]) -> tuple[str, list[dict[str, Any]]]:
    helper = Path(__file__).with_name("vision_ocr.swift")
    swift = shutil.which("swift") if platform.system() == "Darwin" else None
    if swift and helper.is_file():
        result = subprocess.run(
            [swift, str(helper), *(str(frame) for frame in frames)],
            capture_output=True, text=True, check=False, timeout=180,
        )
        if result.returncode:
            raise ValueError(f"macOS Vision OCR failed: {result.stderr[-300:]}")
        try:
            rows = [json.loads(line) for line in result.stdout.splitlines()]
        except json.JSONDecodeError as exc:
            raise ValueError("macOS Vision OCR returned invalid JSON") from exc
        if len(rows) != len(frames) or any(row.get("error") for row in rows):
            raise ValueError("macOS Vision OCR did not process every frame")
        return "macos_vision", rows
    tesseract = shutil.which("tesseract")
    if not tesseract:
        raise ValueError("local video OCR requires macOS Swift Vision or Tesseract")
    rows = []
    for frame in frames:
        result = subprocess.run(
            [tesseract, str(frame), "stdout", "-l", "por+eng"],
            capture_output=True, text=True, check=False, timeout=20,
        )
        if result.returncode:
            raise ValueError(f"Tesseract OCR failed: {result.stderr[-300:]}")
        rows.append({"path": str(frame), "text": result.stdout.strip(), "confidence": None})
    return "tesseract", rows


def _verified_video(fabric: LearningFabric, source_id: str) -> tuple[dict[str, Any], Path]:
    source = fabric.source(source_id)
    if source["modality"] != "video":
        raise ValueError("frame OCR requires a video source")
    stored = Path(source["stored_path"])
    if not stored.is_file() or stored.stat().st_size > MAX_MEDIA_BYTES:
        raise LearningEvidenceIntegrityError("stored video is missing or oversized")
    digest = hashlib.sha256()
    with stored.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != source["source_hash"]:
        raise LearningEvidenceIntegrityError("stored video hash does not match source")
    return source, stored


def _sample_frames(stored: Path, duration: float, ffmpeg: str, root: Path) -> tuple[list[Path], list[float]]:
    interval = max(0.5, duration / MAX_FRAMES)
    times = [round(index * interval, 3) for index in range(MAX_FRAMES) if index * interval < duration]
    frames: list[Path] = []
    for index, seconds in enumerate(times):
        frame = root / f"frame-{index:03d}.png"
        result = subprocess.run(
            [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
             "-ss", str(seconds), "-i", str(stored), "-frames:v", "1",
             "-vf", f"scale='min({MAX_FRAME_WIDTH},iw)':-2", str(frame)],
            capture_output=True, text=True, check=False, timeout=20,
        )
        if result.returncode:
            raise ValueError(f"ffmpeg frame extraction failed: {result.stderr[-300:]}")
        if frame.is_file() and frame.stat().st_size:
            frames.append(frame)
        else:
            break
    return frames, times[:len(frames)]


def extract_video_screen_text(fabric: LearningFabric, source_id: str) -> dict[str, Any]:
    """OCR sampled frames; only text-bearing frame evidence is retained."""
    source, stored = _verified_video(fabric, source_id)
    metadata = dict(source["metadata"])
    if metadata.get("frame_ocr", {}).get("status") == "complete":
        frame_ocr = metadata["frame_ocr"]
        fused_hash = hashlib.sha256((source["extracted_text"] or "").encode()).hexdigest()
        if fused_hash != frame_ocr.get("fused_text_hash"):
            raise LearningEvidenceIntegrityError("archived screen text has changed")
        for item in frame_ocr.get("evidence", []):
            frame = Path(item["frame_path"])
            if not frame.is_file() or hashlib.sha256(frame.read_bytes()).hexdigest() != item["frame_hash"]:
                raise LearningEvidenceIntegrityError("archived OCR frame has changed")
        return source
    try:
        ffmpeg, ffprobe = _media_binary("ffmpeg"), _media_binary("ffprobe")
        if not ffmpeg:
            raise ValueError("ffmpeg is required for local video OCR")
        duration = _duration(stored, ffprobe)
        with TemporaryDirectory(prefix="nara-learning-frames-") as temp:
            frames, times = _sample_frames(stored, duration, ffmpeg, Path(temp))
            if not frames:
                raise ValueError("video contains no readable frames")
            provider, rows = _ocr_backend(frames)
            evidence = []
            seen_text = set()
            for frame, seconds, row in zip(frames, times, rows, strict=True):
                frame_text = str(row.get("text") or "").strip()
                if not frame_text or frame_text in seen_text or len(evidence) >= MAX_EVIDENCE_FRAMES:
                    continue
                seen_text.add(frame_text)
                frame_hash, frame_path = fabric._store(frame.read_bytes())
                evidence.append({
                    "seconds": seconds, "text": frame_text,
                    "confidence": row.get("confidence"),
                    "frame_hash": frame_hash, "frame_path": str(frame_path),
                })
        if not evidence:
            raise ValueError("local OCR found no readable on-screen text")
        transcript = ""
        if source["transcript_path"]:
            transcript_bytes = Path(source["transcript_path"]).read_bytes()
            if hashlib.sha256(transcript_bytes).hexdigest() != source["transcript_hash"]:
                raise LearningEvidenceIntegrityError("stored transcript hash does not match source")
            transcript = transcript_bytes.decode("utf-8")
        screen_text = "\n".join(
            f"[screen @ {item['seconds']:.3f}s] {item['text']}" for item in evidence
        )
        fused = "\n".join(part for part in (transcript, screen_text) if part)
        metadata.pop("frame_ocr_error", None)
        metadata["frame_ocr"] = {
            "status": "complete", "provider": provider,
            "source_hash": source["source_hash"], "sampled_frames": len(frames),
            "duration_seconds": duration, "evidence": evidence,
            "fused_text_hash": hashlib.sha256(fused.encode()).hexdigest(),
            "extracted_at": utc_now(),
        }
        status = source["extraction_status"]
        if status == "needs_extraction":
            status = "screen_text_local"
        with transaction(fabric._connect(), immediate=True) as conn:
            conn.execute(
                """UPDATE learning_sources SET extraction_status = ?, extracted_text = ?,
                   metadata_json = ? WHERE source_id = ?""",
                (status, fused, json.dumps(metadata, sort_keys=True, ensure_ascii=False), source_id),
            )
        return fabric.source(source_id)
    except LearningEvidenceIntegrityError:
        raise
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        metadata["frame_ocr_error"] = str(exc)
        metadata["frame_ocr_attempted_at"] = utc_now()
        with transaction(fabric._connect(), immediate=True) as conn:
            conn.execute(
                "UPDATE learning_sources SET metadata_json = ? WHERE source_id = ?",
                (json.dumps(metadata, sort_keys=True, ensure_ascii=False), source_id),
            )
        raise ValueError(f"local video OCR failed: {exc}") from exc


def extract_video_local(
    fabric: LearningFabric, source_id: str, *, language: str = "pt",
) -> dict[str, Any]:
    """Run speech and screen extraction independently; retain partial evidence."""
    errors = []
    for operation in (lambda: extract_local_media(fabric, source_id, language=language),
                      lambda: extract_video_screen_text(fabric, source_id)):
        try:
            operation()
        except LearningEvidenceIntegrityError:
            raise
        except ValueError as exc:
            errors.append(str(exc))
    source = fabric.source(source_id)
    if source["extraction_status"] == "needs_extraction":
        raise ValueError("; ".join(errors))
    return source
