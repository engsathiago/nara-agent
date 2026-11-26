"""A declared acceptance floor must survive evaluation and promotion."""

import json
from pathlib import Path

import pytest

from nara_constants import reset_nara_home_override
from tests.plugins.mission_control.test_learning_eval_cli import _command, _prepare


def test_cli_rejects_partial_gain_below_declared_floor(tmp_path, monkeypatch, capsys):
    home, token, parser, evaluator, cases = _prepare(tmp_path, monkeypatch)
    try:
        evaluator.write_text(
            "import json, sys\nfrom pathlib import Path\n"
            "r = json.load(sys.stdin)\n"
            "score = r['case']['score'] if r['candidate'] else 0.0\n"
            "Path('proof.json').write_text(json.dumps({'score':score}))\n"
            "print(json.dumps({'score':score,'artifact_paths':['proof.json']}))\n",
            encoding="utf-8",
        )
        cases.write_text(json.dumps({"cases": [
            {"case_id": "dev-a", "score": 1.0},
            {"case_id": "partial", "score": 0.5},
            {"case_id": "complete", "score": 1.0},
        ]}), encoding="utf-8")
        _, candidate = _command(parser, capsys, "learn-extract", "mission-a")
        code, report = _command(
            parser, capsys, "learn-evaluate", candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "dev-a", "--minimum-candidate-score", "1.0",
        )
        assert code == 0 and report["mean_delta"] == 0.75 and report["regressions"] == 0
        assert report["minimum_candidate_score"] == 1.0
        assert report["below_minimum"] == ["partial"] and report["passed"] is False
        code, denied = _command(parser, capsys, "learn-promote", candidate["candidate_id"])
        assert code == 1 and "did not pass" in denied["message"]
        assert not list((home / "skills").glob("nara-learned-*"))
        report_path = home / "plugin-data/mission-control/learning/candidates" / f"{candidate['candidate_id']}.eval.json"
        report["passed"] = True
        report_path.write_text(json.dumps(report), encoding="utf-8")
        code, denied = _command(parser, capsys, "learn-promote", candidate["candidate_id"])
        assert code == 1 and "minimum" in denied["message"]
    finally:
        reset_nara_home_override(token)


@pytest.mark.parametrize("minimum", ["nan", "inf", "-0.1", "1.1"])
def test_invalid_floor_does_not_create_an_evaluation(tmp_path, monkeypatch, capsys, minimum):
    home, token, parser, evaluator, cases = _prepare(tmp_path, monkeypatch)
    try:
        _, candidate = _command(parser, capsys, "learn-extract", "mission-a")
        code, result = _command(
            parser, capsys, "learn-evaluate", candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "dev-a", f"--minimum-candidate-score={minimum}",
        )
        assert code == 1 and "minimum" in result["message"]
        assert not list(home.rglob("*.eval.json"))
    finally:
        reset_nara_home_override(token)


def test_complete_transfer_can_be_promoted_with_floor(tmp_path, monkeypatch, capsys):
    _, token, parser, evaluator, cases = _prepare(tmp_path, monkeypatch)
    try:
        _, candidate = _command(parser, capsys, "learn-extract", "mission-a")
        code, report = _command(
            parser, capsys, "learn-evaluate", candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "dev-a", "--minimum-candidate-score", "1.0",
        )
        assert code == 0 and report["passed"] and report["below_minimum"] == []
        code, promoted = _command(parser, capsys, "learn-promote", candidate["candidate_id"])
        assert code == 0 and Path(promoted["skill_path"], "SKILL.md").is_file()
    finally:
        reset_nara_home_override(token)
