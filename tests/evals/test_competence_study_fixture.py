from __future__ import annotations

from evals.competence_study.run_fixture import run_fixture


def test_failure_study_practice_and_reserved_proof_promote_competence(tmp_path):
    result = run_fixture(tmp_path)

    assert result["status"] == "passed"
    assert result["failure"]["score"] == 0.5
    assert result["gap"]["state"] == "resolved"
    assert set(result["study_plan"]["development_case_ids"]).isdisjoint(
        result["study_plan"]["holdout_case_ids"])
    assert result["practice_score"] == 1.0
    assert result["evaluation"]["passed"] is True
    assert result["evaluation"]["regressions"] == 0
    assert result["proof_mission_status"] == "completed"
    assert result["competence"][0]["state"] == "demonstrated"
