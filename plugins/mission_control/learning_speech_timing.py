"""Persist native speech timings without inventing alignment for plain transcripts."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def archive_speech_timing(fabric, source, transcription, duration: float) -> dict[str, Any]:
    rows = transcription.get("speech_segments")
    if not rows:
        return {"status": "unavailable", "reason": "backend supplied no segment timestamps"}
    previous = -1.0
    clean = []
    for row in rows:
        start, end = float(row["start"]), float(row["end"])
        text = str(row["text"]).strip()
        if not (math.isfinite(start) and math.isfinite(end)
                and previous <= start < end <= duration + 0.5 and start >= 0 and text):
            raise ValueError("invalid speech segment timestamps")
        clean.append({"start": start, "end": end, "text": text})
        previous = start
    if " ".join(row["text"] for row in clean) != str(transcription["transcript"]).strip():
        raise ValueError("speech segment text differs from transcript")
    payload = {"schema_version": 1, "source_hash": source["source_hash"],
               "provider": transcription.get("provider"), "segments": clean}
    digest, path = fabric._store(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode())
    return {"status": "available", "sha256": digest, "path": str(path), "segments": clean}


def check_speech_timing(source: dict[str, Any]) -> None:
    timing = source["metadata"].get("local_extraction", {}).get("timing", {})
    if timing.get("status") != "available":
        return
    path = Path(timing["path"])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != timing["sha256"]:
        raise ValueError("archived speech timestamps have changed")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload["source_hash"] != source["source_hash"] or payload["segments"] != timing["segments"]:
        raise ValueError("archived speech timestamps do not match source metadata")
