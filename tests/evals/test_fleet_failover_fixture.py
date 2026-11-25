from __future__ import annotations

from evals.fleet_failover.run_fixture import CRASH_EXIT, run_fixture


def test_two_local_hosts_handoff_and_reclaim_without_repeating_confirmed_effect(tmp_path):
    result = run_fixture(tmp_path)

    assert result["status"] == "passed"
    assert result["mission_status"] == "completed"
    assert result["host_a_exit"] == CRASH_EXIT
    assert result["host_b_exit"] == 0
    assert result["initial_host"] == "host-a"
    assert result["replacement_host"] == "host-b"
    assert result["effect_count"] == 1
    assert result["skip_receipt_ids"] == ["external-effect"]
    assert result["artifact_verified"] is True
