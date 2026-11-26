import json
import shlex
import shutil
import sys
import wave
from pathlib import Path

import pytest

from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_media import extract_local_media


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="media tools unavailable")
def test_command_timestamps_reach_persistent_learning_evidence(tmp_path, monkeypatch):
    media = tmp_path / "audio.wav"
    with wave.open(str(media), "wb") as handle:
        handle.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        handle.writeframes(b"\0\0" * 16000)
    command = tmp_path / "fixture_backend.py"
    command.write_text(
        "import sys,json,wave\nfrom pathlib import Path\n"
        "with wave.open(sys.argv[1]) as audio: assert audio.getframerate()==16000\n"
        "root=Path(sys.argv[2])\n"
        "(root/'speech.txt').write_text('Check results.',encoding='utf-8')\n"
        "(root/'speech.json').write_text(json.dumps({'segments':[{'start':0.1,'end':0.9,'text':'Check results.'}]}),encoding='utf-8')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NARA_LOCAL_STT_COMMAND", f"{shlex.quote(sys.executable)} {shlex.quote(str(command))} {{input_path}} {{output_dir}}")
    monkeypatch.setattr("tools.transcription_tools._HAS_FASTER_WHISPER", False)
    fabric = LearningFabric(tmp_path / "fabric")
    source = fabric.ingest_file(media, modality="audio")
    extracted = extract_local_media(fabric, source["source_id"])
    timing = extracted["metadata"]["local_extraction"]["timing"]
    assert timing["status"] == "available"
    assert timing["segments"] == [{"start": 0.1, "end": 0.9, "text": "Check results."}]
    assert Path(timing["path"]).is_file()
    assert LearningFabric(fabric.root).source(source["source_id"])["metadata"]["local_extraction"]["timing"] == timing
