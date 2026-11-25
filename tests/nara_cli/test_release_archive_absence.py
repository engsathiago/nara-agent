"""Nara source updates do not contact an inherited release archive."""

import pytest

from nara_cli import source_releases

pytestmark = pytest.mark.real_release_channels


def test_unpublished_archive_is_skipped_for_github_release(monkeypatch):
    monkeypatch.setattr(source_releases, "_PUBLIC_BASE", "")
    monkeypatch.setattr(source_releases, "_read", lambda *args, **kwargs: pytest.fail("unexpected archive read"))

    assert source_releases._release_pointer("stable") == (None, None)


def test_preview_channel_requires_a_published_archive(monkeypatch):
    monkeypatch.setattr(source_releases, "_PUBLIC_BASE", "")

    with pytest.raises(ValueError, match="not published"):
        source_releases._resolve_channel("preview", source_releases.OFFICIAL_REPOSITORY)
