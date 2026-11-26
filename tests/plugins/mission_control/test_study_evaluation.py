"""A study closes a gap only through reserved, sufficiently good evidence."""

import json
import sqlite3
from pathlib import Path

import pytest

from nara_constants import reset_nara_home_override
from plugins.mission_control.competence import CompetenceRegistry
from tests.plugins.mission_control.test_learning_eval_cli import _command, _prepare


def test_small_improvement_does_not_resolve_a_gap(tmp_path):
    registry = CompetenceRegistry(tmp_path / "competence.db")
    gap = registry.record_gap("reports", "Complete reports", "missing fields", impact=3)
    plan = registry.create_study_plan(
        gap["gap_id"], "Complete every required field",
        sources=[{"uri": "file:report-spec", "version": "1"}],
        development_case_ids=["dev"], holdout_case_ids=["reserved"],
    )
    result = registry.evaluate_study(
        plan.plan_id, baseline_scores={"reserved": 0.0},
        candidate_scores={"reserved": 0.5}, system={"model": "fixture"},
        evidence_artifact_ids=["fixture-proof"],
    )
    assert result["passed"] is False
    assert registry.gap(gap["gap_id"])["state"] == "unresolved"
    assert registry.current() == []


def _plan(parser, capsys):
    code, gap = _command(parser, capsys, "gap-record", "reports", "Write report",
                         "write was incomplete", "--impact", "3")
    assert code == 0
    code, plan = _command(
        parser, capsys, "study-plan", gap["gap_id"], "Write and verify reports",
        "--source", '{"uri":"mission:mission-a","version":"1"}',
        "--development-case", "dev-a", "--holdout-case", "holdout-b",
        "--minimum-candidate-score", "1",
    )
    assert code == 0
    return plan


def test_cli_runs_reserved_study_and_links_verified_evidence(tmp_path, monkeypatch, capsys):
    home, token, parser, evaluator, cases = _prepare(tmp_path, monkeypatch)
    try:
        plan = _plan(parser, capsys)
        _, candidate = _command(parser, capsys, "learn-extract", "mission-a")
        system = tmp_path / "system.json"
        system.write_text('{"model":"fixture","environment":"local"}', encoding="utf-8")
        code, result = _command(
            parser, capsys, "study-evaluate", plan["plan_id"], candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--system-file", str(system),
        )
        assert code == 0 and result["competence"]["passed"]
        registry = CompetenceRegistry.open_default()
        assert registry.gap(plan["gap_id"])["state"] == "resolved"
        observed = registry.current("reports")[0]
        assert observed["state"] == "demonstrated"
        assert observed["system"]["procedure_candidate_id"] == candidate["candidate_id"]
        assert result["evaluation"]["minimum_candidate_score"] == 1
        assert result["evaluation"]["holdout_case_ids"] == ["holdout-b"]
        assert Path(result["receipt_path"]).is_file()
        receipt = json.loads(Path(result["receipt_path"]).read_text(encoding="utf-8-sig"))
        assert receipt["plan"]["plan_id"] == plan["plan_id"]
        assert receipt["evaluation"] == result["evaluation"]
        assert not list((home / "skills").glob("nara-learned-*"))
    finally:
        reset_nara_home_override(token)


@pytest.mark.parametrize("failure", ["partial", "exit", "corrupt", "wrong_cases"])
def test_cli_cannot_record_unproved_study(tmp_path, monkeypatch, capsys, failure):
    home, token, parser, evaluator, cases = _prepare(tmp_path, monkeypatch)
    try:
        plan = _plan(parser, capsys)
        _, candidate = _command(parser, capsys, "learn-extract", "mission-a")
        system = tmp_path / "system.json"
        system.write_text('{"model":"fixture"}', encoding="utf-8")
        if failure == "partial":
            evaluator.write_text(
                "import json, sys\nfrom pathlib import Path\n"
                "r=json.load(sys.stdin)\nscore=0.5 if r['candidate'] else 0.0\n"
                "Path('proof').write_text(str(score))\n"
                "print(json.dumps({'score':score,'artifact_paths':['proof']}))\n",
                encoding="utf-8")
        elif failure == "exit":
            evaluator.write_text("raise RuntimeError('case interrupted')\n", encoding="utf-8")
        elif failure == "corrupt":
            from plugins.mission_control.learning_runner import ProcessEvaluator

            run = ProcessEvaluator.__call__

            def corrupt(self, candidate, case):
                result = run(self, candidate, case)
                if candidate is not None:
                    Path(result["evidence"][0]["path"]).write_text("changed", encoding="utf-8")
                return result

            monkeypatch.setattr(ProcessEvaluator, "__call__", corrupt)
        else:
            payload = json.loads(cases.read_text(encoding="utf-8-sig"))
            payload["cases"][1]["case_id"] = "replacement"
            cases.write_text(json.dumps(payload), encoding="utf-8")
        code, result = _command(
            parser, capsys, "study-evaluate", plan["plan_id"], candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--system-file", str(system))
        if failure == "partial":
            assert code == 0 and result["competence"]["passed"] is False
            assert result["competence"]["below_minimum"] == ["holdout-b"]
        else:
            assert code == 1
        if failure in {"exit", "corrupt"}:
            receipts = [json.loads(path.read_text(encoding="utf-8-sig"))
                        for path in (home / "plugin-data/mission-control/learning/studies").glob("*.json")]
            failed = [item for item in receipts if item["kind"] == "study_evaluation_failure"]
            assert len(failed) == 1 and failed[0]["plan_id"] == plan["plan_id"]
            assert Path(failed[0]["request_path"]).is_file()
        registry = CompetenceRegistry.open_default()
        assert registry.current() == []
        assert registry.gap(plan["gap_id"])["state"] == (
            "studying" if failure == "wrong_cases" else "unresolved")
        assert not list((home / "skills").glob("nara-learned-*"))
    finally:
        reset_nara_home_override(token)


def test_competence_and_gap_commit_together(tmp_path):
    registry = CompetenceRegistry(tmp_path / "competence.db")
    gap = registry.record_gap("reports", "Write reports", "missing fields", impact=3)
    plan = registry.create_study_plan(
        gap["gap_id"], "Complete fields", sources=[{"uri": "fixture", "version": "1"}],
        development_case_ids=["dev"], holdout_case_ids=["reserved"])
    with sqlite3.connect(registry.path) as conn:
        conn.execute("""CREATE TRIGGER fail_observation BEFORE INSERT ON competence_observations
                        BEGIN SELECT RAISE(ABORT, 'injected storage failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected storage failure"):
        registry.evaluate_study(
            plan.plan_id, baseline_scores={"reserved": 0}, candidate_scores={"reserved": 1},
            system={"model": "fixture"}, evidence_artifact_ids=["fixture"])
    assert registry.study_plan(plan.plan_id).status == "studying"
    assert registry.gap(gap["gap_id"])["state"] == "studying"
    assert registry.current() == []
    with sqlite3.connect(registry.path) as conn:
        assert conn.execute("SELECT count(*) FROM study_evaluations").fetchone()[0] == 0


def _legacy_registry(path):
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE study_plans (
                plan_id TEXT PRIMARY KEY, gap_id TEXT NOT NULL, objective TEXT NOT NULL,
                sources_json TEXT NOT NULL, development_case_ids_json TEXT NOT NULL,
                holdout_case_ids_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
            PRAGMA user_version=1;
        """)
        conn.execute("INSERT INTO study_plans VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     ("legacy", "gap", "old objective", '[{"uri":"fixture","version":"1"}]',
                      '["dev"]', '["reserved"]', "studying", "2026-11-01"))
    return CompetenceRegistry(path)


def test_existing_plan_preserves_its_relative_only_contract(tmp_path):
    registry = _legacy_registry(tmp_path / "legacy.db")
    for _ in range(2):
        plan = registry.study_plan("legacy")
        assert plan.minimum_candidate_score == 0.0
        assert plan.objective == "old objective" and plan.holdout_case_ids == ("reserved",)


def test_interrupted_schema_migration_can_be_reopened(tmp_path):
    from plugins.mission_control.competence import _initialize

    registry = _legacy_registry(tmp_path / "legacy.db")
    conn = sqlite3.connect(registry.path)

    def deny_version_write(action, arg1, arg2, database, trigger):
        if action == sqlite3.SQLITE_PRAGMA and arg1 == "user_version" and arg2 is not None:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(deny_version_write)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            _initialize(conn)
    finally:
        conn.close()
    assert registry.study_plan("legacy").minimum_candidate_score == 0.0


def test_explicit_low_floor_records_practice_without_resolving_gap(tmp_path):
    registry = CompetenceRegistry(tmp_path / "competence.db")
    gap = registry.record_gap("reports", "Write reports", "missing fields", impact=3)
    plan = registry.create_study_plan(
        gap["gap_id"], "Partial progress", sources=[{"uri": "fixture", "version": "1"}],
        development_case_ids=["dev"], holdout_case_ids=["reserved"], minimum_candidate_score=0.4)
    result = registry.evaluate_study(
        plan.plan_id, baseline_scores={"reserved": 0}, candidate_scores={"reserved": 0.5},
        system={"model": "fixture"}, evidence_artifact_ids=["fixture"])
    assert result["passed"] and result["observation"]["status"] == "practicing"
    assert registry.gap(gap["gap_id"])["state"] == "practicing"
