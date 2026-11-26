from __future__ import annotations

import pytest

from plugins.mission_control.competence import CompetenceRegistry


def _system():
    return {
        "skill": "atomic-writer@1", "template": "report@2", "model": "model-a",
        "tools": ["file.write", "artifact.verify"], "environment": "darwin-arm64",
    }


def test_verified_observation_requires_evidence_and_is_separate_by_system(tmp_path):
    registry = CompetenceRegistry(tmp_path / "competence.db")
    with pytest.raises(ValueError, match="requires evidence"):
        registry.record_observation(
            "reports.atomic", _system(), 1.0, verified=True, evidence_artifact_ids=[])

    observed = registry.record_observation(
        "reports.atomic", _system(), 0.95, verified=True,
        evidence_artifact_ids=["sha256:abc"], mission_id="mission-a")
    current = registry.current("reports.atomic")

    assert observed["verified"] is True
    assert current[0]["state"] == "demonstrated"
    assert current[0]["best_score"] == 0.95
    assert current[0]["system"]["model"] == "model-a"

    changed = {**_system(), "environment": "linux-x86_64"}
    assessment = registry.assess("reports.atomic", changed)
    assert assessment["state"] == "untested"
    assert assessment["alternatives"][0]["state"] == "outdated"


def test_gap_queue_is_idempotent_and_prioritized(tmp_path):
    registry = CompetenceRegistry(tmp_path / "competence.db")
    low = registry.record_gap(
        "browser.forms", "Fill form", "selector changed", impact=2,
        source_mission_id="mission-a", source_task_id="task-a")
    high = registry.record_gap(
        "effects.reconcile", "Reconcile effect", "destination unknown", impact=5,
        source_mission_id="mission-b", source_task_id="task-b")
    duplicate = registry.record_gap(
        "effects.reconcile", "Reconcile effect", "destination unknown", impact=5,
        source_mission_id="mission-b", source_task_id="task-b")

    assert duplicate["gap_id"] == high["gap_id"]
    assert [item["gap_id"] for item in registry.gaps("open")] == [
        high["gap_id"], low["gap_id"]]


def test_study_refuses_leakage_and_promotes_only_reserved_gain(tmp_path):
    registry = CompetenceRegistry(tmp_path / "competence.db")
    gap = registry.record_gap(
        "archives.inspect", "Inspect archive", "nested path was missed", impact=4)
    with pytest.raises(ValueError, match="must not overlap"):
        registry.create_study_plan(
            gap["gap_id"], "learn nested archive inspection",
            sources=[{"uri": "https://example.test/spec", "version": "v1"}],
            development_case_ids=["same"], holdout_case_ids=["same"])

    plan = registry.create_study_plan(
        gap["gap_id"], "learn nested archive inspection",
        sources=[{"uri": "https://example.test/spec", "version": "v1"}],
        development_case_ids=["dev-a"], holdout_case_ids=["hold-b", "hold-c"],
        minimum_candidate_score=0.75)
    with pytest.raises(ValueError, match="exactly the reserved"):
        registry.evaluate_study(
            plan.plan_id, baseline_scores={"hold-b": 0.5},
            candidate_scores={"hold-b": 1.0}, system=_system(),
            evidence_artifact_ids=["sha256:proof"])

    result = registry.evaluate_study(
        plan.plan_id,
        baseline_scores={"hold-b": 0.5, "hold-c": 0.25},
        candidate_scores={"hold-b": 1.0, "hold-c": 0.75},
        system=_system(), evidence_artifact_ids=["sha256:proof"], mission_id="mission-proof")

    assert result["passed"] is True
    assert result["mean_delta"] == 0.5
    assert registry.gap(gap["gap_id"])["state"] == "resolved"
    assert registry.current("archives.inspect")[0]["state"] == "demonstrated"


def test_failed_study_keeps_competence_undemonstrated(tmp_path):
    registry = CompetenceRegistry(tmp_path / "competence.db")
    gap = registry.record_gap("browser.forms", "Fill form", "wrong field", impact=3)
    plan = registry.create_study_plan(
        gap["gap_id"], "practice form fields",
        sources=[{"uri": "https://example.test/forms", "version": "2026-01"}],
        development_case_ids=["dev"], holdout_case_ids=["proof"])
    result = registry.evaluate_study(
        plan.plan_id, baseline_scores={"proof": 0.8}, candidate_scores={"proof": 0.7},
        system=_system(), evidence_artifact_ids=["sha256:regression"])

    assert result["passed"] is False
    assert result["regressions"] == 1
    assert registry.current("browser.forms") == []
    assert registry.gap(gap["gap_id"])["state"] == "unresolved"
