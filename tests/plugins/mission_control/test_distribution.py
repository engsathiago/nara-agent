from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import sqlite3

from nara_cli.backup import run_backup, run_import
from plugins.mission_control.contracts import Mission
from plugins.mission_control.store import MissionStore
from scripts.nara_product_manifest import build_manifest


def test_product_manifest_names_nara_and_hashes_required_components():
    repo = Path(__file__).resolve().parents[3]
    manifest = build_manifest(repo)
    paths = {item["path"] for item in manifest["files"]}

    assert manifest["product"] == "Nara"
    assert manifest["command"] == "nara"
    assert len(manifest["content_set_sha256"]) == 64
    assert "plugins/mission_control/plugin.yaml" in paths
    assert "extensions/nara_temporal_memory/nara_temporal/plugin.yaml" in paths


def test_full_backup_restore_preserves_running_mission_memory_skill_and_eval(tmp_path, monkeypatch):
    source = tmp_path / "source-home"
    source.mkdir()
    (source / "config.yaml").write_text("memory:\n  provider: nara_temporal\n", encoding="utf-8")
    mission_path = source / "plugin-data" / "mission-control" / "missions.db"
    store = MissionStore(mission_path)
    store.create(Mission(
        mission_id="mission-release", objective="survive release",
        completion_criteria=["state restored"]))
    store.transition("mission-release", "planned")
    store.transition("mission-release", "running")
    memory = source / "memories" / "nara-temporal.db"
    memory.parent.mkdir(parents=True)
    with sqlite3.connect(memory) as conn:
        conn.execute("CREATE TABLE memory_proof (value TEXT NOT NULL)")
        conn.execute("INSERT INTO memory_proof VALUES ('memory-proof')")
    skill = source / "skills" / "learned" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# learned proof\n", encoding="utf-8")
    evaluation = source / "plugin-data" / "mission-control" / "evaluations" / "holdout.json"
    evaluation.parent.mkdir(parents=True)
    evaluation.write_text('{"passed": true}\n', encoding="utf-8")
    archive = tmp_path / "nara-state.zip"

    monkeypatch.setenv("NARA_HOME", str(source))
    assert run_backup(Namespace(
        output=str(archive), quick=False, keep=0, label=None)) is True

    destination = tmp_path / "restored-home"
    destination.mkdir()
    monkeypatch.setenv("NARA_HOME", str(destination))
    monkeypatch.setattr("nara_cli.backup._revive_gateway_after_import", lambda _root: None)
    assert run_import(Namespace(zipfile=str(archive), force=True)) in {None, 0}

    restored = MissionStore(
        destination / "plugin-data" / "mission-control" / "missions.db").get("mission-release")
    assert restored.status.value == "running"
    with sqlite3.connect(destination / "memories" / "nara-temporal.db") as conn:
        assert conn.execute("SELECT value FROM memory_proof").fetchone()[0] == "memory-proof"
    assert (destination / "skills" / "learned" / "SKILL.md").read_text() == "# learned proof\n"
    assert (destination / evaluation.relative_to(source)).read_text() == '{"passed": true}\n'
