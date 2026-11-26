"""Bundled Mission Control is available on a new Nara profile."""

from nara_cli.plugins_discovery import gate_manifest
from nara_cli.plugins_manifest import PluginManifest
from nara_cli.web_server_dashboard import _plugin_runtime_status


def _manifest(*, source="bundled", name="mission_control"):
    return PluginManifest(name=name, key=name, source=source, kind="standalone")


def test_bundled_mission_control_loads_with_no_plugin_selection():
    manifest = _manifest()
    assert gate_manifest(manifest, set(), None).action == "load"
    assert gate_manifest(manifest, set(), set()).action == "load"
    assert gate_manifest(manifest, set(), {"other_plugin"}).action == "load"


def test_explicit_disable_still_wins():
    result = gate_manifest(_manifest(), {"mission_control"}, set())
    assert result.action == "placeholder"
    assert result.error == "disabled via config"


def test_user_override_and_other_bundled_plugins_remain_opt_in():
    assert gate_manifest(_manifest(source="user"), set(), None).action == "placeholder"
    assert gate_manifest(_manifest(name="another_plugin"), set(), None).action == "placeholder"


def test_catalog_status_matches_default_and_explicit_disable():
    aliases = {"mission_control"}
    assert _plugin_runtime_status(aliases, set(), set(), native=True) == "enabled"
    assert _plugin_runtime_status(aliases, set(), aliases, native=True) == "disabled"
    assert _plugin_runtime_status(aliases, set(), set()) == "inactive"
