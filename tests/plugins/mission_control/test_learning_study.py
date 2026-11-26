"""Model-authored procedures must traverse the existing evidence and promotion gates."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.plugin_llm import PluginLlmStructuredResult, PluginLlmUsage
from nara_constants import reset_nara_home_override
from plugins.mission_control.cli import mission_command
from tests.plugins.mission_control.test_learning_media_procedure import _command, _setup, STEP_QUOTE
from tests.plugins.mission_control.test_plugin import _Context


def _model(payload, calls, before_return=lambda: None):
    def complete_structured(**kwargs):
        calls.append(kwargs)
        before_return()
        return PluginLlmStructuredResult(
            text=json.dumps(payload), parsed=payload, content_type="json",
            provider="fixture", model="study-test", agent_id="",
            usage=PluginLlmUsage(input_tokens=30, output_tokens=20, total_tokens=50),
        )
    return SimpleNamespace(complete_structured=complete_structured)


def _valid():
    return {"name": "Inspect repository", "steps": [
        {"instruction": "inspect the pinned commit", "source_span_id": "s0001"},
    ], "decline_reason": ""}


def _study(parser, source, llm, capsys):
    args = parser.parse_args([
        "learn-media-study", source["source_id"], "--objective", "Check a repository before use",
    ])
    code = mission_command(args, llm=llm)
    return code, json.loads(capsys.readouterr().out)


def test_model_candidate_cli_has_provenance_and_reserved_transfer_gate(tmp_path, monkeypatch, capsys):
    home, token, parser, fabric, source, _, evaluator, cases = _setup(tmp_path, monkeypatch)
    calls = []
    try:
        from plugins.mission_control import register

        context = _Context()
        context.llm = _model(_valid(), calls)
        register(context)
        args = parser.parse_args([
            "learn-media-study", source["source_id"], "--objective", "Check a repository before use",
        ])
        code = context.command["handler_fn"](args)
        result = json.loads(capsys.readouterr().out)
        assert code == 0 and result["status"] == "candidate"
        assert len(calls) == 1
        assert calls[0]["task"] in context.auxiliary_tasks
        model_input = json.loads(calls[0]["input"][0]["text"])
        assert model_input["objective"] == "Check a repository before use"
        spans = model_input["source_spans"]
        for span in spans:
            assert span["text"] == source["extracted_text"][span["start"]:span["end"]]
        selected = next(span for span in spans if span["id"] == "s0001")
        assert STEP_QUOTE in selected["text"]
        evidence = Path(result["evidence"]["path"]).read_bytes()
        assert hashlib.sha256(evidence).hexdigest() == result["evidence"]["sha256"]
        archived = json.loads(evidence)
        assert archived["parsed"] == _valid() and archived["usage"]["total_tokens"] == 50
        request_hash = archived["request_sha256"]
        request = json.loads((fabric.root / "sources" / request_hash[:2] / request_hash).read_bytes())
        assert request["input"] == model_input
        candidate_id = result["candidate"]["candidate_id"]
        provenance = []
        for artifact in result["candidate"]["evidence_artifact_ids"]:
            digest = artifact.removeprefix("sha256:")
            path = fabric.root / "sources" / digest[:2] / digest
            if path.exists():
                try:
                    item = json.loads(path.read_bytes())
                except json.JSONDecodeError:
                    continue
                if item.get("kind") == "media_procedure_provenance":
                    provenance.append(item)
        assert len(provenance) == 1 and provenance[0]["quotes"] == [selected["text"]]
        code, denied = _command(parser, capsys, "learn-promote", candidate_id)
        assert code == 1 and "no reserved transfer evaluation" in denied["message"]
        assert not list((home / "skills").glob("nara-learned-*"))
        code, report = _command(
            parser, capsys, "learn-evaluate", candidate_id,
            "--cases-file", str(cases), "--evaluator", str(evaluator),
            "--development-case", "development",
        )
        assert code == 0 and report["passed"]
        code, promoted = _command(parser, capsys, "learn-promote", candidate_id)
        assert code == 0 and Path(promoted["skill_path"], "SKILL.md").is_file()
        code, rolled = _command(parser, capsys, "learn-rollback", candidate_id)
        assert code == 0 and rolled["status"] == "rolled_back"
    finally:
        reset_nara_home_override(token)


@pytest.mark.parametrize("payload", [
    None,
    {**_valid(), "steps": "wrong type"},
    {**_valid(), "steps": [{"instruction": "inspect", "source_span_id": 42}]},
    {**_valid(), "steps": [{"instruction": "inspect", "source_span_id": "invented"}]},
    {**_valid(), "steps": [{"instruction": "inspect", "quote": "invented evidence"}]},
    {**_valid(), "decline_reason": "cannot support this"},
])
def test_invalid_model_output_archived_without_candidate(tmp_path, monkeypatch, capsys, payload):
    home, token, parser, fabric, source, _, _, _ = _setup(tmp_path, monkeypatch)
    try:
        code, result = _study(parser, source, _model(payload, []), capsys)
        assert code == 1 and "media study failed" in result["message"]
        digest = result["message"].split("sha256:")[1]
        receipt = json.loads((fabric.root / "sources" / digest[:2] / digest).read_bytes())
        assert receipt["status"] == "failed" and receipt["parsed"] == payload
        assert receipt["failure_stage"] == "validation" and receipt["reason"]
        assert not list(home.rglob("*.candidate.json"))
        assert not list((home / "skills").glob("nara-learned-*"))
        assert not list((home / "plugin-data/mission-control/learning/candidates").glob("*.json"))
    finally:
        reset_nara_home_override(token)


@pytest.mark.parametrize("when", ["before", "during"])
def test_study_rechecks_source_around_model_call(tmp_path, monkeypatch, capsys, when):
    home, token, parser, _, source, _, _, _ = _setup(tmp_path, monkeypatch)
    calls = []
    def corrupt():
        Path(source["stored_path"]).write_bytes(b"changed evidence")
    try:
        if when == "before":
            corrupt()
        llm = _model(_valid(), calls, corrupt if when == "during" else lambda: None)
        code, _ = _study(parser, source, llm, capsys)
        assert code == 1 and len(calls) == (1 if when == "during" else 0)
        assert not list((home / "plugin-data/mission-control/learning/candidates").glob("*.json"))
    finally:
        reset_nara_home_override(token)


def test_model_can_decline_without_inventing_a_skill(tmp_path, monkeypatch, capsys):
    home, token, parser, _, source, _, _, _ = _setup(tmp_path, monkeypatch)
    try:
        payload = {"name": "", "steps": [], "decline_reason": "No usable procedure"}
        code, result = _study(parser, source, _model(payload, []), capsys)
        assert code == 0 and result["status"] == "no_procedure" and "candidate" not in result
        assert not list((home / "skills").glob("nara-learned-*"))
    finally:
        reset_nara_home_override(token)


def test_transport_failure_keeps_diagnostics_without_error_credentials(tmp_path, monkeypatch, capsys):
    _, token, parser, fabric, source, _, _, _ = _setup(tmp_path, monkeypatch)
    def unavailable(**kwargs):
        raise ConnectionError("https://provider.invalid/?api_key=DO_NOT_ARCHIVE")
    try:
        code, result = _study(parser, source, SimpleNamespace(complete_structured=unavailable), capsys)
        assert code == 1 and "DO_NOT_ARCHIVE" not in result["message"]
        digest = result["message"].split("sha256:")[1]
        raw = (fabric.root / "sources" / digest[:2] / digest).read_bytes()
        receipt = json.loads(raw)
        assert receipt["failure_stage"] == "generation" and receipt["error_type"] == "ConnectionError"
        assert b"DO_NOT_ARCHIVE" not in raw
    finally:
        reset_nara_home_override(token)
