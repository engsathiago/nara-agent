from __future__ import annotations

from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import Mission
from plugins.mission_control.dashboard import plugin_api
from plugins.mission_control.evolution import EvolutionLab
from plugins.mission_control.fleet import FleetCoordinator
from plugins.mission_control.policy import PolicyEngine
from plugins.mission_control.privacy import PrivacyControl
from plugins.mission_control.reverse_lab import ReverseEngineeringLab
from plugins.mission_control.store import MissionStore
from plugins.mission_control.trading_lab import TradingLab


def test_office_state_projects_canonical_stores_without_fake_workers(tmp_path, monkeypatch):
    missions = MissionStore(tmp_path / "missions.db")
    missions.create(Mission(
        mission_id="mission-office", objective="Show real state", completion_criteria=["visible"]))
    missions.request_task("mission-office", "request", {"title": "real task"})
    missions.link_task("mission-office", "request", "task-real", "todo")
    competence = CompetenceRegistry(tmp_path / "competence.db")
    competence.record_gap("office.ui", "Connect office", "no projection", impact=2)
    fleet = FleetCoordinator(tmp_path / "fleet", missions)
    evolution = EvolutionLab(tmp_path / "evolution")
    trading = TradingLab(tmp_path / "trading.db")
    reverse_lab = ReverseEngineeringLab(tmp_path / "reverse.db", plugin_root=tmp_path / "rea")
    policy = PolicyEngine(tmp_path / "policy.db")
    privacy = PrivacyControl(tmp_path / "privacy.db")
    monkeypatch.setattr(MissionStore, "open_default", classmethod(lambda cls: missions))
    monkeypatch.setattr(CompetenceRegistry, "open_default", classmethod(lambda cls: competence))
    monkeypatch.setattr(FleetCoordinator, "open_default", classmethod(lambda cls: fleet))
    monkeypatch.setattr(EvolutionLab, "open_default", classmethod(lambda cls: evolution))
    monkeypatch.setattr(TradingLab, "open_default", classmethod(lambda cls: trading))
    monkeypatch.setattr(
        ReverseEngineeringLab, "open_default", classmethod(lambda cls: reverse_lab))
    monkeypatch.setattr(PolicyEngine, "open_default", classmethod(lambda cls: policy))
    monkeypatch.setattr(PrivacyControl, "open_default", classmethod(lambda cls: privacy))

    state = plugin_api.office_state()

    assert state["authority"] == "mission_control"
    assert state["summary"]["missions"] == 1
    assert state["summary"]["workers"] == 0
    assert state["missions"][0]["tasks"] == [{"task_id": "task-real", "status": "todo"}]
    assert state["gaps"][0]["title"] == "Connect office"
    assert state["trading_lab"]["labs"] == []
    assert state["reverse_engineering_lab"]["investigations"] == []
    assert state["policy"]["active"]["mode"] == "observe_only"
    assert state["privacy"]["telemetry"] == "disabled"
