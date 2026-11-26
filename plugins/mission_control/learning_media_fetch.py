"""Bounded acquisition of one public video for the Learning Fabric."""

from __future__ import annotations

import shutil
import subprocess
import sys
import urllib.parse
from importlib.util import find_spec
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

from plugins.mission_control.learning_media import MAX_MEDIA_BYTES, _duration

if TYPE_CHECKING:
    from plugins.mission_control.learning_fabric import LearningFabric


SUPPORTED_HOSTS = frozenset({
    "instagram.com", "www.instagram.com", "youtube.com", "www.youtube.com",
    "m.youtube.com", "youtu.be", "vimeo.com", "www.vimeo.com",
})


def _extractor_command() -> list[str] | None:
    binary = shutil.which("yt-dlp")
    if binary:
        return [binary]
    if find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    return None


def _public_media_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in SUPPORTED_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("media fetch requires a supported public HTTPS video URL")
    if parsed.hostname in {"instagram.com", "www.instagram.com"}:
        segments = [part for part in parsed.path.split("/") if part]
        if len(segments) != 2 or segments[0] not in {"p", "reel"}:
            raise ValueError("Instagram fetch requires one public post or Reel URL")
    return urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))


def media_fetch_status() -> dict[str, Any]:
    command = _extractor_command()
    probe = shutil.which("ffprobe")
    return {
        "status": "available" if command and probe else "unavailable",
        "provider": "yt-dlp", "command": command, "ffprobe": probe,
        "scope": "one public HTTPS video; no browser cookies or user configuration",
        "supported_hosts": sorted(SUPPORTED_HOSTS),
    }


def fetch_public_media(
    fabric: LearningFabric, url: str, *, extract_local: bool = False, language: str = "pt",
) -> dict[str, Any]:
    """Acquire one bounded video and feed the same local ingestion path as files."""
    canonical_url = _public_media_url(url)
    extractor = _extractor_command()
    if not extractor:
        raise ValueError("yt-dlp is unavailable; install the media-fetch extra to fetch public media URLs")
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise ValueError("ffprobe is unavailable; install ffmpeg to validate media duration")
    with TemporaryDirectory(prefix="nara-learning-fetch-") as temp:
        root = Path(temp)
        command = [
            *extractor, "--ignore-config", "--no-playlist",
            "--no-cookies-from-browser", "--no-cache-dir", "--no-exec",
            "--no-progress", "--no-warnings", "--no-part", "--no-continue",
            "--no-mtime", "--socket-timeout", "15", "--retries", "2",
            "--fragment-retries", "2", "--max-filesize", str(MAX_MEDIA_BYTES),
            "--match-filters", "!is_live",
            "--output", str(root / "source.%(ext)s"), "--print", "after_move:filepath",
            "--", canonical_url,
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, check=False, timeout=360,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("public media download timed out") from exc
        if result.returncode:
            detail = result.stderr.strip().splitlines()[-1:] or ["download failed"]
            raise ValueError(f"public media download failed: {detail[0][:300]}")
        paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(paths) != 1:
            raise ValueError("media extractor did not return exactly one downloaded file")
        media = Path(paths[0]).resolve()
        if not media.is_relative_to(root.resolve()) or not media.is_file():
            raise ValueError("media extractor output escaped its temporary directory")
        if media.stat().st_size > MAX_MEDIA_BYTES:
            raise ValueError("public media exceeds the local ingestion size limit")
        _duration(media, ffprobe)
        source = fabric.ingest_file(
            media, modality="video", source_uri=canonical_url,
            metadata={"acquisition": {"provider": "yt-dlp", "kind": "public_url"}},
        )
    if not extract_local:
        return source
    from plugins.mission_control.learning_video_ocr import extract_video_local

    return extract_video_local(fabric, source["source_id"], language=language)
