"""Gateway consolidation creates one inactive candidate per verified mission."""

import argparse
import json
import shutil
import sqlite3
import time
from pathlib import Path

from extensions.nara_temporal_memory.nara_temporal import TemporalMemoryStore
from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.cli import mission_command, register_cli
from plugins.mission_control.consolidation import (
    MissionConsolidator,
    learning_status_tool,
    maybe_run_gateway_consolidation,
)
from plugins.mission_control.contracts import Mission, Receipt
from plugins.mission_control.learning import LearningLab
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore
from plugins.mission_control.verification import VerificationService


def _verified_profile(tmp_path, monkeypatch):
    import extensions.nara_temporal_memory.nara_temporal as provider_source

    home = tmp_path / "profile"
    (home / "plugins").mkdir(parents=True)
    shutil.copytree(Path(provider_source.__file__).parent, home / "plugins" / "nara_temporal")
    (home / "config.yaml").write_text("memory:\n  provider: nara_temporal\n", encoding="utf-8")
    monkeypatch.setenv("NARA_HOME", str(home))
    token = set_nara_home_override(home)
    missions = MissionStore.open_default()
    missions.create(Mission(
        mission_id="mission-1", objective="archive an invoice",
        completion_criteria=["archive matches original"],
    ))
    receipt = ReceiptStore(missions).prepare(Receipt(
        receipt_id="archive", mission_id="mission-1", task_id="task-1",
        intention="archive source invoice", agent_id="worker", tool="archive.write",
        target="archive.bin", idempotency_key="archive-1",
    ))
    artifacts = ArtifactStore(missions, missions.path.parent / "artifacts")
    artifact = artifacts.put_bytes("mission-1", b"invoice", producer_id="worker")
    ReceiptStore(missions).settle(
        "mission-1", receipt.receipt_id, "confirmed", artifact_ids=[artifact.artifact_id],
        idempotency_key="archive-settled",
    )
    VerificationService(missions, artifacts).verify_artifact(
        "mission-1", "archive matches original", artifact.artifact_id,
        verifier_id="verifier", executor_id="worker", verification_id="verified",
    )
    for state in ("planned", "running", "verifying", "completed"):
        missions.transition("mission-1", state)
    return home, token, missions


def test_learning_status_reports_unavailable_before_first_mission(tmp_path, monkeypatch):
    monkeypatch.setenv("NARA_HOME", str(tmp_path))
    token = set_nara_home_override(tmp_path)
    try:
        assert learning_status_tool()["state"] == "unavailable"
    finally:
        reset_nara_home_override(token)


def test_gateway_consolidates_once_and_cli_can_inspect_candidate(tmp_path, monkeypatch, capsys):
    home, token, missions = _verified_profile(tmp_path, monkeypatch)
    try:
        report = maybe_run_gateway_consolidation()
        assert report is not None and len(report["created"]) == 1
        identity = report["created"][0]["candidate_id"]
        memory = TemporalMemoryStore(home / "memories" / "nara-temporal.db")
        assert memory.get(f"procedure:{identity}")["status"] == "candidate"
        assert maybe_run_gateway_consolidation() is None
        assert learning_status_tool()["state"] == "available"
        assert learning_status_tool()["pending"] == 0
        (home / "config.yaml").write_text("memory:\n  provider: none\n", encoding="utf-8")
        assert learning_status_tool()["state"] == "degraded"
        (home / "config.yaml").write_text("memory:\n  provider: nara_temporal\n", encoding="utf-8")

        parser = argparse.ArgumentParser()
        register_cli(parser)
        assert mission_command(parser.parse_args(["learn-show", identity])) == 0
        assert json.loads(capsys.readouterr().out)["candidate_id"] == identity
        assert mission_command(parser.parse_args(["learn-consolidate"])) == 0
        manual = json.loads(capsys.readouterr().out)
        assert manual["unchanged"] == 1 and manual["created"] == []
        assert mission_command(parser.parse_args(["learn-status"])) == 0
        assert json.loads(capsys.readouterr().out)["processed"]["candidate"] == 1

        state = MissionConsolidator.open_default()
        stamp = time.time()
        assert state.run_due(now=stamp) is None
        assert state.run_due(now=stamp + 601)["unchanged"] == 1
        lab = LearningLab(
            missions, memory, missions.path.parent / "learning" / "candidates", home / "skills",
        )
        assert lab.extract("mission-1").candidate_id == identity
        with sqlite3.connect(home / "memories" / "nara-temporal.db") as conn:
            assert conn.execute("SELECT count(*) FROM memories WHERE status='candidate'").fetchone()[0] == 1
    finally:
        reset_nara_home_override(token)


def test_gateway_housekeeping_reaches_plugin_through_hook(tmp_path, monkeypatch):
    home, token, _missions = _verified_profile(tmp_path, monkeypatch)
    try:
        from gateway.run_learning import housekeeping_plugin_maintenance

        housekeeping_plugin_maintenance()
        report = MissionConsolidator.open_default().status()
        assert report["processed"]["candidate"] == 1
        assert report["pending"] == 0
        assert list((home / "plugin-data" / "mission-control" / "learning" / "candidates").glob("*.json"))
    finally:
        reset_nara_home_override(token)


def test_consolidation_retry_repairs_interrupted_memory_write(tmp_path, monkeypatch):
    home, token, missions = _verified_profile(tmp_path, monkeypatch)
    try:
        lab = LearningLab(
            missions,
            TemporalMemoryStore(home / "memories" / "nara-temporal.db"),
            missions.path.parent / "learning" / "candidates",
            home / "skills",
        )
        original_add = lab.memory.add
        calls = 0

        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("interrupted memory write")
            return original_add(*args, **kwargs)

        lab.memory.add = fail_once
        consolidation = MissionConsolidator(
            missions, lab, missions.path.parent / "learning" / "consolidation.db",
        )
        assert consolidation.run_once()["errors"]
        assert consolidation.status()["state"] == "degraded"
        assert consolidation.status()["pending"] == 1
        report = consolidation.run_once()
        assert len(report["created"]) == 1
        assert consolidation.status()["state"] == "available"
        assert lab.memory.get(f"procedure:{report['created'][0]['candidate_id']}")["status"] == "candidate"
    finally:
        reset_nara_home_override(token)
