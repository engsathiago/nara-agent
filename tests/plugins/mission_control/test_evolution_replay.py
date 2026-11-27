"""Admission retries retain evolution identity and distinguish unknown cost from zero."""

import sqlite3

import pytest

from tests.plugins.mission_control.test_evolution import _lab


def test_named_variant_and_deployment_replays_do_not_duplicate_versions(tmp_path):
    lab = _lab(tmp_path)
    lab.create_experiment("skill", "skill", development_case_ids=["dev"], holdout_case_ids=["canary"], experiment_id="exp")
    baseline = lab.register_variant("exp", b"", baseline=True, variant_id="baseline")
    variant = lab.register_variant("exp", b"procedure", variant_id="candidate")
    assert lab.register_variant("exp", b"procedure", variant_id="candidate")["version"] == variant["version"]
    with pytest.raises(ValueError, match="different content"):
        lab.register_variant("exp", b"changed", variant_id="candidate")
    for _ in range(2):
        lab.evaluate("exp", "candidate", baseline_scores={"canary": 0}, candidate_scores={"canary": 1},
                     evidence_artifact_ids=["sha256:observations"], cost_usd=None)
        deployment = lab.promote_canary("exp", "candidate", deployment_id="deployment")
        lab.activate(deployment["deployment_id"])
    assert len(lab.status("exp")["deployments"]) == 2
    with sqlite3.connect(lab.ledger.path) as conn:
        rows = conn.execute("SELECT cost_usd FROM experience_events WHERE kind='evolution.evaluated'").fetchall()
    assert rows == [(None,)]
    for _ in range(2):
        lab.rollback("deployment", "operator rollback")
    assert len(lab.status("exp")["deployments"]) == 3
    assert lab.active_variant("exp") == baseline["variant_id"]


@pytest.mark.parametrize("budget,passed", [(None, True), (1.0, False)])
def test_unknown_evaluation_cost_never_satisfies_a_monetary_cap(tmp_path, budget, passed):
    lab = _lab(tmp_path)
    lab.create_experiment("skill", "skill", development_case_ids=["dev"], holdout_case_ids=["hold"],
                          max_cost_usd=budget, experiment_id="exp")
    lab.register_variant("exp", b"procedure", variant_id="candidate")
    result = lab.evaluate("exp", "candidate", baseline_scores={"hold": 0}, candidate_scores={"hold": 1},
                          evidence_artifact_ids=["sha256:proof"], cost_usd=None)
    assert result["cost_usd"] is None and result["passed"] is passed
    with sqlite3.connect(lab.db_path) as conn:
        assert conn.execute("SELECT cost_known FROM evolution_evaluations").fetchone() == (0,)


def test_declared_correctness_floor_cannot_be_bypassed_by_positive_delta(tmp_path):
    lab = _lab(tmp_path)
    lab.create_experiment("skill", "skill", development_case_ids=["dev"], holdout_case_ids=["hold"],
                          min_candidate_score=1.0, experiment_id="exp")
    lab.register_variant("exp", b"procedure", variant_id="candidate")
    report = lab.evaluate("exp", "candidate", baseline_scores={"hold": 0}, candidate_scores={"hold": 0.5},
                          evidence_artifact_ids=["sha256:observed"], cost_usd=0)
    assert report["passed"] is False
    with pytest.raises(ValueError, match="passing variant"):
        lab.promote_canary("exp", "candidate")


def test_legacy_cost_records_keep_their_known_amount_after_migration(tmp_path):
    lab = _lab(tmp_path)
    lab.root.mkdir(parents=True)
    with sqlite3.connect(lab.db_path) as conn:
        conn.execute("""CREATE TABLE evolution_evaluations (
            evaluation_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, variant_id TEXT NOT NULL,
            evaluated_hash TEXT NOT NULL, baseline_json TEXT NOT NULL, candidate_json TEXT NOT NULL,
            mean_delta REAL NOT NULL, regressions INTEGER NOT NULL, cost_usd REAL NOT NULL,
            evidence_json TEXT NOT NULL, passed INTEGER NOT NULL, created_at TEXT NOT NULL)""")
        conn.execute("INSERT INTO evolution_evaluations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     ("old", "exp", "v1", "hash", "{}", "{}", 0.5, 0, 0.4, "[]", 1, "2026-01-01"))
        conn.execute("PRAGMA user_version=1")
    lab.status()
    with sqlite3.connect(lab.db_path) as conn:
        assert conn.execute("SELECT cost_usd, cost_known FROM evolution_evaluations WHERE evaluation_id='old'").fetchone() == (0.4, 1)
