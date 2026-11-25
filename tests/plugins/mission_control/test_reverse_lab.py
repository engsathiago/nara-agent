from __future__ import annotations

import json

from plugins.mission_control.reverse_lab import ReverseEngineeringLab


def _plugin(root):
    root.mkdir()
    (root / "mcp.json").write_text(json.dumps({
        "mcpServers": {"rea": {
            "command": "npx", "args": ["-y", "rea-agents@6.7.0", "mcp"],
        }},
    }), encoding="utf-8")
    return root


def test_routes_electron_and_native_without_modifying_original(tmp_path):
    lab = ReverseEngineeringLab(tmp_path / "reverse.db", plugin_root=_plugin(tmp_path / "rea"))
    electron = tmp_path / "app.asar"
    electron.write_bytes(b"electron fixture")
    native = tmp_path / "fixture"
    native.write_bytes(b"\x7fELF" + b"fixture-native")
    electron_before = electron.read_bytes()
    native_before = native.read_bytes()

    routed_electron = lab.route(
        electron, scope_statement="fixture owned by test",
        user_attested_authorized=True)
    routed_native = lab.route(
        native, scope_statement="fixture owned by test",
        user_attested_authorized=True)
    repeated = lab.route(
        electron, scope_statement="fixture owned by test",
        user_attested_authorized=True)

    assert routed_electron["route"] == "rea_static"
    assert routed_native["route"] == "ghidra_static"
    assert routed_electron["investigation_id"] == repeated["investigation_id"]
    assert routed_electron["plan"]["read_only"] is True
    assert electron.read_bytes() == electron_before
    assert native.read_bytes() == native_before
    assert lab.provider_status()["rea_configured"] is True


def test_authorization_and_mutation_are_explicit_gates(tmp_path):
    lab = ReverseEngineeringLab(tmp_path / "reverse.db", plugin_root=_plugin(tmp_path / "rea"))
    target = tmp_path / "target.bin"
    target.write_bytes(b"owned")

    for kwargs in (
        {"scope_statement": "", "user_attested_authorized": True},
        {"scope_statement": "owned", "user_attested_authorized": False},
        {"scope_statement": "owned", "user_attested_authorized": True, "read_only": False},
    ):
        try:
            lab.route(target, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("reverse-engineering gate was bypassed")
