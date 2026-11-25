from __future__ import annotations

from plugins.mission_control import voice_bridge
from plugins.mission_control.contracts import Mission
from plugins.mission_control.store import MissionStore


def test_wake_reuses_active_text_mission_and_transcript_is_receipted(tmp_path, monkeypatch):
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-1", objective="build", completion_criteria=["built"],
        session_id="session-1",
    ))
    store.bind_goal("mission-1", {
        "session_id": "session-1", "goal": "build", "authority": "mission_control",
    })
    monkeypatch.setattr(MissionStore, "open_default", classmethod(lambda cls: store))

    decision = voice_bridge.on_voice_wake(
        session_id="session-1", request_id="wake-1", phrase="Ei, Nara")
    voice_bridge.on_voice_transcript(
        session_id="session-1", request_id="utterance-1", transcript="continue o projeto")

    mission = store.get("mission-1")
    assert decision["reuse_session"] is True
    assert [event["presence"] for event in mission.voice_events.values()] == ["listening", "thinking"]
    transcript_event = list(mission.voice_events.values())[1]
    assert "transcript" not in transcript_event
    assert transcript_event["transcript_chars"] == len("continue o projeto")
    assert transcript_event["intent"] == "request"


def test_barge_in_correction_cancel_and_reconnect_are_distinct(tmp_path, monkeypatch):
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-voice", objective="voice task", completion_criteria=["done"]))
    store.bind_goal("mission-voice", {"session_id": "session-voice"})
    monkeypatch.setattr(MissionStore, "open_default", classmethod(lambda cls: store))

    voice_bridge.on_voice_transcript(
        session_id="session-voice", transcript="na verdade use o arquivo B",
        surface="cli", barge_in=True, request_id="correction")
    reconnect = voice_bridge.record_presence(
        "session-voice", voice_bridge.PresenceState.RECONNECTING,
        provider="webrtc", request_id="reconnect")

    mission = store.get("mission-voice")
    events = list(mission.voice_events.values())
    assert events[0]["intent"] == "correction"
    assert reconnect["presence"] == "reconnecting"
    assert voice_bridge.classify_voice_intent("pare", barge_in=True).value == "cancel_speech"
    assert voice_bridge.classify_voice_intent(
        "cancele a missão", barge_in=True).value == "cancel_mission"
    assert store.get("mission-voice").status.value == "draft"
