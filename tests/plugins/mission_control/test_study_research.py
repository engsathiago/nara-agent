"""Source research must use actual extraction, persist provenance and leave competence unproven."""

import argparse
import json

import pytest

from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control import register
from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.cli import register_cli
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.store import MissionStore
from tests.plugins.mission_control.test_plugin import _Context


@pytest.fixture
def research_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("NARA_HOME", str(tmp_path))
    token = set_nara_home_override(tmp_path)
    registry = CompetenceRegistry.open_default()
    gap = registry.record_gap("archive", "Archive extraction failed", "PRIVATE_DIAGNOSIS", impact=4)
    parser = argparse.ArgumentParser()
    register_cli(parser)
    try:
        yield parser, registry, gap
    finally:
        reset_nara_home_override(token)


def _run(parser, gap, dispatch, capsys, *extra):
    ctx = _Context()
    ctx.dispatch_tool = dispatch
    register(ctx)
    code = ctx.command["handler_fn"](parser.parse_args([
        "study-research", gap["gap_id"], "--objective", "Python ZIP extraction documentation",
        "--domain", "docs.python.org", *extra]))
    return code, json.loads(capsys.readouterr().out)


def test_research_cli_extracts_allowed_sources_and_retains_mission_evidence(research_profile, capsys):
    parser, registry, gap = research_profile
    calls = []
    url = "https://docs.python.org/3/library/zipfile.html"
    content = "Use ZipFile.infolist to inspect archive members before extracting them."

    def dispatch(name, args):
        calls.append((name, args))
        if name == "web_search":
            return json.dumps({"success": True, "data": {"web": [
                {"url": "https://docs.python.org.attacker.invalid/install"},
                {"url": url}, {"url": url + "#duplicate"},
                {"url": "https://docs.python.org/3/tutorial/errors.html"},
            ]}})
        selected = args["urls"][0]
        return json.dumps({"results": [{"url": selected, "content": content if selected == url else "",
                                        "error": None if selected == url else "unavailable"}]})

    code, result = _run(parser, gap, dispatch, capsys, "--max-sources", "2")
    assert code == 0 and result["status"] == "sources_found"
    assert len(calls) == 3 and [call[0] for call in calls] == ["web_search", "web_extract", "web_extract"]
    assert "PRIVATE_DIAGNOSIS" not in json.dumps(calls)
    assert len(result["sources"]) == 1 and len(result["rejected"]) == 2
    source = LearningFabric.open_default().source(result["sources"][0]["source_id"])
    assert source["extracted_text"] == content and source["source_uri"] == url
    assert source["metadata"]["claims_status"] == "unverified"
    missions = MissionStore.open_default()
    mission = missions.get(result["mission_id"])
    assert mission.status == "completed" and mission.constraints["gap_id"] == gap["gap_id"]
    assert missions.verify_projection(mission.mission_id)
    archived = json.loads(ArtifactStore.open_default().read_bytes(mission.mission_id, result["receipt"]["artifact_id"]))
    assert archived["sources"] == result["sources"] and archived["calls_started"] == 3
    assert registry.gap(gap["gap_id"])["state"] == "open" and registry.current() == []


@pytest.mark.parametrize("failure", ["search", "extract", "budget", "empty"])
def test_research_stops_honestly_when_sources_or_priced_usage_are_unavailable(research_profile, capsys, failure):
    parser, registry, gap = research_profile
    if failure == "budget":
        gap = registry.record_gap("priced", "Priced research", "missing documentation", impact=4, budget_usd=1)
    calls = []
    url = "https://docs.python.org/3/library/zipfile.html"

    def dispatch(name, args):
        calls.append(name)
        if name == "web_search":
            if failure == "search":
                return json.dumps({"success": False, "error": "provider unavailable"})
            return json.dumps({"success": True, "data": {"web": [] if failure == "empty" else [{"url": url}]}})
        return json.dumps({"results": [{"url": url, "error": "unavailable", "content": ""}]})

    code, result = _run(parser, gap, dispatch, capsys)
    assert code == 0 and result["status"] == "unresolved"
    assert len(calls) == (2 if failure == "extract" else 1)
    assert MissionStore.open_default().get(result["mission_id"]).status == "failed"
    assert registry.current() == [] and result["sources"] == []
