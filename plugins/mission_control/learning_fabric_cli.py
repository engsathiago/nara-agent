"""Operator commands for the local Learning Fabric media pipeline."""

from __future__ import annotations

import argparse
from typing import Any

from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_github_source import verify_quoted_repository
from plugins.mission_control.learning_media_fetch import fetch_public_media, media_fetch_status
from plugins.mission_control.learning_media import extract_local_media
from plugins.mission_control.learning_video_ocr import extract_video_local, extract_video_screen_text


def register_media_cli(actions: Any) -> None:
    ingest = actions.add_parser("learn-media-ingest", help="Archive and locally transcribe audio/video")
    ingest.add_argument("path")
    ingest.add_argument("--modality", choices=["audio", "video"], required=True)
    ingest.add_argument("--source-uri")
    ingest.add_argument("--version")
    ingest.add_argument("--license-name")
    ingest.add_argument("--extract-local", action="store_true")
    ingest.add_argument("--language", default="pt")

    fetch = actions.add_parser("learn-media-fetch", help="Acquire one public HTTPS video URL")
    fetch.add_argument("url")
    fetch.add_argument("--extract-local", action="store_true")
    fetch.add_argument("--language", default="pt")
    actions.add_parser("learn-media-fetch-status", help="Check public media acquisition availability")

    show = actions.add_parser("learn-media-show", help="Show stored source and transcript provenance")
    show.add_argument("source_id")

    frames = actions.add_parser("learn-media-frames", help="Extract and archive video frame OCR evidence")
    frames.add_argument("source_id")

    repository = actions.add_parser("learn-repo-verify", help="Verify a quoted repository with GitHub's public API")
    repository.add_argument("source_id")
    repository.add_argument("--quote", required=True)

    propose = actions.add_parser("learn-media-propose", help="Propose an inactive, source-quoted claim")
    propose.add_argument("source_id")
    propose.add_argument("claim")
    propose.add_argument("--quote", required=True)

    procedure = actions.add_parser(
        "learn-media-procedure", help="Propose an inactive procedure with exact media quotes; optionally attach a verified repository")
    procedure.add_argument("source_id")
    procedure.add_argument("--repo-claim")
    procedure.add_argument("--name", required=True)
    procedure.add_argument("--step", action="append", required=True)
    procedure.add_argument("--quote", action="append", required=True)


def media_command(args: argparse.Namespace) -> dict[str, Any]:
    fabric = LearningFabric.open_default()
    if args.mission_action == "learn-media-fetch-status":
        return media_fetch_status()
    if args.mission_action == "learn-media-fetch":
        return fetch_public_media(
            fabric, args.url, extract_local=args.extract_local, language=args.language,
        )
    if args.mission_action == "learn-media-show":
        try:
            return fabric.source(args.source_id)
        except KeyError as exc:
            raise ValueError(f"unknown learning source: {args.source_id}") from exc
    if args.mission_action == "learn-media-frames":
        try:
            return extract_video_screen_text(fabric, args.source_id)
        except KeyError as exc:
            raise ValueError(f"unknown learning source: {args.source_id}") from exc
    if args.mission_action == "learn-repo-verify":
        try:
            return verify_quoted_repository(fabric, args.source_id, args.quote)
        except KeyError as exc:
            raise ValueError(f"unknown learning source: {args.source_id}") from exc
    if args.mission_action == "learn-media-propose":
        try:
            return fabric.propose_claim(args.source_id, args.claim, args.quote)
        except KeyError as exc:
            raise ValueError(f"unknown learning source: {args.source_id}") from exc
    try:
        source = fabric.ingest_file(
            args.path, modality=args.modality, source_uri=args.source_uri,
            version=args.version, license_name=args.license_name,
        )
    except OSError as exc:
        raise ValueError(f"cannot read media source: {exc}") from exc
    if not args.extract_local:
        return source
    if args.modality == "video":
        return extract_video_local(fabric, source["source_id"], language=args.language)
    return extract_local_media(fabric, source["source_id"], language=args.language)
