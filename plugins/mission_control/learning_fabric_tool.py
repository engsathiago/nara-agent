"""Agent-facing Learning Fabric ingestion with optional local media transcription."""

from __future__ import annotations

from typing import Any

from plugins.mission_control.learning_fabric import LearningFabric, MODALITIES
from plugins.mission_control.learning_github_source import verify_quoted_repository
from plugins.mission_control.learning_media import extract_local_media
from plugins.mission_control.learning_video_ocr import extract_video_local, extract_video_screen_text


LEARNING_INGEST_SCHEMA = {
    "name": "nara_learning_ingest",
    "description": "Archive a local source; optionally extract speech and video screen text locally.",
    "parameters": {"type": "object", "properties": {
        "path": {"type": "string"},
        "modality": {"type": "string", "enum": sorted(MODALITIES)},
        "source_uri": {"type": "string"}, "version": {"type": "string"},
        "license_name": {"type": "string"}, "transcript_path": {"type": "string"},
        "extract_local": {"type": "boolean"},
        "language": {"type": "string"},
    }, "required": ["path", "modality"]},
}


def learning_ingest_tool(
    path: str, modality: str, source_uri: str = "", version: str = "",
    license_name: str = "", transcript_path: str = "", extract_local: bool = False,
    language: str = "pt",
    **_: Any,
) -> dict[str, Any]:
    fabric = LearningFabric.open_default()
    source = fabric.ingest_file(
        path, modality=modality, source_uri=source_uri or None, version=version or None,
        license_name=license_name or None, transcript_path=transcript_path or None,
    )
    if extract_local:
        if modality == "video":
            return extract_video_local(fabric, source["source_id"], language=language)
        return extract_local_media(fabric, source["source_id"], language=language)
    return source


FRAME_EXTRACT_SCHEMA = {
    "name": "nara_learning_frame_extract",
    "description": "Extract local on-screen text and archived frame evidence from a video source.",
    "parameters": {"type": "object", "properties": {
        "source_id": {"type": "string"},
    }, "required": ["source_id"]},
}


def learning_frame_extract_tool(source_id: str, **_: Any) -> dict[str, Any]:
    return extract_video_screen_text(LearningFabric.open_default(), source_id)


REPOSITORY_VERIFY_SCHEMA = {
    "name": "nara_learning_repo_verify",
    "description": "Verify a source-quoted public GitHub repository identity at a pinned commit.",
    "parameters": {"type": "object", "properties": {
        "source_id": {"type": "string"}, "quote": {"type": "string"},
    }, "required": ["source_id", "quote"]},
}


def learning_repo_verify_tool(source_id: str, quote: str, **_: Any) -> dict[str, Any]:
    return verify_quoted_repository(LearningFabric.open_default(), source_id, quote)


CLAIM_PROPOSE_SCHEMA = {
    "name": "nara_learning_claim_propose",
    "description": "Propose a candidate claim with an exact quote from an archived source or transcript.",
    "parameters": {"type": "object", "properties": {
        "source_id": {"type": "string"}, "claim": {"type": "string"},
        "quote": {"type": "string"}, "confidence": {"type": "number"},
    }, "required": ["source_id", "claim", "quote"]},
}


def learning_claim_propose_tool(
    source_id: str, claim: str, quote: str, confidence: float = 0.7, **_: Any,
) -> dict[str, Any]:
    return LearningFabric.open_default().propose_claim(
        source_id, claim, quote, confidence=confidence,
    )


def register_learning_tools(ctx: Any, adapt: Any) -> None:
    ctx.register_tool(
        name="nara_learning_ingest", toolset="mission_control",
        schema=LEARNING_INGEST_SCHEMA, handler=adapt(learning_ingest_tool), emoji="📚")
    ctx.register_tool(
        name="nara_learning_claim_propose", toolset="mission_control",
        schema=CLAIM_PROPOSE_SCHEMA, handler=adapt(learning_claim_propose_tool), emoji="📝")
    ctx.register_tool(
        name="nara_learning_frame_extract", toolset="mission_control",
        schema=FRAME_EXTRACT_SCHEMA, handler=adapt(learning_frame_extract_tool), emoji="🎞️")
    ctx.register_tool(
        name="nara_learning_repo_verify", toolset="mission_control",
        schema=REPOSITORY_VERIFY_SCHEMA, handler=adapt(learning_repo_verify_tool), emoji="🔎")
