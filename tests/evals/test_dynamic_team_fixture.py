from __future__ import annotations

from evals.dynamic_team.run_fixture import run_fixture


def test_resolver_factory_and_three_parallel_workers_complete_verified_team_mission(tmp_path):
    result = run_fixture(tmp_path)

    assert result["status"] == "passed"
    assert result["mission_status"] == "completed"
    assert result["specialist_count"] == 3
    assert result["speedup"] > 1.3
    assert result["team_quality"] > result["leader_baseline_quality"]
    assert result["completion_blockers"] == []
    assert {plan["specialist_id"] for plan in result["worker_plans"].values()} == {
        "analista_dados", "precificacao", "copywriter"}
