from types import SimpleNamespace

from tools import transcription_tools as stt


def test_local_backend_retains_times_only_for_accepted_speech(monkeypatch):
    rows = [
        SimpleNamespace(text=" Texto real. ", start=0.2, end=0.8, no_speech_prob=0.1, avg_logprob=-0.1),
        SimpleNamespace(text="silence hallucination", start=0.8, end=1.0, no_speech_prob=0.99, avg_logprob=-4),
    ]
    model = SimpleNamespace(supported_languages=["pt"], transcribe=lambda *a, **kw: (
        iter(rows), SimpleNamespace(language="pt", duration=1.0)))
    monkeypatch.setattr(stt, "_HAS_FASTER_WHISPER", True)
    monkeypatch.setattr(stt, "_get_or_load_local_model", lambda *a: model)
    monkeypatch.setattr(stt, "_load_stt_config", lambda: {"local": {"idle_unload_seconds": 0}})
    monkeypatch.setattr(stt, "_start_idle_unload_watcher", lambda *a: None)
    result = stt._transcribe_local("unused.wav", "base", language="pt")
    assert result["success"]
    assert result["transcript"] == "Texto real."
    assert result["speech_segments"] == [{"start": 0.2, "end": 0.8, "text": "Texto real."}]
