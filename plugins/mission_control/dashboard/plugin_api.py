"""Authenticated dashboard projection of Mission Control's canonical stores."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.evolution import EvolutionLab
from plugins.mission_control.fleet import FleetCoordinator
from plugins.mission_control.policy import PolicyEngine
from plugins.mission_control.privacy import PrivacyControl
from plugins.mission_control.reverse_lab import ReverseEngineeringLab
from plugins.mission_control.store import MissionStore
from plugins.mission_control.trading_lab import TradingLab


router = APIRouter()


def _mission_row(mission) -> dict[str, Any]:
    leases = list(mission.leases.values())
    return {
        "mission_id": mission.mission_id, "objective": mission.objective,
        "status": mission.status.value, "version": mission.version,
        "updated_at": mission.updated_at,
        "tasks": [{"task_id": task_id, "status": status} for task_id, status in mission.task_states.items()],
        "workers": [{
            "lease_id": item.get("lease_id"), "worker_id": item.get("worker_id"),
            "task_id": item.get("task_id"), "status": item.get("status"),
            "model": item.get("model"), "provider": item.get("provider"),
        } for item in leases],
        "receipt_counts": _counts(item.get("effect_status") for item in mission.receipts.values()),
        "artifact_count": len(mission.artifacts),
        "verification_counts": _counts(item.get("status") for item in mission.verifications.values()),
        "diagnostics": list(mission.diagnostics.values()),
    }


def _counts(values) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        result[key] = result.get(key, 0) + 1
    return result


def office_state() -> dict[str, Any]:
    missions = MissionStore.open_default()
    competence = CompetenceRegistry.open_default()
    try:
        fleet = FleetCoordinator.open_default().status()
    except Exception as exc:
        fleet = {"hosts": [], "assignments": [], "degraded": str(exc)}
    try:
        evolution = EvolutionLab.open_default().status()
    except Exception as exc:
        evolution = {"experiments": [], "deployments": [], "degraded": str(exc)}
    try:
        trading = TradingLab.open_default().status()
    except Exception as exc:
        trading = {"labs": [], "degraded": str(exc), "live_available": False}
    try:
        reverse_lab = ReverseEngineeringLab.open_default().status()
    except Exception as exc:
        reverse_lab = {"investigations": [], "degraded": str(exc)}
    try:
        policy = PolicyEngine.open_default().status()
    except Exception as exc:
        policy = {"active": None, "degraded": str(exc)}
    try:
        privacy = PrivacyControl.open_default().status()
    except Exception as exc:
        privacy = {"degraded": str(exc)}
    rows = [_mission_row(mission) for mission in missions.list()]
    return {
        "schema_version": 1, "authority": "mission_control",
        "missions": rows,
        "summary": {
            "missions": len(rows),
            "active": sum(row["status"] in {"planned", "running", "verifying"} for row in rows),
            "workers": sum(len(row["workers"]) for row in rows),
            "artifacts": sum(row["artifact_count"] for row in rows),
        },
        "competencies": competence.current(), "gaps": competence.gaps(),
        "fleet": fleet, "evolution": evolution,
        "trading_lab": trading, "reverse_engineering_lab": reverse_lab,
        "policy": policy,
        "privacy": privacy,
    }


@router.get("/state")
def get_state() -> dict[str, Any]:
    return office_state()


@router.get("/missions/{mission_id}")
def get_mission(mission_id: str) -> dict[str, Any]:
    store = MissionStore.open_default()
    mission = store.get(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="mission not found")
    return {
        "mission": mission.to_dict(),
        "events": [event.to_dict() for event in store.events(mission_id)],
    }
