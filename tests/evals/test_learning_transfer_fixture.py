from __future__ import annotations

from evals.learning_transfer.run_fixture import run_fixture


def test_phase2_learning_transfers_in_fresh_session_and_keeps_corrections(tmp_path):
    result = run_fixture(tmp_path)

    assert result["status"] == "passed"
    assert result["continuity"]["fault_exit_code"] == 86
    assert result["continuity"]["effect_count"] == 1
    assert result["transfer_evaluation"]["holdout_case_ids"] == [
        "holdout-invoice", "holdout-audit", "holdout-portuguese"]
    assert result["transfer_evaluation"]["mean_delta"] == 0.5
    assert result["fresh_session"]["mission_status"] == "completed"
    assert result["fresh_session"]["memory_recalled"] is True
    assert result["correction"]["current"] == ["The transfer workspace is session-b"]
    assert result["correction"]["history_count"] == 2
