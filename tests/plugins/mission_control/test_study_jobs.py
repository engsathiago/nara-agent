"""Queued source research and reserved study run through the registered product surfaces."""

import json
from pathlib import Path
import threading

import pytest

from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control import register
from plugins.mission_control.store import MissionStore
from tests.plugins.mission_control.test_learning_study import _model, _valid
from tests.plugins.mission_control.test_plugin import _Context
from tests.plugins.mission_control.test_study_cycle import _cycle_setup
from tests.waiting import wait_until


def proposal():
    payload = _valid()
    payload["steps"][0]["source_span_id"] = "s0000"
    return payload


@pytest.fixture
def job_profile(tmp_path, monkeypatch, capsys):
    home, token, parser, registry, plan, evaluator, argv = _cycle_setup(tmp_path, monkeypatch, capsys)
    registry.transition_gap(plan.gap_id, "open")
    spec = {"objective": "Inspect the pinned repository commit", "domains": ["docs.example.org"],
            "cases_file": argv[argv.index("--cases-file") + 1], "evaluator": str(evaluator),
            "system_file": argv[argv.index("--system-file") + 1], "development_case_ids": ["development"],
            "minimum_candidate_score": 1, "max_seconds": 120, "max_sources": 1}
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    calls, web_calls = [], []
    ctx = _Context()
    ctx.llm = _model(proposal(), calls)

    def dispatch(name, args):
        web_calls.append((name, args))
        url = "https://docs.example.org/repository"
        if name == "web_search":
            return json.dumps({"success": True, "data": {"web": [{"url": url}]}})
        return json.dumps({"results": [{"url": url,
            "content": "Inspect the pinned commit in the repository before running unfamiliar code."}]})

    ctx.dispatch_tool = dispatch
    register(ctx)
    try:
        yield home, parser, registry, plan, spec, path, ctx, calls, web_calls
    finally:
        reset_nara_home_override(token)


def command(ctx, parser, capsys, *args):
    code = ctx.command["handler_fn"](parser.parse_args(list(args)))
    return code, json.loads(capsys.readouterr().out)


def test_queue_freezes_inputs_and_runs_research_practice_and_proof(job_profile, capsys):
    home, parser, registry, plan, spec, path, ctx, calls, web_calls = job_profile
    code, queued = command(ctx, parser, capsys, "study-enqueue", plan.gap_id, "--protocol-file", str(path))
    assert code == 0 and queued["status"] == "planned"
    _, same = command(ctx, parser, capsys, "study-enqueue", plan.gap_id, "--protocol-file", str(path))
    assert same["mission_id"] == queued["mission_id"]
    for name in ("cases_file", "evaluator", "system_file"):
        Path(spec[name]).unlink()
    code, result = command(ctx, parser, capsys, "study-work")
    assert code == 0 and result["status"] == "completed", result
    assert len(calls) == 1 and [name for name, _ in web_calls] == ["web_search", "web_extract"]
    assert "HOLDOUT_PRIVATE_EXPECTATION" not in json.dumps(calls + web_calls)
    assert registry.gap(plan.gap_id)["state"] == "resolved" and registry.current()[0]["sample_count"] == 1
    missions = MissionStore.open_default()
    mission = missions.get(queued["mission_id"])
    assert mission.status == "completed" and missions.verify_projection(mission.mission_id)
    assert mission.diagnostics["study_state"]["research"]["sources"]
    assert not list((home / "skills").glob("nara-learned-*"))
    _, idle = command(ctx, parser, capsys, "study-work")
    assert idle["status"] == "idle" and len(calls) == 1


def test_gateway_wakes_one_profile_scoped_worker_without_blocking(job_profile, capsys, tmp_path):
    _, _, registry, plan, spec, _, ctx, calls, web_calls = job_profile
    started, release = threading.Event(), threading.Event()

    def pause_model():
        started.set()
        assert release.wait(timeout=20)

    ctx.llm = _model(proposal(), calls, pause_model)
    ctx.get_config = lambda key, default=None: {
        "enabled": True, "protocols": {"repositories": spec}, "interval_seconds": 600}
    register(ctx)
    hook = ctx.hooks["on_gateway_housekeeping"]
    second_token = None
    try:
        first = hook()
        assert first["study"]["state"] == "started"
        assert started.wait(timeout=20)
        assert hook()["study"]["state"] == "running"
        second_token = set_nara_home_override(tmp_path / "other-profile")
        release.set()
        wait_until(lambda: registry.gap(plan.gap_id)["state"] == "resolved", timeout=20,
                   what="background study proof")
        assert not (tmp_path / "other-profile" / "plugin-data").exists()
        assert len(calls) == 1 and len(web_calls) == 2
    finally:
        release.set()
        if second_token is not None:
            reset_nara_home_override(second_token)
        wait_until(lambda: hook()["study"]["state"] == "not_due", timeout=20,
                   what="owned background study worker exit")


@pytest.mark.parametrize("boundary", ["finished", "verification", "verifying"])
def test_finished_cycle_recovers_job_settlement_without_new_calls(job_profile, capsys, monkeypatch, boundary):
    from plugins.mission_control.study_jobs import StudyJobs

    _, parser, registry, plan, _, path, ctx, calls, web_calls = job_profile
    _, queued = command(ctx, parser, capsys, "study-enqueue", plan.gap_id, "--protocol-file", str(path))
    checkpoint = StudyJobs._checkpoint

    class Interrupted(BaseException):
        pass

    def stop(self, identity, state):
        checkpoint(self, identity, state)
        if state["phase"] == "finished":
            raise Interrupted()

    from plugins.mission_control.verification import VerificationService

    record = VerificationService.record
    transition = MissionStore.transition

    def verified(self, proof):
        result = record(self, proof)
        if proof.mission_id.startswith("study-job-"):
            raise Interrupted()
        return result

    def transitioned(self, identity, status, **kwargs):
        result = transition(self, identity, status, **kwargs)
        if identity.startswith("study-job-") and status == "verifying":
            raise Interrupted()
        return result

    with monkeypatch.context() as patch:
        target, method, replacement = {
            "finished": (StudyJobs, "_checkpoint", stop),
            "verification": (VerificationService, "record", verified),
            "verifying": (MissionStore, "transition", transitioned),
        }[boundary]
        patch.setattr(target, method, replacement)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, "study-work")
    capsys.readouterr()
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "completed" and result["job_id"] == queued["mission_id"]
    assert len(calls) == 1 and len(web_calls) == 2 and registry.current()[0]["sample_count"] == 1


@pytest.mark.parametrize("interrupted_phase", ["ready", "research_running"])
def test_job_restart_does_not_renew_deadline_or_repeat_unknown_research(job_profile, capsys, monkeypatch, interrupted_phase):
    from plugins.mission_control.study_jobs import StudyJobs
    import time

    _, parser, registry, plan, _, path, ctx, calls, web_calls = job_profile
    command(ctx, parser, capsys, "study-enqueue", plan.gap_id, "--protocol-file", str(path))
    checkpoint = StudyJobs._checkpoint

    class Interrupted(BaseException):
        pass

    def stop(self, identity, state):
        checkpoint(self, identity, state)
        if state["phase"] == interrupted_phase:
            raise Interrupted()

    with monkeypatch.context() as patch:
        patch.setattr(StudyJobs, "_checkpoint", stop)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, "study-work")
    capsys.readouterr()
    now = time.time()
    monkeypatch.setattr("plugins.mission_control.study_jobs.time.time", lambda: now + 7200)
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "failed"
    assert ("deadline" if interrupted_phase == "ready" else "unconfirmed") in result["reason"]
    assert calls == [] and web_calls == [] and registry.current() == []


@pytest.mark.parametrize("failure", ["no_sources", "holdout", "changed_input"])
def test_failed_jobs_preserve_gap_without_competence(job_profile, capsys, failure):
    _, parser, registry, plan, spec, path, ctx, calls, _ = job_profile
    if failure == "holdout":
        evaluator = Path(spec["evaluator"])
        evaluator.write_text(evaluator.read_text(encoding="utf-8-sig").replace(
            "score=float(r['case']['requires'] in steps)",
            "score=float(r['case']['requires'] in steps) * (0.5 if r['case']['case_id']=='holdout' else 1)"),
            encoding="utf-8")
    if failure == "no_sources":
        ctx.dispatch_tool = lambda name, args: json.dumps({"success": True, "data": {"web": []}})
    _, queued = command(ctx, parser, capsys, "study-enqueue", plan.gap_id, "--protocol-file", str(path))
    if failure == "changed_input":
        protocol = json.loads(Path(queued["constraints"]["protocol"]["path"]).read_text(encoding="utf-8-sig"))
        Path(protocol["files"]["evaluator"]["path"]).write_bytes(b"changed")
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == ("holdout_failed" if failure == "holdout" else "failed")
    assert registry.gap(plan.gap_id)["state"] == "unresolved" and registry.current() == []
    assert len(calls) == (1 if failure == "holdout" else 0)
    assert MissionStore.open_default().get(queued["mission_id"]).status == "failed"


def test_busy_study_plan_keeps_job_pending_without_repeating_research(job_profile, capsys):
    from plugins.mission_control.study_checkpoint import study_lock

    _, parser, registry, plan, _, path, ctx, calls, web_calls = job_profile
    _, queued = command(ctx, parser, capsys, "study-enqueue", plan.gap_id, "--protocol-file", str(path))
    store = MissionStore.open_default()
    with study_lock(store.path.parent / "learning", queued["mission_id"]):
        code, result = command(ctx, parser, capsys, "study-work")
    assert code == 0 and result["status"] == "busy"
    assert store.get(queued["mission_id"]).status == "running" and calls == []
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "completed" and len(calls) == 1 and len(web_calls) == 2
    assert registry.current()[0]["sample_count"] == 1
