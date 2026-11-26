import json
import shlex
import sys
import wave

import pytest

from tools.transcription_local import _transcribe_local_command


@pytest.mark.parametrize("shape", ["whisper", "whisper_cpp"])
def test_command_preserves_native_segment_times(tmp_path, monkeypatch, shape):
    audio = tmp_path / "speech.wav"
    with wave.open(str(audio), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(b"\0\0" * 16000)
    row = {"text": "Olá mundo."}
    if shape == "whisper":
        row.update(start=0.1, end=0.9)
        payload = {"segments": [row]}
    else:
        row["offsets"] = {"from": 100, "to": 900}
        payload = {"transcription": [row]}
    command = tmp_path / "backend.py"
    command.write_text(
        "import sys\nfrom pathlib import Path\n"
        "root=Path(sys.argv[1])\n"
        "(root/'speech.txt').write_text('Olá mundo.',encoding='utf-8')\n"
        f"(root/'speech.json').write_text({json.dumps(payload)!r},encoding='utf-8')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NARA_LOCAL_STT_COMMAND",
                       f"{shlex.quote(sys.executable)} {shlex.quote(str(command))} {{output_dir}}")
    result = _transcribe_local_command(str(audio), "base", language="pt")
    assert result["success"]
    assert result["speech_segments"] == [{"start": 0.1, "end": 0.9, "text": "Olá mundo."}]


@pytest.mark.parametrize("payload", [
    {"segments": [{"start": float("nan"), "end": 1, "text": "Hello"}]},
    {"segments": [{"start": 0, "end": 1, "text": "Different words"}]},
    {"transcription": [{"offsets": {"from": 900, "to": 100}, "text": "Hello"}]},
])
def test_invalid_or_mismatched_timing_is_not_accepted(tmp_path, payload):
    from tools.transcription_command_timing import read_command_transcript

    transcript = tmp_path / "speech.txt"
    transcript.write_text("Hello", encoding="utf-8")
    transcript.with_suffix(".json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="local STT"):
        read_command_transcript(transcript)
