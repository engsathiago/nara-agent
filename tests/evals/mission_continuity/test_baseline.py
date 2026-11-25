from __future__ import annotations

import json
import subprocess

import pytest

from evals.mission_continuity import baseline


def _completed(argv, **kwargs):
    return subprocess.CompletedProcess(argv, 0, stdout="Nara Agent v-test\n", stderr="")


def test_inventory_distinguishes_substrate_from_mission_layer():
    existing = {"nara_state", "nara_cli.kanban_db", "agent.verify.runner", "tools.file_operations"}
    capabilities = baseline.collect_inventory(
        find_spec=lambda name: object() if name in existing else None,
        which=lambda name: "/tmp/nara" if name == "nara" else None,
        run=_completed,
    )
    inventory = {item.capability_id: item for item in capabilities}

    assert inventory["runtime.command"].maturity == "verified"
    assert inventory["substrate.session_db"].availability == "available"
    assert inventory["substrate.kanban"].limitation is None
    assert inventory["mission.control"].availability == "unavailable"
    assert inventory["mission.control"].maturity == "discovered"


def test_inventory_does_not_report_retired_phase1_debt():
    limitations = "\n".join(
        item.limitation or ""
        for item in baseline.MODULE_PROBES
    ).lower()

    assert "not yet" not in limitations
    assert "remains phase 1 work" not in limitations


def test_scorecard_blocks_on_real_missing_requirements_and_writes_receipt(tmp_path):
    fixture = baseline.load_fixture()
    capabilities = [
        baseline.Capability(capability_id, "available", "wired", "fixture")
        for capability_id in fixture["required_capabilities"]
        if capability_id != "mission.event_log"
    ]
    scorecard = baseline.build_scorecard(fixture, capabilities, generated_at="2026-11-22T00:00:00+00:00")

    assert scorecard["status"] == "blocked"
    assert scorecard["blockers"] == [{"capability_id": "mission.event_log", "reason": "not inventoried"}]

    output = tmp_path / "receipts" / "baseline.json"
    baseline.write_scorecard(output, scorecard)
    assert json.loads(output.read_text()) == scorecard


def test_scorecard_is_ready_only_when_every_required_capability_is_wired():
    fixture = baseline.load_fixture()
    capabilities = [
        baseline.Capability(capability_id, "available", "wired", "verified by fixture")
        for capability_id in fixture["required_capabilities"]
    ]

    scorecard = baseline.build_scorecard(fixture, capabilities, generated_at="2026-11-22T00:00:00+00:00")

    assert scorecard["status"] == "ready"
    assert scorecard["blockers"] == []


def test_present_but_discovered_capability_remains_blocked():
    fixture = {"required_capabilities": ["mission.control"], "fixture_id": "fixture",
               "objective": "objective", "steps": [{}], "acceptance": ["criterion"]}
    capability = baseline.Capability("mission.control", "available", "discovered", "module resolves")

    scorecard = baseline.build_scorecard(fixture, [capability], generated_at="2026-11-22T00:00:00+00:00")

    assert scorecard["status"] == "blocked"
    assert scorecard["blockers"][0]["reason"] == "maturity is discovered; fixture requires wired or higher"


def test_fixture_rejects_duplicate_step_ids(tmp_path):
    fixture = json.loads(baseline.DEFAULT_FIXTURE.read_text())
    fixture["steps"][1]["id"] = fixture["steps"][0]["id"]
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        baseline.load_fixture(path)
