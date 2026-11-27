"""Real killed workers cannot reset budgets or repeat confirmed evaluations."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from nara_constants import reset_nara_home_override
from plugins.mission_control import register
from tests.plugins.mission_control.test_learning_study import _model, _valid
from tests.plugins.mission_control.test_plugin import _Context
from tests.plugins.mission_control.test_study_cycle import _cycle_setup
from tests.waiting import wait_until


def _resume(parser, plan_id, capsys, calls):
    ctx = _Context()
    ctx.llm = _model(_valid(), calls)
    register(ctx)
    code = ctx.command["handler_fn"](parser.parse_args(["study-resume", plan_id]))
    return code, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("stage", ["generation", "practice-result", "holdout-result", "holdout-complete", "competence-recorded"])
def test_killed_cycle_resumes_without_repeating_confirmed_work(tmp_path, monkeypatch, capsys, stage):
    home, token, parser, registry, plan, evaluator, argv = _cycle_setup(tmp_path, monkeypatch, capsys)
    trace = tmp_path / "executions.jsonl"
    evaluator.write_text(evaluator.read_text(encoding="utf-8-sig").replace(
        "r=json.load(sys.stdin)\n",
        "r=json.load(sys.stdin)\n"
        f"with open({str(trace)!r}, 'a', encoding='utf-8') as trace:\n"
        " trace.write(json.dumps([r['case']['case_id'],bool(r['candidate'])])+'\\n')\n"), encoding="utf-8")
    arguments = tmp_path / "argv.json"
    arguments.write_text(json.dumps(argv), encoding="utf-8")
    marker = tmp_path / "ready"
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG"}}
    env["NARA_HOME"] = str(home)
    logs = tmp_path / "worker.log"
    child = None
    calls = []
    try:
        with logs.open("w", encoding="utf-8") as output:
            child = subprocess.Popen(
                [sys.executable, "-m", "tests.plugins.mission_control.study_cycle_worker",
                 str(arguments), stage, str(marker)], env=env, stdout=output, stderr=output)
            wait_until(lambda: marker.exists() or child.poll() is not None,
                       timeout=30, what="owned study worker checkpoint")
            assert marker.exists(), logs.read_text(encoding="utf-8-sig")
            code, busy = _resume(parser, plan.plan_id, capsys, calls)
            assert code == 1 and "executing" in busy["message"]
            assert calls == [] and child.poll() is None
            child.kill()
            child.wait(timeout=10)
        code, result = _resume(parser, plan.plan_id, capsys, calls)
        assert code == 0 and result["status"] == "completed"
        assert result["generation_calls_started"] == (2 if stage == "generation" else 1)
        assert len(calls) == (1 if stage == "generation" else 0)
        observed = [json.loads(line) for line in trace.read_text(encoding="utf-8-sig").splitlines()]
        assert observed == [["development", True], ["holdout", False], ["holdout", True]]
        assert registry.current()[0]["sample_count"] == 1
        assert registry.gap(plan.gap_id)["state"] == "resolved"
        code, repeated = _resume(parser, plan.plan_id, capsys, calls)
        assert code == 0 and repeated["receipt_sha256"] == result["receipt_sha256"]
        assert trace.read_text(encoding="utf-8-sig").count("\n") == 3
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        reset_nara_home_override(token)


@pytest.fixture
def interrupted_cycle(tmp_path, monkeypatch, capsys):
    home, token, parser, registry, plan, evaluator, argv = _cycle_setup(tmp_path, monkeypatch, capsys)

    def interrupt(stage, extra=(), budget=None):
        selected_plan = plan
        arguments_list = [*argv, *extra]
        if budget is not None:
            gap = registry.record_gap("priced", "Budgeted study", "missing procedure", impact=3, budget_usd=budget)
            selected_plan = registry.create_study_plan(
                gap["gap_id"], plan.objective, sources=plan.sources,
                development_case_ids=plan.development_case_ids, holdout_case_ids=plan.holdout_case_ids)
            arguments_list[1] = selected_plan.plan_id
        arguments = tmp_path / "argv.json"
        arguments.write_text(json.dumps(arguments_list), encoding="utf-8")
        marker = tmp_path / "ready"
        env = {key: value for key, value in os.environ.items()
               if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG"}}
        env["NARA_HOME"] = str(home)
        logs = tmp_path / "worker.log"
        with logs.open("w", encoding="utf-8") as output:
            child = subprocess.Popen(
                [sys.executable, "-m", "tests.plugins.mission_control.study_cycle_worker",
                 str(arguments), stage, str(marker)], env=env, stdout=output, stderr=output)
            try:
                wait_until(lambda: marker.exists() or child.poll() is not None,
                           timeout=30, what="owned study worker checkpoint")
                assert marker.exists(), logs.read_text(encoding="utf-8-sig")
            finally:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=10)
        return parser, registry, selected_plan, evaluator

    try:
        yield interrupt
    finally:
        reset_nara_home_override(token)


def test_unknown_evaluator_intent_is_not_reexecuted(interrupted_cycle, capsys):
    parser, registry, plan, _ = interrupted_cycle("unknown-evaluator")
    calls = []
    code, result = _resume(parser, plan.plan_id, capsys, calls)
    assert code == 0 and result["status"] == "reconciliation_required"
    assert result["evaluator_calls_started"] == 1 and result["evaluator_usage"] == []
    assert result["pending_call"]["kind"] == "evaluator"
    assert registry.current() == [] and registry.gap(plan.gap_id)["state"] == "unresolved"
    assert calls == []
    _, repeated = _resume(parser, plan.plan_id, capsys, calls)
    assert repeated["receipt_sha256"] == result["receipt_sha256"] and calls == []


@pytest.mark.parametrize("limit", ["time", "calls"])
def test_resume_does_not_renew_generation_budget(interrupted_cycle, capsys, monkeypatch, limit):
    parser, registry, plan, _ = interrupted_cycle("generation", ["--max-attempts", "1"] if limit == "calls" else [])
    if limit == "time":
        import time

        now = time.time()
        monkeypatch.setattr("plugins.mission_control.study_resume.time.time", lambda: now + 7200)
    calls = []
    code, result = _resume(parser, plan.plan_id, capsys, calls)
    assert code == 0 and result["status"] == ("budget_exhausted" if limit == "time" else "exhausted")
    assert result["generation_calls_started"] == 1 and result["cost_unknown"]
    assert result["evaluator_calls_started"] == 0 and calls == []
    assert registry.current() == []


def test_resume_uses_archived_evaluator_when_original_is_gone(interrupted_cycle, capsys):
    parser, _, plan, evaluator = interrupted_cycle("practice-result")
    evaluator.unlink()
    calls = []
    code, result = _resume(parser, plan.plan_id, capsys, calls)
    assert code == 0 and result["status"] == "completed" and calls == []


@pytest.mark.parametrize("artifact", ["generation", "evaluator", "observation"])
def test_resume_refuses_changed_evidence_before_new_calls(interrupted_cycle, capsys, artifact):
    parser, registry, plan, _ = interrupted_cycle("practice-result")
    row = registry.study_cycle(plan.plan_id)
    if artifact == "generation":
        path = row["result"]["attempts"][0]["generation_evidence"]["path"]
    elif artifact == "evaluator":
        request = json.loads(Path(row["request"]["path"]).read_text(encoding="utf-8-sig"))
        path = request["evaluator"]["path"]
    else:
        path = row["result"]["evaluator_usage"][0]["evidence"][0]["path"]
    Path(path).write_bytes(b"changed")
    calls = []
    code, result = _resume(parser, plan.plan_id, capsys, calls)
    assert code == 1 and "changed" in result["message"] and calls == []
    assert registry.current() == []


def test_completed_holdout_can_be_recorded_after_deadline_without_more_calls(interrupted_cycle, capsys, monkeypatch):
    parser, registry, plan, _ = interrupted_cycle("holdout-complete")
    import time

    now = time.time()
    monkeypatch.setattr("plugins.mission_control.study_resume.time.time", lambda: now + 7200)
    calls = []
    code, result = _resume(parser, plan.plan_id, capsys, calls)
    assert code == 0 and result["status"] == "completed"
    assert result["evaluator_calls_started"] == 3 and calls == []
    assert registry.current()[0]["sample_count"] == 1


def test_unknown_generation_price_stops_budgeted_resume(interrupted_cycle, capsys):
    parser, registry, plan, _ = interrupted_cycle("generation", budget=1)
    calls = []
    code, result = _resume(parser, plan.plan_id, capsys, calls)
    assert code == 0 and result["status"] == "budget_unverifiable"
    assert result["cost_unknown"] and result["generation_calls_started"] == 1
    assert result["evaluator_calls_started"] == 0 and calls == []
    assert registry.current() == []


def test_legacy_interrupted_cycle_is_not_restarted(tmp_path, monkeypatch, capsys):
    from plugins.mission_control.learning_cli import open_learning_lab
    from plugins.mission_control.store import MissionStore
    from plugins.mission_control.study_execution import _archive

    _, token, parser, registry, plan, _, _ = _cycle_setup(tmp_path, monkeypatch, capsys)
    try:
        lab = open_learning_lab(MissionStore.open_default())
        path, digest = _archive(lab, {"kind": "study_cycle_request", "schema_version": 1})
        registry.claim_study_cycle(plan.plan_id, {"path": str(path), "sha256": digest})
        calls = []
        code, result = _resume(parser, plan.plan_id, capsys, calls)
        assert code == 1 and "legacy interrupted" in result["message"] and calls == []
        assert registry.study_cycle(plan.plan_id)["status"] == "studying"
    finally:
        reset_nara_home_override(token)


def test_unknown_running_evaluator_is_not_duplicated(tmp_path, monkeypatch, capsys):
    import psutil
    import socket

    home, token, parser, registry, plan, evaluator, argv = _cycle_setup(tmp_path, monkeypatch, capsys)
    marker = tmp_path / "evaluator-effect.json"
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(10)
    evaluator.write_text(
        "import json, os, sys, socket\nfrom pathlib import Path\n"
        "request=json.load(sys.stdin)\n"
        f"channel=socket.create_connection(('127.0.0.1', {listener.getsockname()[1]}), timeout=60)\n"
        f"staged=Path({str(marker.with_suffix('.tmp'))!r})\n"
        "staged.write_text(json.dumps(dict(pid=os.getpid(),request=request)))\n"
        f"staged.replace({str(marker)!r})\n"
        "channel.recv(1)\nchannel.close()\n", encoding="utf-8")
    arguments = tmp_path / "argv.json"
    arguments.write_text(json.dumps(argv), encoding="utf-8")
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG"}}
    env["NARA_HOME"] = str(home)
    child = evaluator_process = connection = None
    try:
        with (tmp_path / "worker.log").open("w", encoding="utf-8") as output:
            child = subprocess.Popen(
                [sys.executable, "-m", "tests.plugins.mission_control.study_cycle_worker",
                 str(arguments), "active-evaluator", str(tmp_path / "unused")],
                env=env, stdout=output, stderr=output)
            connection, _ = listener.accept()
            wait_until(lambda: marker.exists() or child.poll() is not None,
                       timeout=30, what="owned evaluator external effect")
            assert marker.exists()
            effect = marker.read_bytes()
            evaluator_process = psutil.Process(json.loads(effect)["pid"])
            assert evaluator_process.ppid() == child.pid
            child.kill()
            child.wait(timeout=10)
            calls = []
            code, result = _resume(parser, plan.plan_id, capsys, calls)
            assert code == 0 and result["status"] == "reconciliation_required"
            assert evaluator_process.is_running() and marker.read_bytes() == effect
            assert result["evaluator_calls_started"] == 1 and calls == []
            assert registry.current() == []
    finally:
        # The evaluator may now belong to init. Release our private channel
        # instead of signalling an orphan outside the test's process tree.
        if connection is not None:
            connection.close()
        listener.close()
        if evaluator_process is not None:
            evaluator_process.wait(timeout=10)
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=10)
        reset_nara_home_override(token)
