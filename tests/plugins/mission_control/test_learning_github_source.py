"""Source-quoted GitHub repository verification and archived official evidence."""

import argparse
import hashlib
import json
import urllib.error
from pathlib import Path

import pytest

from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control.cli import mission_command, register_cli
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_github_source import _github_json, verify_quoted_repository


QUOTE = "github.com/ggml-org/whisper.cpp"
HEAD = "a" * 40


def _source(tmp_path):
    path = tmp_path / "lesson.txt"
    path.write_text(f"The screen shows {QUOTE}.")
    fabric = LearningFabric(tmp_path / "fabric")
    return fabric, fabric.ingest_file(path, modality="document")


def _official(urls):
    def get(url):
        urls.append(url)
        if url.endswith("?per_page=1"):
            return [{"sha": HEAD, "html_url": f"https://github.com/ggml-org/whisper.cpp/commit/{HEAD}"}]
        return {
            "full_name": "ggml-org/whisper.cpp", "private": False,
            "visibility": "public", "html_url": "https://github.com/ggml-org/whisper.cpp",
            "default_branch": "master", "license": {"spdx_id": "MIT"},
        }
    return get


def test_official_repository_claim_is_narrow_and_has_archived_evidence(tmp_path, monkeypatch):
    fabric, source = _source(tmp_path)
    urls = []
    monkeypatch.setattr("plugins.mission_control.learning_github_source._github_json", _official(urls))
    result = verify_quoted_repository(fabric, source["source_id"], QUOTE)
    claim, primary = result["claim"], result["primary_source"]
    assert urls == [
        "https://api.github.com/repos/ggml-org/whisper.cpp",
        "https://api.github.com/repos/ggml-org/whisper.cpp/commits?per_page=1",
    ]
    assert claim["status"] == "verified"
    assert claim["claim"] == f"Official GitHub repository ggml-org/whisper.cpp exists at {HEAD}"
    assert claim["quote"] == QUOTE
    assert claim["evidence_artifact_ids"] == [f"sha256:{primary['snapshot_hash']}"]
    stored = Path(primary["snapshot_path"])
    assert hashlib.sha256(stored.read_bytes()).hexdigest() == primary["snapshot_hash"]
    assert json.loads(stored.read_text())["repository_response"]["full_name"] == "ggml-org/whisper.cpp"
    assert len(fabric.source(source["source_id"])["metadata"]["primary_sources"]) == 1
    assert verify_quoted_repository(fabric, source["source_id"], QUOTE)["claim"]["claim_id"] == claim["claim_id"]
    assert len(fabric.source(source["source_id"])["metadata"]["primary_sources"]) == 1


def test_tampered_official_snapshot_fails_claim_read(tmp_path, monkeypatch):
    fabric, source = _source(tmp_path)
    monkeypatch.setattr("plugins.mission_control.learning_github_source._github_json", _official([]))
    result = verify_quoted_repository(fabric, source["source_id"], QUOTE)
    Path(result["primary_source"]["snapshot_path"]).write_text("altered")
    with pytest.raises(ValueError, match="archived claim evidence has changed"):
        fabric.claim(result["claim"]["claim_id"])


def test_tampered_cited_source_cannot_be_verified(tmp_path, monkeypatch):
    fabric, source = _source(tmp_path)
    Path(source["stored_path"]).write_text("altered archive")
    monkeypatch.setattr("plugins.mission_control.learning_github_source._github_json", _official([]))
    with pytest.raises(ValueError, match="cited source archive has changed"):
        verify_quoted_repository(fabric, source["source_id"], QUOTE)
    assert fabric.status()["claims"] == []


def test_wrong_or_unquoted_repository_cannot_be_verified(tmp_path, monkeypatch):
    fabric, source = _source(tmp_path)
    monkeypatch.setattr(
        "plugins.mission_control.learning_github_source._github_json",
        lambda url: {"full_name": "someone/else", "private": False},
    )
    with pytest.raises(ValueError, match="identity does not match"):
        verify_quoted_repository(fabric, source["source_id"], QUOTE)
    with pytest.raises(ValueError, match="not present"):
        verify_quoted_repository(fabric, source["source_id"], "github.com/unquoted/repo")
    assert fabric.status()["claims"] == []


def test_public_api_error_is_visible(monkeypatch):
    class FailingOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(request.full_url, 403, "rate limited", None, None)
    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: FailingOpener())
    with pytest.raises(ValueError, match="HTTP 403"):
        _github_json("https://api.github.com/repos/ggml-org/whisper.cpp")
    with pytest.raises(ValueError, match="only permits"):
        _github_json("https://not-github.example/repos/ggml-org/whisper.cpp")


def test_repository_cli_uses_same_source_and_verified_claim(tmp_path, monkeypatch, capsys):
    profile = tmp_path / "profile"
    monkeypatch.setenv("NARA_HOME", str(profile))
    token = set_nara_home_override(profile)
    try:
        path = tmp_path / "lesson.txt"
        path.write_text(f"The screen shows {QUOTE}.")
        source = LearningFabric.open_default().ingest_file(path, modality="document")
        monkeypatch.setattr("plugins.mission_control.learning_github_source._github_json", _official([]))
        parser = argparse.ArgumentParser()
        register_cli(parser)
        assert mission_command(parser.parse_args([
            "learn-repo-verify", source["source_id"], "--quote", QUOTE,
        ])) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["claim"]["status"] == "verified"
        assert result["primary_source"]["source_id"] == source["source_id"]
    finally:
        reset_nara_home_override(token)
