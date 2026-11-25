from __future__ import annotations

import json

from plugins.mission_control.privacy import PrivacyControl, redact_sensitive


def test_default_privacy_is_local_opt_in_and_secret_safe(tmp_path):
    control = PrivacyControl(tmp_path / "privacy.db")
    status = control.status()
    safe = redact_sensitive({
        "api_key": "real-key", "command": "TOKEN=inline-secret run",
        "nested": {"password": "hunter2"},
    })

    assert status["telemetry"] == "disabled"
    assert status["sensitive_trace_content"] == "redacted"
    assert status["settings"]["voice_transcript_storage"] is False
    assert "real-key" not in json.dumps(safe)
    assert "inline-secret" not in json.dumps(safe)
    assert "hunter2" not in json.dumps(safe)
    assert "sha256:" in json.dumps(safe)


def test_privacy_configuration_and_export_are_explicit_and_hashed(tmp_path):
    control = PrivacyControl(tmp_path / "privacy.db")
    updated = control.configure({"media_retention_days": 7, "telemetry_enabled": True})
    exported = control.export(tmp_path / "privacy-export.json")

    assert updated["media_retention_days"] == 7
    assert updated["telemetry_enabled"] is True
    assert len(exported["sha256"]) == 64
    assert json.loads((tmp_path / "privacy-export.json").read_text())["kind"] == "nara_privacy_export"
