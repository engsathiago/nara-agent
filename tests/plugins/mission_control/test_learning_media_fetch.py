"""Public video acquisition uses a bounded, temporary, cookie-free path."""

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control.cli import mission_command, register_cli
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_media_fetch import (
    _public_media_url, fetch_public_media, media_fetch_status,
)


URL = "https://www.instagram.com/reel/C123abcd/"


@pytest.mark.parametrize("url", [
    "http://www.instagram.com/reel/C123abcd/",
    "https://127.0.0.1/video.mp4",
    "https://www.instagram.com.evil.example/reel/C123abcd/",
    "https://www.instagram.com/profile/",
    "https://user:pass@www.instagram.com/reel/C123abcd/",
])
def test_rejects_nonpublic_or_nonvideo_urls(url):
    with pytest.raises(ValueError):
        _public_media_url(url)


def test_reports_missing_extractor(tmp_path, monkeypatch):
    monkeypatch.setattr("plugins.mission_control.learning_media_fetch.shutil.which", lambda name: None)
    assert media_fetch_status()["status"] == "unavailable"
    with pytest.raises(ValueError, match="yt-dlp is unavailable"):
        fetch_public_media(LearningFabric(tmp_path / "fabric"), URL)


def test_fetches_one_file_through_learning_fabric_and_removes_temp(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("plugins.mission_control.learning_media_fetch.shutil.which", lambda name: "/usr/bin/yt-dlp")
    monkeypatch.setattr("plugins.mission_control.learning_media_fetch._duration", lambda media, probe: 10.0)

    def download(command, **options):
        calls.append((command, options))
        template = command[command.index("--output") + 1]
        media = Path(template.replace("%(ext)s", "mp4"))
        media.write_bytes(b"public example video")
        return SimpleNamespace(returncode=0, stdout=str(media) + "\n", stderr="")

    monkeypatch.setattr("plugins.mission_control.learning_media_fetch.subprocess.run", download)
    fabric = LearningFabric(tmp_path / "fabric")
    source = fetch_public_media(fabric, URL)
    assert source["source_uri"] == URL
    assert source["modality"] == "video"
    assert source["metadata"]["acquisition"]["provider"] == "yt-dlp"
    assert Path(source["stored_path"]).read_bytes() == b"public example video"
    assert not Path(calls[0][0][calls[0][0].index("--output") + 1]).parent.exists()
    command = calls[0][0]
    assert command[-2:] == ["--", URL]
    assert "--ignore-config" in command and "--no-cookies-from-browser" in command
    assert "--max-filesize" in command and "--match-filters" in command
    assert calls[0][1]["timeout"] == 360


def test_cli_fetch_uses_same_pipeline(tmp_path, monkeypatch, capsys):
    profile = tmp_path / "profile"
    monkeypatch.setenv("NARA_HOME", str(profile))
    monkeypatch.setattr("plugins.mission_control.learning_media_fetch.shutil.which", lambda name: "/usr/bin/yt-dlp")
    monkeypatch.setattr("plugins.mission_control.learning_media_fetch._duration", lambda media, probe: 10.0)

    def download(command, **options):
        media = Path(command[command.index("--output") + 1].replace("%(ext)s", "mp4"))
        media.write_bytes(b"cli video")
        return SimpleNamespace(returncode=0, stdout=str(media) + "\n", stderr="")

    monkeypatch.setattr("plugins.mission_control.learning_media_fetch.subprocess.run", download)
    token = set_nara_home_override(profile)
    try:
        parser = argparse.ArgumentParser()
        register_cli(parser)
        assert mission_command(parser.parse_args(["learn-media-fetch", URL])) == 0
        output = capsys.readouterr().out
        assert '"source_uri": "https://www.instagram.com/reel/C123abcd/"' in output
        assert LearningFabric.open_default().status()["sources"][0]["count"] == 1
    finally:
        reset_nara_home_override(token)


def test_rejects_long_media_before_archiving(tmp_path, monkeypatch):
    monkeypatch.setattr("plugins.mission_control.learning_media_fetch.shutil.which", lambda name: "/usr/bin/yt-dlp")

    def download(command, **options):
        media = Path(command[command.index("--output") + 1].replace("%(ext)s", "mp4"))
        media.write_bytes(b"long video")
        return SimpleNamespace(returncode=0, stdout=str(media) + "\n", stderr="")

    def long_duration(media, probe):
        raise ValueError("media duration must be between 0 and 900 seconds")

    monkeypatch.setattr("plugins.mission_control.learning_media_fetch.subprocess.run", download)
    monkeypatch.setattr("plugins.mission_control.learning_media_fetch._duration", long_duration)
    fabric = LearningFabric(tmp_path / "fabric")
    with pytest.raises(ValueError, match="duration"):
        fetch_public_media(fabric, URL)
    assert fabric.status()["sources"] == []
