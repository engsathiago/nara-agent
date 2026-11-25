"""Dataset-driven wake-word benchmark; never promotes a detector without audio evidence."""

from __future__ import annotations

import argparse
import array
import json
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


@dataclass(frozen=True)
class SampleResult:
    sample_id: str
    expected_wake: bool
    detected: bool
    path: str


def load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    samples = payload.get("samples") if isinstance(payload, dict) else None
    if not isinstance(samples, list) or not samples:
        raise ValueError("voice benchmark manifest requires a non-empty samples list")
    return samples


def _pcm16(path: Path) -> array.array:
    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000:
            raise ValueError(f"{path} must be mono PCM16 at 16 kHz")
        raw = wav.readframes(wav.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    return samples


def evaluate(
    manifest_path: Path,
    detector_factory: Callable[[], Any],
) -> dict[str, Any]:
    samples = load_manifest(manifest_path)
    results = []
    for spec in samples:
        path = (manifest_path.parent / str(spec["path"])).resolve()
        detector = detector_factory()
        frame_length = int(getattr(detector, "frame_length", 1280))
        pcm = _pcm16(path)
        detected = False
        try:
            for start in range(0, len(pcm), frame_length):
                frame = pcm[start:start + frame_length]
                if len(frame) < frame_length:
                    frame.extend([0] * (frame_length - len(frame)))
                if detector.process(frame):
                    detected = True
                    break
        finally:
            close = getattr(detector, "close", None)
            if callable(close):
                close()
        results.append(SampleResult(
            sample_id=str(spec["id"]),
            expected_wake=bool(spec["wake"]),
            detected=detected,
            path=str(path),
        ))
    positives = [item for item in results if item.expected_wake]
    negatives = [item for item in results if not item.expected_wake]
    true_positive = sum(item.detected for item in positives)
    false_positive = sum(item.detected for item in negatives)
    return {
        "schema_version": 1,
        "kind": "nara.voice.wake_benchmark",
        "status": "measured",
        "positive_samples": len(positives),
        "negative_samples": len(negatives),
        "detection_rate": true_positive / len(positives) if positives else None,
        "false_fires": false_positive,
        "false_fire_rate": false_positive / len(negatives) if negatives else None,
        "promotion_ready": (
            len(positives) >= 100 and len(negatives) > 0
            and true_positive / len(positives) >= 0.95 and false_positive <= 1
        ),
        "results": [asdict(item) for item in results],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the configured Nara wake detector")
    parser.add_argument("manifest", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    from tools.wake_word import _build_engine, load_wake_word_config
    report = evaluate(args.manifest, lambda: _build_engine(load_wake_word_config()))
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(not report["promotion_ready"])


if __name__ == "__main__":
    raise SystemExit(main())
