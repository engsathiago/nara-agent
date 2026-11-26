"""Read native Whisper JSON alongside a local command's text transcript."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def read_command_transcript(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig").strip()
    sidecar = path.with_suffix(".json")
    if not sidecar.exists():
        return {"transcript": text}
    if sidecar.stat().st_size > 4_000_000:
        raise ValueError("local STT timestamp JSON exceeds 4 MB")
    payload = json.loads(sidecar.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("local STT timestamp JSON must be an object")
    if "segments" in payload:
        rows, scale = payload["segments"], 1.0
    elif "transcription" in payload:
        rows, scale = payload["transcription"], 1000.0
    else:
        raise ValueError("local STT timestamp JSON has no supported segments")
    if not isinstance(rows, list):
        raise ValueError("local STT timestamp segments must be a list")
    result = []
    previous = -1.0
    for row in rows:
        try:
            start = float(row["start"] if scale == 1 else row["offsets"]["from"]) / scale
            end = float(row["end"] if scale == 1 else row["offsets"]["to"]) / scale
            words = row["text"].strip()
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("invalid local STT timestamp segment") from exc
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end and start >= previous):
            raise ValueError("invalid local STT timestamp interval")
        previous = start
        if words:
            result.append({"start": start, "end": end, "text": words})
    joined = " ".join(row["text"] for row in result)
    if joined.split() != text.split():
        raise ValueError("local STT timestamps differ from text transcript")
    return {"transcript": joined, "speech_segments": result}
