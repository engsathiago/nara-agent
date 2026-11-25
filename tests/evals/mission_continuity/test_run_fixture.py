from __future__ import annotations

from evals.mission_continuity.run_fixture import run_fixture


def test_vertical_fixture_survives_crash_and_completes_once(tmp_path):
    result = run_fixture(tmp_path / "fixture")

    assert result["status"] == "passed"
    assert result["mission_status"] == "completed"
    assert result["fault_exit_code"] == 86
    assert result["effect_count"] == 1
    assert result["receipt_status"] == "confirmed"
    assert result["artifact_verified"] is True
    assert result["browser_observation"]["completion_marker"] is True
    assert result["completion_blockers"] == []
