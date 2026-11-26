"""Verify a video-quoted repository name against GitHub's public REST API."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nara_cli.sqlite_util import transaction
from plugins.mission_control.contracts import utc_now

if TYPE_CHECKING:
    from plugins.mission_control.learning_fabric import LearningFabric


REPOSITORY_QUOTE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+)", re.IGNORECASE,
)
MAX_RESPONSE_BYTES = 1_000_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise ValueError("GitHub API redirect refused")


def _github_json(url: str) -> Any:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "api.github.com":
        raise ValueError("repository verification only permits the GitHub API")
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Nara-Learning-Fabric/1",
    })
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=10) as response:
            final = urllib.parse.urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "api.github.com":
                raise ValueError("GitHub API redirected outside its official host")
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"GitHub API returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"GitHub API unavailable: {exc.reason}") from exc
    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError("GitHub API response exceeds the evidence limit")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub API returned invalid JSON") from exc


def _quoted_repository(quote: str) -> str:
    match = REPOSITORY_QUOTE.search(quote)
    if match is None:
        raise ValueError("quote must contain a github.com/owner/repository URL")
    owner = match.group(1)
    repo = match.group(2).rstrip(".,;:!?)]}").removesuffix(".git")
    if not repo:
        raise ValueError("quote has no repository name")
    return f"{owner}/{repo}"


def _check_cited_source(source: dict[str, Any]) -> None:
    """Reject a citation when its archived media or extraction proof changed."""
    from plugins.mission_control.learning_speech_timing import check_speech_timing

    check_speech_timing(source)
    original = Path(source["stored_path"])
    digest = hashlib.sha256()
    try:
        with original.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError("cited source archive is missing") from exc
    if digest.hexdigest() != source["source_hash"]:
        raise ValueError("cited source archive has changed")
    transcript_path = source.get("transcript_path")
    if transcript_path:
        transcript = Path(transcript_path)
        if not transcript.is_file() or hashlib.sha256(transcript.read_bytes()).hexdigest() != source["transcript_hash"]:
            raise ValueError("cited transcript archive has changed")
    frame_ocr = source["metadata"].get("frame_ocr", {})
    if frame_ocr.get("status") == "complete":
        fused = hashlib.sha256((source["extracted_text"] or "").encode()).hexdigest()
        if fused != frame_ocr.get("fused_text_hash"):
            raise ValueError("cited screen text has changed")
        for item in frame_ocr.get("evidence", []):
            frame = Path(item["frame_path"])
            if not frame.is_file() or hashlib.sha256(frame.read_bytes()).hexdigest() != item["frame_hash"]:
                raise ValueError("cited video frame archive has changed")


def verify_quoted_repository(
    fabric: LearningFabric, source_id: str, quote: str,
) -> dict[str, Any]:
    """Verify only repository identity/existence, never a video's feature claims."""
    source = fabric.source(source_id)
    _check_cited_source(source)
    if quote not in (source["extracted_text"] or ""):
        raise ValueError("repository quote is not present in the extracted source")
    requested = _quoted_repository(quote)
    owner, repo = requested.split("/", 1)
    base = f"https://api.github.com/repos/{owner}/{repo}"
    repository = _github_json(base)
    if not isinstance(repository, dict) or str(repository.get("full_name", "")).casefold() != requested.casefold():
        raise ValueError("GitHub repository identity does not match the cited URL")
    if repository.get("private") or repository.get("visibility") not in (None, "public"):
        raise ValueError("cited repository is not public")
    commits = _github_json(f"{base}/commits?per_page=1")
    if not isinstance(commits, list) or not commits or not isinstance(commits[0], dict):
        raise ValueError("GitHub repository has no readable commit to pin")
    head = commits[0]
    sha = str(head.get("sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("GitHub API returned an invalid commit SHA")
    snapshot = {"repository_response": repository, "head_response": head}
    content = json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode("utf-8")
    snapshot_hash, stored = fabric._store(content)
    if hashlib.sha256(stored.read_bytes()).hexdigest() != snapshot_hash:
        raise ValueError("archived GitHub response has changed")
    now = utc_now()
    record = {
        "kind": "github_repository", "source_id": source_id, "quote": quote,
        "full_name": repository["full_name"], "url": repository.get("html_url"),
        "default_branch": repository.get("default_branch"), "head_sha": sha,
        "license": (repository.get("license") or {}).get("spdx_id"),
        "snapshot_hash": snapshot_hash, "snapshot_path": str(stored),
        "verified_at": now, "verifies": "repository identity and existence at the pinned commit only",
    }
    metadata = dict(source["metadata"])
    prior = list(metadata.get("primary_sources") or [])
    if not any(item.get("snapshot_hash") == snapshot_hash and item.get("quote") == quote for item in prior):
        prior.append(record)
    metadata["primary_sources"] = prior
    with transaction(fabric._connect(), immediate=True) as conn:
        conn.execute(
            "UPDATE learning_sources SET metadata_json = ? WHERE source_id = ?",
            (json.dumps(metadata, sort_keys=True, ensure_ascii=False), source_id),
        )
    claim = fabric.propose_claim(
        source_id, f"Official GitHub repository {repository['full_name']} exists at {sha}", quote,
    )
    verified = fabric.verify_claim(
        claim["claim_id"], verifier_id="github-public-rest-v1",
        evidence_artifact_ids=[f"sha256:{snapshot_hash}"], accepted=True,
    )
    return {"claim": verified, "primary_source": record}
