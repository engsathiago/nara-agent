from __future__ import annotations

import json
import wave

from evals.voice_presence.benchmark import evaluate


def _wav(path, value):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(int(value).to_bytes(2, "little", signed=True) * 1280)


class _Detector:
    frame_length = 1280

    def process(self, frame):
        return max(frame) > 0


def test_benchmark_measures_without_promoting_a_tiny_dataset(tmp_path):
    _wav(tmp_path / "positive.wav", 100)
    _wav(tmp_path / "negative.wav", 0)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"samples": [
        {"id": "p1", "path": "positive.wav", "wake": True},
        {"id": "n1", "path": "negative.wav", "wake": False},
    ]}), encoding="utf-8")

    report = evaluate(manifest, _Detector)

    assert report["detection_rate"] == 1.0
    assert report["false_fires"] == 0
    assert report["promotion_ready"] is False
