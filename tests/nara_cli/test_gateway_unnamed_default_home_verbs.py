"""Unnamed dashboard gateway lifecycle verbs issued from the DEFAULT home must name
``-p default`` explicitly (``_own_profile_selector``), so the spawned child can never
re-read the sticky ``active_profile`` and restart another profile's gateway, and so the
action environment takes the named-target scrub branch like every other named profile.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def default_home_process(tmp_path, monkeypatch):
    """Process whose own home is the DEFAULT one, with a sticky active_profile naming a
    named profile (the state that made the selector-less child resolve the wrong home)."""
    root = tmp_path / "nara"
    (root / "profiles" / "coder").mkdir(parents=True)
    (root / "profiles" / "coder" / "config.yaml").write_text("{}\n")  # identity marker
    (root / "config.yaml").write_text("model: {default: x}\n")
    (root / "active_profile").write_text("coder")  # sticky: points at a named profile
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("NARA_HOME", str(root))
    for var in ("NARA_SUPERVISED_CHILD", "NARA_S6_SUPERVISED_CHILD", "INVOCATION_ID",
                "NARA_GATEWAY_EXTERNAL_SUPERVISOR", "NARA_UPDATE_POST_SWAP"):
        monkeypatch.delenv(var, raising=False)
    import nara_constants
    monkeypatch.setattr(nara_constants, "_default_nara_root_memo", None)
    return root


def test_unnamed_lifecycle_verbs_from_default_home_always_name_default(default_home_process):
    """Every unnamed verb pins ``-p default``: the child argv names a profile and the env
    pins the default home even though the sticky ``active_profile`` names ``coder``."""
    from nara_cli.web_server_gateway import (
        _gateway_subcommand,
        _named_profile_from_action,
        _profile_action_environment,
    )

    for verb in ("start", "stop", "restart"):
        argv = _gateway_subcommand(None, verb)
        assert argv == ["-p", "default", "gateway", verb]
        assert _named_profile_from_action(argv) == "default"
    env = _profile_action_environment(_gateway_subcommand(None, "restart"))
    assert env["NARA_HOME"] == str(default_home_process)
