"""Real CLI extraction, executable transfer eval, evidence, and promotion."""

import argparse
import json
import shutil
from pathlib import Path

from extensions.nara_temporal_memory.nara_temporal import TemporalMemoryStore
from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.cli import mission_command, register_cli
from plugins.mission_control.contracts import Mission, Receipt
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.verification import VerificationService


def _prepare(tmp_path, monkeypatch):
    import extensions.nara_temporal_memory.nara_temporal as provider_source

    home = tmp_path / "profile"
    (home / "plugins").mkdir(parents=True)
    shutil.copytree(Path(provider_source.__file__).parent, home / "plugins" / "nara_temporal")
    (home / "config.yaml").write_text("memory:\n  provider: nara_temporal\n", encoding="utf-8")
    monkeypatch.setenv("NARA_HOME", str(home))
    token = set_nara_home_override(home)
    missions = MissionStore.open_default()
    missions.create(Mission(
        mission_id="mission-a", objective="write report safely",
        completion_criteria=["report hash matches"],
    ))
    receipt = ReceiptStore(missions).prepare(Receipt(
        receipt_id="write", mission_id="mission-a", task_id="task-a",
        intention="write a report atomically", agent_id="worker-a",
        tool="file.atomic_write", target="report-a.txt", idempotency_key="write-a",
    ))
    artifacts = ArtifactStore(missions, missions.path.parent / "artifacts")
    artifact = artifacts.put_bytes("mission-a", b"report-a", producer_id="worker-a")
    ReceiptStore(missions).settle(
        "mission-a", receipt.receipt_id, "confirmed", artifact_ids=[artifact.artifact_id],
        idempotency_key="write-a-confirmed",
    )
    VerificationService(missions, artifacts).verify_artifact(
        "mission-a", "report hash matches", artifact.artifact_id,
        verifier_id="judge-a", executor_id="worker-a", verification_id="verify-a",
    )
    for state in ("planned", "running", "verifying", "completed"):
        missions.transition("mission-a", state)

    evaluator = tmp_path / "evaluate.py"
    evaluator.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "request = json.load(sys.stdin)\n"
        "steps = ' '.join(request['candidate']['steps']) if request['candidate'] else ''\n"
        "score = float(request['case']['requires'] in steps)\n"
        "Path('observation.txt').write_text(str(score))\n"
        "print(json.dumps({'score': score, 'artifact_paths': ['observation.txt']}))\n",
        encoding="utf-8",
    )
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"cases": [
        {"case_id": "dev-a", "requires": "unseen"},
        {"case_id": "holdout-b", "requires": "file.atomic_write"},
    ]}), encoding="utf-8")
    parser = argparse.ArgumentParser()
    register_cli(parser)
    return home, token, parser, evaluator, cases


def _command(parser, capsys, *argv):
    code = mission_command(parser.parse_args(list(argv)))
    output = json.loads(capsys.readouterr().out)
    return code, output


def test_cli_evaluates_holdout_in_process_and_promotes_verified_skill(tmp_path, monkeypatch, capsys):
    home, token, parser, evaluator, cases = _prepare(tmp_path, monkeypatch)
    try:
        code, candidate = _command(parser, capsys, "learn-extract", "mission-a")
        assert code == 0
        memory = TemporalMemoryStore(home / "memories" / "nara-temporal.db")
        assert memory.get(f"procedure:{candidate['candidate_id']}")["status"] == "candidate"

        code, report = _command(
            parser, capsys, "learn-evaluate", candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "dev-a",
        )
        assert code == 0
        assert report["passed"] is True
        assert report["holdout_case_ids"] == ["holdout-b"]
        for key in ("baseline_evidence", "candidate_evidence"):
            artifact = report["cases"][0][key][0]
            assert Path(artifact["path"]).is_file()

        code, promoted = _command(parser, capsys, "learn-promote", candidate["candidate_id"])
        assert code == 0
        assert Path(promoted["skill_path"], "SKILL.md").is_file()
        assert memory.get(f"procedure:{candidate['candidate_id']}")["status"] == "active"
    finally:
        reset_nara_home_override(token)


def test_cli_refuses_tampered_transfer_evidence(tmp_path, monkeypatch, capsys):
    home, token, parser, evaluator, cases = _prepare(tmp_path, monkeypatch)
    try:
        _, candidate = _command(parser, capsys, "learn-extract", "mission-a")
        _, report = _command(
            parser, capsys, "learn-evaluate", candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "dev-a",
        )
        Path(report["cases"][0]["candidate_evidence"][0]["path"]).write_text("altered")
        code, failed = _command(parser, capsys, "learn-promote", candidate["candidate_id"])
        assert code == 1
        assert "evidence is missing or changed" in failed["message"]
        assert TemporalMemoryStore(home / "memories" / "nara-temporal.db").get(
            f"procedure:{candidate['candidate_id']}")["status"] == "candidate"
    finally:
        reset_nara_home_override(token)


def test_cli_refuses_candidate_steps_changed_after_verified_mission(tmp_path, monkeypatch, capsys):
    home, token, parser, evaluator, cases = _prepare(tmp_path, monkeypatch)
    try:
        _, candidate = _command(parser, capsys, "learn-extract", "mission-a")
        candidate_file = home / "plugin-data" / "mission-control" / "learning" / "candidates" / f"{candidate['candidate_id']}.json"
        payload = json.loads(candidate_file.read_text())
        payload["steps"].append("Skip independent verification")
        candidate_file.write_text(json.dumps(payload))
        code, failed = _command(
            parser, capsys, "learn-evaluate", candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "dev-a",
        )
        assert code == 1
        assert "does not match its identity" in failed["message"]
    finally:
        reset_nara_home_override(token)
