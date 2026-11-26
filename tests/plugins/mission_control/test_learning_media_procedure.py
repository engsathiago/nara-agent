"""A media-sourced procedure remains inactive until its own transfer eval."""

import argparse
import json
import shutil
from pathlib import Path

from extensions.nara_temporal_memory.nara_temporal import TemporalMemoryStore
from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control.cli import mission_command, register_cli
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_github_source import verify_quoted_repository


REPO = "github.com/ggml-org/whisper.cpp"
STEP_QUOTE = "inspect the pinned commit"


def _setup(tmp_path, monkeypatch):
    import extensions.nara_temporal_memory.nara_temporal as provider_source

    home = tmp_path / "profile"
    (home / "plugins").mkdir(parents=True)
    shutil.copytree(Path(provider_source.__file__).parent, home / "plugins" / "nara_temporal")
    (home / "config.yaml").write_text("memory:\n  provider: nara_temporal\n", encoding="utf-8")
    monkeypatch.setenv("NARA_HOME", str(home))
    token = set_nara_home_override(home)
    lesson = tmp_path / "lesson.txt"
    lesson.write_text(f"The screen shows {REPO}. Then {STEP_QUOTE} before using it.")
    fabric = LearningFabric.open_default()
    source = fabric.ingest_file(lesson, modality="document", license_name="MIT")

    def official(url):
        if url.endswith("?per_page=1"):
            return [{"sha": "a" * 40}]
        return {"full_name": "ggml-org/whisper.cpp", "private": False,
                "visibility": "public", "html_url": "https://github.com/ggml-org/whisper.cpp"}

    monkeypatch.setattr("plugins.mission_control.learning_github_source._github_json", official)
    repo = verify_quoted_repository(fabric, source["source_id"], REPO)["claim"]
    parser = argparse.ArgumentParser()
    register_cli(parser)
    evaluator = tmp_path / "evaluator.py"
    evaluator.write_text(
        "import json, sys\n"
        "from pathlib import Path\n"
        "request = json.load(sys.stdin)\n"
        "steps = ' '.join(request['candidate']['steps']) if request['candidate'] else ''\n"
        "score = float(request['case']['requires'] in steps)\n"
        "Path('proof.txt').write_text(str(score))\n"
        "print(json.dumps({'score': score, 'artifact_paths': ['proof.txt']}))\n",
        encoding="utf-8",
    )
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"cases": [
        {"case_id": "development", "requires": "never"},
        {"case_id": "holdout", "requires": "pinned commit"},
    ]}))
    return home, token, parser, fabric, source, repo, evaluator, cases


def _command(parser, capsys, *argv):
    code = mission_command(parser.parse_args(list(argv)))
    return code, json.loads(capsys.readouterr().out)


def test_media_candidate_requires_quote_and_transfer_before_skill(tmp_path, monkeypatch, capsys):
    home, token, parser, fabric, source, repo, evaluator, cases = _setup(tmp_path, monkeypatch)
    try:
        code, failed = _command(
            parser, capsys, "learn-media-procedure", source["source_id"],
            "--repo-claim", repo["claim_id"], "--name", "Invented step",
            "--step", "download secrets", "--quote", "the video never said this",
        )
        assert code == 1 and "exact quote" in failed["message"]
        code, candidate = _command(
            parser, capsys, "learn-media-procedure", source["source_id"],
            "--repo-claim", repo["claim_id"], "--name", "Inspect a pinned repository",
            "--step", "inspect the pinned commit and inspect the README",
            "--quote", STEP_QUOTE,
        )
        assert code == 0
        code, repeated = _command(
            parser, capsys, "learn-media-procedure", source["source_id"],
            "--repo-claim", repo["claim_id"], "--name", "Inspect a pinned repository",
            "--step", "inspect the pinned commit and inspect the README",
            "--quote", STEP_QUOTE,
        )
        assert code == 0 and repeated["candidate_id"] == candidate["candidate_id"]
        assert candidate["mission_id"] == f"media:{source['source_id']}"
        assert not list((home / "skills").glob("nara-learned-*"))
        memory = TemporalMemoryStore(home / "memories" / "nara-temporal.db")
        assert memory.get(f"procedure:{candidate['candidate_id']}")["status"] == "candidate"
        code, result = _command(parser, capsys, "learn-promote", candidate["candidate_id"])
        assert code == 1
        assert "no reserved transfer evaluation" in result["message"]
        code, report = _command(
            parser, capsys, "learn-evaluate", candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "development",
        )
        assert code == 0 and report["passed"] is True
        code, promoted = _command(parser, capsys, "learn-promote", candidate["candidate_id"])
        assert code == 0
        assert "source_media:" in Path(promoted["skill_path"], "SKILL.md").read_text()
        assert memory.get(f"procedure:{candidate['candidate_id']}")["status"] == "active"
        assert fabric.claim(repo["claim_id"])["status"] == "verified"
    finally:
        reset_nara_home_override(token)


def test_changed_media_provenance_blocks_promotion(tmp_path, monkeypatch, capsys):
    home, token, parser, _fabric, source, repo, evaluator, cases = _setup(tmp_path, monkeypatch)
    try:
        _, candidate = _command(
            parser, capsys, "learn-media-procedure", source["source_id"],
            "--repo-claim", repo["claim_id"], "--name", "Inspect a pinned repository",
            "--step", "inspect the pinned commit", "--quote", STEP_QUOTE,
        )
        _, report = _command(
            parser, capsys, "learn-evaluate", candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "development",
        )
        assert report["passed"] is True
        Path(source["stored_path"]).write_text("tampered")
        code, failed = _command(parser, capsys, "learn-promote", candidate["candidate_id"])
        assert code == 1
        assert "cited source archive has changed" in failed["message"]
        assert TemporalMemoryStore(home / "memories" / "nara-temporal.db").get(
            f"procedure:{candidate['candidate_id']}")["status"] == "candidate"
    finally:
        reset_nara_home_override(token)


def test_changed_quote_mapping_blocks_evaluation(tmp_path, monkeypatch, capsys):
    home, token, parser, fabric, source, repo, evaluator, cases = _setup(tmp_path, monkeypatch)
    try:
        _, candidate = _command(
            parser, capsys, "learn-media-procedure", source["source_id"],
            "--repo-claim", repo["claim_id"], "--name", "Inspect a pinned repository",
            "--step", "inspect the pinned commit", "--quote", STEP_QUOTE,
        )
        for artifact_id in candidate["evidence_artifact_ids"]:
            digest = artifact_id.removeprefix("sha256:")
            path = fabric.root / "sources" / digest[:2] / digest
            if path.stat().st_size > 100_000:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except (UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("kind") == "media_procedure_provenance":
                path.write_text("{}")
                break
        else:
            raise AssertionError("provenance archive missing")
        code, failed = _command(
            parser, capsys, "learn-evaluate", candidate["candidate_id"],
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "development",
        )
        assert code == 1
        assert "archived claim evidence has changed" in failed["message"]
        assert not list((home / "skills").glob("nara-learned-*"))
    finally:
        reset_nara_home_override(token)
