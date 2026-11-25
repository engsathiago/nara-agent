from __future__ import annotations

from pathlib import Path

import pytest

from plugins.mission_control.evolution import EvolutionLab
from plugins.mission_control.ledger import ExperienceLedger


def _lab(tmp_path):
    return EvolutionLab(tmp_path / "evolution", ExperienceLedger(tmp_path / "ledger.db"))


def test_variant_identity_gate_canary_activation_and_session_pins(tmp_path):
    lab = _lab(tmp_path)
    experiment = lab.create_experiment(
        "report prompt", "prompt", development_case_ids=["dev"],
        holdout_case_ids=["hold-a", "hold-b"], min_mean_delta=0.1,
        experiment_id="prompt-exp")
    baseline = lab.register_variant(experiment["experiment_id"], "write report", baseline=True)
    old_pin = lab.pin_session("session-old", experiment["experiment_id"])
    candidate = lab.register_variant(
        experiment["experiment_id"], "write report and verify every criterion")
    evaluation = lab.evaluate(
        experiment["experiment_id"], candidate["variant_id"],
        baseline_scores={"hold-a": 0.5, "hold-b": 0.5},
        candidate_scores={"hold-a": 1.0, "hold-b": 0.75},
        evidence_artifact_ids=["sha256:proof"], cost_usd=0.01)
    canary = lab.promote_canary(experiment["experiment_id"], candidate["variant_id"])

    assert evaluation["passed"] is True
    assert canary["previous_variant_id"] == baseline["variant_id"]
    assert lab.pin_session("session-before-activation", experiment["experiment_id"]) == baseline["variant_id"]
    lab.activate(canary["deployment_id"])
    assert lab.pin_session("session-old", experiment["experiment_id"]) == old_pin
    assert lab.pin_session("session-new", experiment["experiment_id"]) == candidate["variant_id"]


def test_regression_rolls_back_and_tampering_blocks_reload(tmp_path):
    lab = _lab(tmp_path)
    lab.create_experiment(
        "router", "router", development_case_ids=["dev"], holdout_case_ids=["hold"],
        experiment_id="router-exp")
    baseline = lab.register_variant("router-exp", "route=stable", baseline=True)
    candidate = lab.register_variant("router-exp", "route=faster")
    lab.evaluate(
        "router-exp", candidate["variant_id"], baseline_scores={"hold": 0.4},
        candidate_scores={"hold": 0.9}, evidence_artifact_ids=["sha256:eval"])
    deployment = lab.promote_canary("router-exp", candidate["variant_id"])
    lab.activate(deployment["deployment_id"])
    rolled_back = lab.rollback(deployment["deployment_id"], "canary regression")

    assert rolled_back["restored"] == baseline["variant_id"]
    assert lab.active_variant("router-exp") == baseline["variant_id"]
    path = candidate["content_path"]
    Path(path).write_text("tampered", encoding="utf-8")
    with pytest.raises(RuntimeError, match="identity mismatch"):
        lab.reload_variant(candidate["variant_id"])


def test_failed_holdout_never_enters_canary(tmp_path):
    lab = _lab(tmp_path)
    lab.create_experiment(
        "tool", "tool", development_case_ids=["dev"], holdout_case_ids=["hold"],
        experiment_id="tool-exp")
    lab.register_variant("tool-exp", "baseline", baseline=True)
    candidate = lab.register_variant("tool-exp", "regression")
    result = lab.evaluate(
        "tool-exp", candidate["variant_id"], baseline_scores={"hold": 0.9},
        candidate_scores={"hold": 0.2}, evidence_artifact_ids=["sha256:regression"])

    assert result["passed"] is False
    with pytest.raises(ValueError, match="passing variant"):
        lab.promote_canary("tool-exp", candidate["variant_id"])
