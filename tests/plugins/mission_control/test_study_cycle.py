"""A bounded study revises on development evidence, then freezes for holdouts."""

import json
from pathlib import Path

import pytest

from nara_constants import reset_nara_home_override
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control import register
from tests.plugins.mission_control.test_learning_media_procedure import _setup, _command
from tests.plugins.mission_control.test_learning_study import _model
from tests.plugins.mission_control.test_plugin import _Context


def _cycle_setup(tmp_path, monkeypatch, capsys):
    home, token, parser, _, source, _, evaluator, cases = _setup(tmp_path, monkeypatch)
    cases.write_text(json.dumps({"cases": [
        {"case_id": "development", "requires": "pinned commit"},
        {"case_id": "holdout", "requires": "pinned commit", "private": "HOLDOUT_PRIVATE_EXPECTATION"},
    ]}), encoding="utf-8")
    evaluator.write_text(
        "import json, sys\nfrom pathlib import Path\n"
        "r=json.load(sys.stdin)\n"
        "steps=' '.join(r['candidate']['steps']) if r['candidate'] else ''\n"
        "score=float(r['case']['requires'] in steps)\n"
        "Path('proof.json').write_text(json.dumps({'case':r['case'],'score':score}))\n"
        "print(json.dumps({'score':score,'artifact_paths':['proof.json'],"
        "'feedback':'Missing pinned commit inspection' if score < 1 else 'Complete'}))\n",
        encoding="utf-8")
    registry = CompetenceRegistry.open_default()
    gap = registry.record_gap("repositories", "Inspect commits", "pin was not inspected", impact=3)
    plan = registry.create_study_plan(
        gap["gap_id"], "Inspect a repository before using it",
        sources=[{"uri": source["source_id"], "version": source["source_hash"]}],
        development_case_ids=["development"], holdout_case_ids=["holdout"],
        minimum_candidate_score=1)
    system = tmp_path / "system.json"
    system.write_text('{"environment":"fixture"}', encoding="utf-8")
    argv = ["study-run", plan.plan_id, source["source_id"], "--cases-file", str(cases),
            "--evaluator", str(evaluator), "--system-file", str(system)]
    return home, token, parser, registry, plan, evaluator, argv


def _adaptive_model(calls):
    def generate(**kwargs):
        request = json.loads(kwargs["input"][0]["text"])
        step = "inspect the repository" if not request.get("development_feedback") else "inspect the pinned commit"
        payload = {"name": "Inspect repository", "steps": [
            {"instruction": step, "source_span_id": "s0001"}], "decline_reason": ""}
        return _model(payload, calls).complete_structured(**kwargs)

    from types import SimpleNamespace

    return SimpleNamespace(complete_structured=generate)


def test_registered_cycle_practices_then_evaluates_once(tmp_path, monkeypatch, capsys):
    home, token, parser, registry, plan, _, argv = _cycle_setup(tmp_path, monkeypatch, capsys)
    calls = []
    try:
        ctx = _Context()
        ctx.llm = _adaptive_model(calls)
        register(ctx)
        code = ctx.command["handler_fn"](parser.parse_args(argv))
        result = json.loads(capsys.readouterr().out)
        assert code == 0 and result["status"] == "completed"
        assert len(calls) == 2 and len(result["attempts"]) == 2
        assert result["attempts"][0]["practice"][0]["score"] == 0
        assert result["attempts"][1]["practice"][0]["score"] == 1
        feedback = json.loads(calls[1]["input"][0]["text"])["development_feedback"]
        assert feedback["cases"][0]["feedback"] == "Missing pinned commit inspection"
        assert "HOLDOUT_PRIVATE_EXPECTATION" not in json.dumps(calls)
        assert result["transfer"]["competence"]["passed"]
        assert registry.gap(plan.gap_id)["state"] == "resolved"
        assert registry.current()[0]["system"]["study_model"] == "study-test"
        assert not list((home / "skills").glob("nara-learned-*"))
        code, shown = _command(parser, capsys, "study-show", plan.plan_id)
        assert code == 0 and shown["cycle"]["status"] == "completed"
        code = ctx.command["handler_fn"](parser.parse_args(argv))
        repeated = json.loads(capsys.readouterr().out)
        assert code == 1 and "already" in repeated["message"] and len(calls) == 2
        assert Path(result["receipt_path"]).is_file()
    finally:
        reset_nara_home_override(token)


@pytest.mark.parametrize("stop", ["exhausted", "holdout_failed"])
def test_cycle_stops_without_tuning_on_holdout(tmp_path, monkeypatch, capsys, stop):
    home, token, parser, registry, plan, evaluator, argv = _cycle_setup(tmp_path, monkeypatch, capsys)
    calls = []
    try:
        if stop == "exhausted":
            argv += ["--max-attempts", "1"]
        else:
            evaluator.write_text(evaluator.read_text(encoding="utf-8-sig").replace(
                "score=float(r['case']['requires'] in steps)",
                "score=float(r['case']['requires'] in steps) * (0.5 if r['case']['case_id']=='holdout' else 1)"),
                encoding="utf-8")
        ctx = _Context()
        ctx.llm = _adaptive_model(calls)
        register(ctx)
        code = ctx.command["handler_fn"](parser.parse_args(argv))
        result = json.loads(capsys.readouterr().out)
        assert code == 0 and result["status"] == stop
        assert len(calls) == (1 if stop == "exhausted" else 2)
        assert registry.gap(plan.gap_id)["state"] == "unresolved"
        assert registry.current() == []
        assert "HOLDOUT_PRIVATE_EXPECTATION" not in json.dumps(calls)
        if stop == "exhausted":
            assert not list(home.rglob("*.eval.json"))
    finally:
        reset_nara_home_override(token)


@pytest.mark.parametrize("cost,expected", [(None, "budget_unverifiable"), (0.02, "budget_exhausted")])
def test_cycle_stops_on_unverifiable_or_exhausted_cost_budget(tmp_path, monkeypatch, capsys, cost, expected):
    _, token, parser, registry, old_plan, _, argv = _cycle_setup(tmp_path, monkeypatch, capsys)
    calls = []
    try:
        gap = registry.record_gap("priced", "Priced study", "missing procedure", impact=3, budget_usd=0.01)
        plan = registry.create_study_plan(
            gap["gap_id"], old_plan.objective, sources=old_plan.sources,
            development_case_ids=old_plan.development_case_ids, holdout_case_ids=old_plan.holdout_case_ids)
        argv[1] = plan.plan_id
        ctx = _Context()
        ctx.llm = _adaptive_model(calls)
        generate = ctx.llm.complete_structured

        def priced(**kwargs):
            result = generate(**kwargs)
            result.usage.cost_usd = cost
            return result

        ctx.llm.complete_structured = priced
        register(ctx)
        code = ctx.command["handler_fn"](parser.parse_args(argv))
        result = json.loads(capsys.readouterr().out)
        assert code == 0 and result["status"] == expected
        assert len(calls) == 1 and result["evaluator_calls_started"] == 0
        assert result["transfer"] is None and registry.gap(plan.gap_id)["state"] == "unresolved"
    finally:
        reset_nara_home_override(token)


def test_cycle_freezes_cases_and_evaluator_before_generation(tmp_path, monkeypatch, capsys):
    _, token, parser, registry, plan, evaluator, argv = _cycle_setup(tmp_path, monkeypatch, capsys)
    calls = []
    try:
        ctx = _Context()
        ctx.llm = _adaptive_model(calls)
        generate = ctx.llm.complete_structured

        def change_inputs(**kwargs):
            result = generate(**kwargs)
            evaluator.write_text("raise RuntimeError('changed after freeze')\n", encoding="utf-8")
            Path(argv[argv.index("--cases-file") + 1]).write_text("[]", encoding="utf-8")
            return result

        ctx.llm.complete_structured = change_inputs
        register(ctx)
        code = ctx.command["handler_fn"](parser.parse_args(argv))
        result = json.loads(capsys.readouterr().out)
        assert code == 0 and result["status"] == "completed" and len(calls) == 2
        assert result["transfer"]["evaluation"]["holdout_case_ids"] == ["holdout"]
        assert registry.gap(plan.gap_id)["state"] == "resolved"
    finally:
        reset_nara_home_override(token)
