"""Verified skills remain verifiable and recover publication without changing their content."""

import json
from pathlib import Path

import pytest

from nara_constants import reset_nara_home_override
from plugins.mission_control.learning import LearningLab
from plugins.mission_control.learning_cli import open_learning_lab
from tests.plugins.mission_control.test_learning_eval_cli import _command, _prepare
from tools.skills_tool import find_all_skills


@pytest.fixture
def evaluated(tmp_path, monkeypatch, capsys):
    home, token, parser, evaluator, cases = _prepare(tmp_path, monkeypatch)
    try:
        _, candidate = _command(parser, capsys, "learn-extract", "mission-a")
        _, report = _command(parser, capsys, "learn-evaluate", candidate["candidate_id"],
                             "--cases-file", str(cases), "--evaluator", str(evaluator),
                             "--development-case", "dev-a")
        assert report["passed"]
        yield home, parser, candidate["candidate_id"], report
    finally:
        reset_nara_home_override(token)


def test_repeated_promotion_preserves_proof_skill_and_memory_version(evaluated, capsys):
    _, parser, identity, report = evaluated
    _, first = _command(parser, capsys, "learn-promote", identity)
    lab = open_learning_lab()
    skill = Path(first["skill_path"]) / "SKILL.md"
    before, memory = skill.read_bytes(), lab.memory.get("procedure:" + identity)
    code, repeated = _command(parser, capsys, "learn-promote", identity)
    assert code == 0, repeated
    assert repeated == first and skill.read_bytes() == before
    assert lab.verified_evaluation(identity) == report
    assert lab.memory.get("procedure:" + identity)["version"] == memory["version"]
    assert skill.parent.name in {item["name"] for item in find_all_skills()}


@pytest.mark.parametrize("operation", ["promote", "rollback"])
def test_completed_metadata_write_can_be_replayed_without_repeating_effects(evaluated, capsys, monkeypatch, operation):
    _, parser, identity, report = evaluated
    if operation == "rollback":
        _, initial = _command(parser, capsys, "learn-promote", identity)
        active = Path(initial["skill_path"])
    write = LearningLab._write_json

    class Interrupted(BaseException):
        pass

    def crash(self, path, payload):
        write(self, path, payload)
        if path == self._candidate_path(identity) and payload.get("status") == {
            "promote": "promoted", "rollback": "rolled_back"}[operation]:
            raise Interrupted()

    with monkeypatch.context() as patch:
        patch.setattr(LearningLab, "_write_json", crash)
        with pytest.raises(Interrupted):
            _command(parser, capsys, "learn-" + operation, identity)
    capsys.readouterr()
    lab = open_learning_lab()
    version = lab.memory.get("procedure:" + identity)["version"]
    code, resumed = _command(parser, capsys, "learn-" + operation, identity)
    assert code == 0, resumed
    assert Path(resumed["skill_path"], "SKILL.md").is_file()
    assert lab.memory.get("procedure:" + identity)["version"] == version
    assert lab.verified_evaluation(identity) == report
    if operation == "rollback":
        assert not active.exists()
        assert active.name not in {item["name"] for item in find_all_skills()}


def test_promoted_content_edits_are_still_rejected_by_evaluation(evaluated, capsys):
    _, parser, identity, _ = evaluated
    _command(parser, capsys, "learn-promote", identity)
    lab = open_learning_lab()
    path = lab._candidate_path(identity)
    candidate = json.loads(path.read_text(encoding="utf-8-sig"))
    candidate["description"] += " changed after evaluation"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    with pytest.raises(ValueError, match="changed after transfer"):
        lab.verified_evaluation(identity)


def test_repeated_promotion_does_not_overwrite_modified_skill(evaluated, capsys):
    _, parser, identity, _ = evaluated
    _, first = _command(parser, capsys, "learn-promote", identity)
    skill = Path(first["skill_path"]) / "SKILL.md"
    skill.write_text("Locally edited procedure", encoding="utf-8")
    code, result = _command(parser, capsys, "learn-promote", identity)
    assert code == 1 and "skill" in result["message"]
    assert skill.read_text(encoding="utf-8-sig") == "Locally edited procedure"


@pytest.mark.parametrize("stage", ["memory-promoted", "skill-published", "skill-removed"])
def test_killed_deployment_recovers_owned_files_and_releases_process_lock(evaluated, capsys, tmp_path, stage):
    import os
    import subprocess
    import sys
    from tests.waiting import wait_until

    home, parser, identity, report = evaluated
    action = "learn-rollback" if stage == "skill-removed" else "learn-promote"
    if stage == "skill-removed":
        _command(parser, capsys, "learn-promote", identity)
    marker, logs = tmp_path / "ready", tmp_path / "worker.log"
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG"}}
    env["NARA_HOME"] = str(home)
    with logs.open("w", encoding="utf-8") as output:
        child = subprocess.Popen([
            sys.executable, "-m", "tests.plugins.mission_control.learning_deployment_worker",
            identity, stage, str(marker)], env=env, stdout=output, stderr=output)
        try:
            wait_until(lambda: marker.exists() or child.poll() is not None,
                       timeout=30, what="owned skill deployment crash boundary")
            assert marker.exists() and child.poll() is None, logs.read_text(encoding="utf-8-sig")
            code, busy = _command(parser, capsys, action, identity)
            assert code == 1 and "already executing" in busy["message"]
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=10)
    if stage == "skill-removed":
        code, blocked = _command(parser, capsys, "learn-promote", identity)
        assert code == 1 and "rollback" in blocked["message"]
        assert not list((home / "skills").glob("nara-learned-*/SKILL.md"))
    code, resumed = _command(parser, capsys, action, identity)
    assert code == 0, resumed
    lab = open_learning_lab()
    version = lab.memory.get("procedure:" + identity)["version"]
    code, repeated = _command(parser, capsys, action, identity)
    assert code == 0 and repeated == resumed
    assert lab.memory.get("procedure:" + identity)["version"] == version
    assert lab.verified_evaluation(identity) == report
    assert Path(resumed["skill_path"], "SKILL.md").is_file()


@pytest.mark.parametrize("evaluate_active", [False, True])
def test_legacy_evaluation_without_status_binding_survives_promotion(evaluated, capsys, evaluate_active):
    home, parser, identity, _ = evaluated
    if evaluate_active:
        _command(parser, capsys, "learn-promote", identity)
        code, report = _command(parser, capsys, "learn-evaluate", identity,
                                "--cases-file", str(home.parent / "cases.json"),
                                "--evaluator", str(home.parent / "evaluate.py"),
                                "--development-case", "dev-a")
        assert code == 0 and report["passed"], report
    lab = open_learning_lab()
    for suffix in (".eval.request.json", ".eval.json"):
        path = lab.candidate_root / (identity + suffix)
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        payload.pop("candidate_status")
        path.write_text(json.dumps(payload), encoding="utf-8")
    for _ in range(2):
        code, result = _command(parser, capsys, "learn-promote", identity)
        assert code == 0, result
    assert lab.verified_evaluation(identity)["passed"]


def test_legacy_suffixed_archive_remains_recoverable(evaluated, capsys):
    _, parser, identity, _ = evaluated
    _command(parser, capsys, "learn-promote", identity)
    _, rolled = _command(parser, capsys, "learn-rollback", identity)
    archived = Path(rolled["skill_path"])
    legacy = archived.with_name(archived.name + "-old-receipt")
    archived.rename(legacy)
    lab = open_learning_lab()
    path = lab._candidate_path(identity)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    payload["skill_path"] = str(legacy)
    path.write_text(json.dumps(payload), encoding="utf-8")
    code, repeated = _command(parser, capsys, "learn-rollback", identity)
    assert code == 0 and repeated["skill_path"] == str(legacy), repeated
