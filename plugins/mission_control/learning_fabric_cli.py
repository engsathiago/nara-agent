"""Operator commands for the local Learning Fabric media pipeline."""

from __future__ import annotations

import argparse
from typing import Any

from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_media import extract_local_media


def register_media_cli(actions: Any) -> None:
    ingest = actions.add_parser("learn-media-ingest", help="Archive and locally transcribe audio/video")
    ingest.add_argument("path")
    ingest.add_argument("--modality", choices=["audio", "video"], required=True)
    ingest.add_argument("--source-uri")
    ingest.add_argument("--version")
    ingest.add_argument("--license-name")
    ingest.add_argument("--extract-local", action="store_true")
    ingest.add_argument("--language", default="pt")

    show = actions.add_parser("learn-media-show", help="Show stored source and transcript provenance")
    show.add_argument("source_id")

    propose = actions.add_parser("learn-media-propose", help="Propose an inactive, source-quoted claim")
    propose.add_argument("source_id")
    propose.add_argument("claim")
    propose.add_argument("--quote", required=True)


def media_command(args: argparse.Namespace) -> dict[str, Any]:
    fabric = LearningFabric.open_default()
    if args.mission_action == "learn-media-show":
        try:
            return fabric.source(args.source_id)
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
    return extract_local_media(fabric, source["source_id"], language=args.language) if args.extract_local else source
