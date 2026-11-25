"""Bind wake/transcript presence to the same durable text mission."""

from __future__ import annotations

import hashlib
import uuid
from enum import StrEnum
from typing import Any

from plugins.mission_control.contracts import MissionStatus, utc_now
from plugins.mission_control.ledger import mission_for_session
from plugins.mission_control.store import MissionStore


class PresenceState(StrEnum):
    ARMED = "armed"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    FOLLOWUP = "followup"
    RECONNECTING = "reconnecting"
    MIC_UNAVAILABLE = "mic_unavailable"


class VoiceIntent(StrEnum):
    REQUEST = "request"
    CORRECTION = "correction"
    CANCEL_SPEECH = "cancel_speech"
    CANCEL_MISSION = "cancel_mission"


def classify_voice_intent(transcript: str, *, barge_in: bool) -> VoiceIntent:
    normalized = " ".join(transcript.casefold().split())
    if any(phrase in normalized for phrase in (
        "cancele a missão", "cancela a missão", "cancel mission", "aborte a missão")):
        return VoiceIntent.CANCEL_MISSION
    if barge_in and normalized in {"pare", "para", "stop", "chega", "silêncio"}:
        return VoiceIntent.CANCEL_SPEECH
    if barge_in or normalized.startswith(("correção", "corrigindo", "na verdade", "mude para")):
        return VoiceIntent.CORRECTION
    return VoiceIntent.REQUEST


def _event_id(kind: str, session_id: str, request_id: str) -> str:
    return hashlib.sha256(f"{kind}\0{session_id}\0{request_id}".encode()).hexdigest()[:24]


def on_voice_wake(
    session_id: str = "", phrase: str = "Ei, Nara", surface: str = "cli",
    request_id: str = "", **_: Any,
) -> dict[str, Any] | None:
    if not session_id:
        return None
    store = MissionStore.open_default()
    mission = mission_for_session(store, session_id)
    if mission is None:
        return {"reuse_session": False, "presence": PresenceState.LISTENING.value}
    stable_request = request_id or uuid.uuid4().hex
    voice_event_id = _event_id("wake", session_id, stable_request)
    store.record_voice_event(
        mission.mission_id,
        {
            "voice_event_id": voice_event_id,
            "kind": "wake",
            "session_id": session_id,
            "surface": surface,
            "phrase": phrase,
            "presence": PresenceState.LISTENING.value,
            "observed_at": utc_now(),
        },
        idempotency_key=f"voice:{voice_event_id}",
    )
    return {
        "reuse_session": mission.status not in {
            MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED,
        },
        "mission_id": mission.mission_id,
        "presence": PresenceState.LISTENING.value,
    }


def on_voice_transcript(
    session_id: str = "", transcript: str = "", surface: str = "cli", barge_in: bool = False,
    request_id: str = "", **_: Any,
) -> None:
    if not (session_id and transcript):
        return
    store = MissionStore.open_default()
    mission = mission_for_session(store, session_id)
    if mission is None:
        return
    digest = hashlib.sha256(transcript.encode()).hexdigest()
    intent = classify_voice_intent(transcript, barge_in=barge_in)
    stable_request = request_id or f"{digest}:{len(mission.voice_events)}"
    voice_event_id = _event_id("transcript", session_id, stable_request)
    store.record_voice_event(
        mission.mission_id,
        {
            "voice_event_id": voice_event_id,
            "kind": "barge_in" if barge_in else "transcript",
            "intent": intent.value,
            "session_id": session_id,
            "surface": surface,
            "presence": PresenceState.THINKING.value,
            "transcript_sha256": digest,
            "transcript_chars": len(transcript),
            "observed_at": utc_now(),
        },
        idempotency_key=f"voice:{voice_event_id}",
    )


def record_presence(
    session_id: str, presence: PresenceState | str, *, surface: str = "voice",
    request_id: str = "", provider: str = "",
) -> dict[str, Any] | None:
    store = MissionStore.open_default()
    mission = mission_for_session(store, session_id)
    if mission is None:
        return None
    state = PresenceState(presence)
    stable = request_id or uuid.uuid4().hex
    identity = _event_id(f"presence:{state.value}", session_id, stable)
    event = {
        "voice_event_id": identity, "kind": "presence", "session_id": session_id,
        "surface": surface, "presence": state.value, "provider": provider or None,
        "observed_at": utc_now(),
    }
    store.record_voice_event(mission.mission_id, event, idempotency_key=f"voice:{identity}")
    return {"mission_id": mission.mission_id, **event}


VOICE_PRESENCE_SCHEMA = {
    "name": "nara_voice_presence",
    "description": "Record voice reconnect, speaking, follow-up, armed, or microphone state on the same mission.",
    "parameters": {"type": "object", "properties": {
        "session_id": {"type": "string"},
        "presence": {"type": "string", "enum": [state.value for state in PresenceState]},
        "surface": {"type": "string"}, "request_id": {"type": "string"},
        "provider": {"type": "string"},
    }, "required": ["session_id", "presence"]},
}


def voice_presence_tool(
    session_id: str, presence: str, surface: str = "voice", request_id: str = "",
    provider: str = "", **_: Any,
) -> dict[str, Any]:
    result = record_presence(
        session_id, presence, surface=surface, request_id=request_id, provider=provider)
    return result or {"error": "no active mission is bound to this session"}
