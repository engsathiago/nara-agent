"""Approved study must test the native skill in isolation before automatic publication."""

import json
from pathlib import Path

import pytest

from plugins.mission_control.evolution import EvolutionLab
from plugins.mission_control.learning_cli import open_learning_lab
from plugins.mission_control.store import MissionStore
from tests.plugins.mission_control import test_study_jobs as job_tests
from tests.plugins.mission_control.test_study_jobs import command
from tools.skills_tool import find_all_skills

job_profile = job_tests.job_profile


@pytest.fixture
def admission_job(job_profile, tmp_path):
    _, _, _, _, spec, path, _, _, _ = job_profile
    evaluator = tmp_path / "canary.py"
    evaluator.write_text(
        "import hashlib, json, os, sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(Path(__file__).resolve().parents[3])!r})\n"
        "from tools.skills_tool import find_all_skills\n"
        "r=json.load(sys.stdin)\nassert r['candidate'] is None\n"
        "name=r['canary']['skill_name']\n"
        "found=name in {s['name'] for s in find_all_skills()}\n"
        "path=Path(os.environ['NARA_HOME'])/'skills'/name/'SKILL.md'\n"
        "raw=path.read_bytes() if found else b''\n"
        "observed=hashlib.sha256(raw).hexdigest() if found else None\n"
        "score=float(found and r['case']['requires'] in raw.decode())\n"
        "Path('observation.json').write_text(json.dumps({'discovered':found,'skill':observed,'score':score}))\n"
        "print(json.dumps({'score':score,'artifact_paths':['observation.json'],'cost_usd':0,"
        "'observed_skill_sha256':observed}))\n", encoding="utf-8")
    cases = tmp_path / "canary-cases.json"
    cases.write_text(json.dumps({"cases": [{"case_id": "canary-new", "requires": "inspect the pinned commit",
                                           "private": "CANARY_PRIVATE_EXPECTATION"}]}), encoding="utf-8")
    spec["skill_admission"] = {"cases_file": str(cases), "evaluator": str(evaluator), "minimum_score": 1.0}
    path.write_text(json.dumps(spec), encoding="utf-8")
    return job_profile


def enqueue(profile, capsys):
    _, parser, _, plan, _, path, ctx, _, _ = profile
    code, job = command(ctx, parser, capsys, "study-enqueue", plan.gap_id, "--protocol-file", str(path))
    assert code == 0, job
    return job


def test_study_activates_exact_native_skill_after_reserved_canary(admission_job, capsys):
    home, parser, _, _, _, _, ctx, calls, web_calls = admission_job
    job = enqueue(admission_job, capsys)
    code, result = command(ctx, parser, capsys, "study-work")
    assert code == 0 and result["status"] == "completed", result
    active = list((home / "skills").glob("nara-learned-*/SKILL.md"))
    assert len(active) == 1
    assert active[0].parent.name in {skill["name"] for skill in find_all_skills()}
    assert "CANARY_PRIVATE_EXPECTATION" not in json.dumps(calls + web_calls)
    mission = MissionStore.open_default().get(job["mission_id"])
    admission = mission.diagnostics["skill_admission"]
    assert admission["status"] == "active" and len(admission["observations"]) == 2
    evolution = EvolutionLab.open_default()
    assert evolution.active_variant(admission["experiment_id"]) == admission["variant_id"]
    assert evolution.reload_variant(admission["variant_id"]) == active[0].read_bytes()
    assert open_learning_lab().verified_evaluation(admission["candidate_id"])["passed"]


def test_failed_canary_never_publishes_native_skill(admission_job, capsys):
    home, parser, registry, plan, spec, _, ctx, _, _ = admission_job
    canary = Path(spec["skill_admission"]["cases_file"])
    canary.write_text(json.dumps({"cases": [{"case_id": "canary-new", "requires": "missing procedure"}]}), encoding="utf-8")
    enqueue(admission_job, capsys)
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "admission_failed", result
    assert not list((home / "skills").glob("nara-learned-*/SKILL.md"))
    assert registry.gap(plan.gap_id)["state"] == "unresolved"


def test_admission_cases_are_disjoint_and_frozen_before_research(admission_job, capsys):
    _, parser, _, plan, spec, path, ctx, calls, web_calls = admission_job
    canary = Path(spec["skill_admission"]["cases_file"])
    canary.write_text(json.dumps({"cases": [{"case_id": "holdout", "requires": "same case"}]}), encoding="utf-8")
    code, failure = command(ctx, parser, capsys, "study-enqueue", plan.gap_id, "--protocol-file", str(path))
    assert code == 1 and "disjoint" in failure["message"]
    assert calls == [] and web_calls == []


def test_admitted_skill_can_be_rolled_back_even_if_case_files_change(admission_job, capsys):
    home, parser, _, _, _, _, ctx, _, _ = admission_job
    job = enqueue(admission_job, capsys)
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "completed", result
    missions = MissionStore.open_default()
    state = missions.get(job["mission_id"]).diagnostics["skill_admission"]
    protocol = json.loads(Path(job["constraints"]["protocol"]["path"]).read_text(encoding="utf-8-sig"))
    Path(protocol["skill_admission"]["files"]["cases_file"]["path"]).write_bytes(b"changed")
    for _ in range(2):
        code, rolled = command(ctx, parser, capsys, "study-rollback", job["mission_id"], "--reason", "operator rollback")
        assert code == 0 and rolled["status"] == "rolled_back", rolled
    assert not list((home / "skills").glob("nara-learned-*/SKILL.md"))
    assert EvolutionLab.open_default().active_variant(state["experiment_id"]) == state["experiment_id"] + ":baseline"
    assert open_learning_lab().memory.get("procedure:" + state["candidate_id"])["status"] == "rejected"


@pytest.mark.parametrize("boundary", ["pending", "observed", "approved", "active"])
def test_admission_restart_never_repeats_confirmed_calls(admission_job, capsys, monkeypatch, boundary):
    from plugins.mission_control.study_admission import StudyAdmission

    _, parser, _, _, _, _, ctx, calls, web_calls = admission_job
    job = enqueue(admission_job, capsys)
    save = StudyAdmission._save

    class Interrupted(BaseException):
        pass

    def stop(self):
        save(self)
        state = self.state
        match = {"pending": bool(state["pending_call"]), "observed": len(state["observations"]) == 1,
                 "approved": state["status"] == "approved", "active": state["status"] == "active"}[boundary]
        if match:
            raise Interrupted()

    with monkeypatch.context() as patch:
        patch.setattr(StudyAdmission, "_save", stop)
        with pytest.raises(Interrupted):
            command(ctx, parser, capsys, "study-work")
    capsys.readouterr()
    _, resumed = command(ctx, parser, capsys, "study-work")
    assert resumed["status"] == ("admission_failed" if boundary == "pending" else "completed"), resumed
    state = MissionStore.open_default().get(job["mission_id"]).diagnostics["skill_admission"]
    assert len(state["observations"]) == (0 if boundary == "pending" else 2)
    assert len(calls) == 1 and len(web_calls) == 2


def test_publication_retries_without_new_canaries_or_duplicate_memory(admission_job, capsys, monkeypatch):
    from plugins.mission_control.learning import LearningLab

    _, parser, _, _, _, _, ctx, calls, web_calls = admission_job
    job = enqueue(admission_job, capsys)
    promote = LearningLab.promote

    def interrupted(self, *args, **kwargs):
        promote(self, *args, **kwargs)
        raise OSError("transient publication interruption")

    with monkeypatch.context() as patch:
        patch.setattr(LearningLab, "promote", interrupted)
        _, pending = command(ctx, parser, capsys, "study-work")
    assert pending["status"] == "publication_pending", pending
    code, listed = command(ctx, parser, capsys, "study-jobs")
    observed = next(row for row in listed if row["job_id"] == job["mission_id"])
    assert code == 0 and observed["admission"]["status"] == "publishing"
    assert observed["admission"]["reason"] == "transient publication interruption"
    store = MissionStore.open_default()
    before = store.get(job["mission_id"]).diagnostics["skill_admission"]
    lab = open_learning_lab()
    memory = lab.memory.get("procedure:" + before["candidate_id"])
    _, finished = command(ctx, parser, capsys, "study-work")
    assert finished["status"] == "completed", finished
    after = store.get(job["mission_id"]).diagnostics["skill_admission"]
    assert after["observations"] == before["observations"] and len(calls) == 1 and len(web_calls) == 2
    assert lab.memory.get("procedure:" + before["candidate_id"])["version"] == memory["version"]


def test_gateway_worker_automatically_admits_the_verified_skill(admission_job):
    from tests.waiting import wait_until

    home, _, _, _, spec, _, ctx, _, _ = admission_job
    ctx.get_config = lambda key, default=None: {"enabled": True, "protocols": {"repositories": spec}, "interval_seconds": 600}
    hook = ctx.hooks["on_gateway_housekeeping"]
    assert hook()["study"]["state"] == "started"
    try:
        wait_until(lambda: any(job.status == "completed" and job.constraints.get("study_job")
                               for job in MissionStore.open_default().list()),
                   timeout=30, what="background native skill admission")
        assert list((home / "skills").glob("nara-learned-*/SKILL.md"))
    finally:
        wait_until(lambda: hook()["study"]["state"] == "not_due", timeout=30, what="background admission worker exit")


def test_canary_with_wrong_skill_identity_cannot_activate(admission_job, capsys):
    home, parser, _, _, spec, _, ctx, _, _ = admission_job
    path = Path(spec["skill_admission"]["evaluator"])
    path.write_text(path.read_text(encoding="utf-8-sig").replace("'observed_skill_sha256':observed", "'observed_skill_sha256':'wrong-hash'"), encoding="utf-8")
    enqueue(admission_job, capsys)
    _, result = command(ctx, parser, capsys, "study-work")
    assert result["status"] == "failed" and "exact declared native skill" in result["reason"], result
    assert not list((home / "skills").glob("nara-learned-*/SKILL.md"))


def test_corrupt_canary_after_partial_publication_withdraws_the_skill(admission_job, capsys, monkeypatch):
    from plugins.mission_control.learning import LearningLab

    home, parser, _, _, _, _, ctx, _, _ = admission_job
    job = enqueue(admission_job, capsys)
    promote = LearningLab.promote

    def interrupted(self, *args, **kwargs):
        promote(self, *args, **kwargs)
        raise OSError("publication not committed")

    with monkeypatch.context() as patch:
        patch.setattr(LearningLab, "promote", interrupted)
        _, pending = command(ctx, parser, capsys, "study-work")
    assert pending["status"] == "publication_pending"
    state = MissionStore.open_default().get(job["mission_id"]).diagnostics["skill_admission"]
    Path(state["observations"][0]["result"]["evidence"][-1]["path"]).write_bytes(b"corrupted")
    _, failed = command(ctx, parser, capsys, "study-work")
    assert failed["status"] == "failed", failed
    assert not list((home / "skills").glob("nara-learned-*/SKILL.md"))
    assert open_learning_lab().memory.get("procedure:" + state["candidate_id"])["status"] == "rejected"
    assert EvolutionLab.open_default().active_variant(state["experiment_id"]) == state["experiment_id"] + ":baseline"


@pytest.mark.parametrize("stage", ["pending", "observed", "activated"])
def test_killed_admission_recovers_without_reexecuting_canaries(admission_job, capsys, tmp_path, stage):
    import os
    import subprocess
    import sys
    from tests.waiting import wait_until

    home, parser, _, _, spec, _, ctx, calls, web_calls = admission_job
    trace = tmp_path / "canary-calls.jsonl"
    evaluator = Path(spec["skill_admission"]["evaluator"])
    evaluator.write_text(evaluator.read_text(encoding="utf-8-sig").replace(
        "r=json.load(sys.stdin)\n",
        "r=json.load(sys.stdin)\n"
        f"with open({str(trace)!r},'a',encoding='utf-8') as out:\n"
        " out.write(json.dumps(r['canary']['variant'])+'\\n')\n"), encoding="utf-8")
    job = enqueue(admission_job, capsys)
    marker, logs = tmp_path / "ready", tmp_path / "worker.log"
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG"}}
    env["NARA_HOME"] = str(home)
    with logs.open("w", encoding="utf-8") as output:
        child = subprocess.Popen([sys.executable, "-m", "tests.plugins.mission_control.study_admission_worker",
                                  stage, str(marker)], env=env, stdout=output, stderr=output)
        try:
            wait_until(lambda: marker.exists() or child.poll() is not None,
                       timeout=30, what="owned admission checkpoint")
            assert marker.exists() and child.poll() is None, logs.read_text(encoding="utf-8-sig")
            code, busy = command(ctx, parser, capsys, "study-work")
            assert code == 1 and "already executing" in busy["message"]
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
    _, resumed = command(ctx, parser, capsys, "study-work")
    assert resumed["status"] == ("admission_failed" if stage == "pending" else "completed"), resumed
    observed = [json.loads(line) for line in trace.read_text(encoding="utf-8-sig").splitlines()] if trace.exists() else []
    assert observed == ([] if stage == "pending" else ["baseline", "candidate"])
    assert calls == [] and web_calls == []
    assert MissionStore.open_default().verify_projection(job["mission_id"])


def test_pending_publication_can_be_cancelled_before_a_skill_file_exists(admission_job, capsys, monkeypatch):
    from plugins.mission_control import learning_deployment

    home, parser, _, _, _, _, ctx, _, _ = admission_job
    job = enqueue(admission_job, capsys)

    def unavailable(*args):
        raise OSError("native skill directory unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(learning_deployment, "_publish", unavailable)
        _, pending = command(ctx, parser, capsys, "study-work")
    assert pending["status"] == "publication_pending", pending
    code, rolled = command(ctx, parser, capsys, "study-rollback", job["mission_id"], "--reason", "cancel publication")
    assert code == 0 and rolled["status"] == "rolled_back", rolled
    state = MissionStore.open_default().get(job["mission_id"]).diagnostics["skill_admission"]
    assert state["unpublished_cancelled"]
    assert open_learning_lab().memory.get("procedure:" + state["candidate_id"])["status"] == "rejected"
    assert not list((home / "skills").rglob("SKILL.md"))
