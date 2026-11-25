from __future__ import annotations

import pytest

from plugins.mission_control.capability_router import Capability, CapabilityRouter
from plugins.mission_control.contracts import Mission
from plugins.mission_control.store import MissionStore, MissionStoreError


CAPABILITIES = (
    Capability("api", "adapter.api", 10, ("structured",), "low", "low", True,
               "native", "query destination"),
    Capability("dom", "adapter.dom", 20, ("structured", "browser"), "medium", "medium", True,
               "destination", "DOM query"),
    Capability("vision", "adapter.vision", 30, ("browser",), "high", "high", True,
               "weak", "screenshot"),
)


def test_router_uses_lowest_rank_available_matching_route():
    available = {"adapter.dom", "adapter.vision"}
    router = CapabilityRouter(CAPABILITIES, find_spec=lambda module: object() if module in available else None)

    decision = router.select(["browser"])

    assert decision.capability_id == "dom"
    assert decision.alternatives == ("vision",)


def test_router_refuses_when_no_capability_proves_availability():
    router = CapabilityRouter(CAPABILITIES, find_spec=lambda module: None)

    with pytest.raises(MissionStoreError, match="no available capability"):
        router.select(["browser"])


def test_route_decision_is_a_confirmed_mission_receipt(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-1", objective="inspect page", completion_criteria=["page inspected"],
    ))
    router = CapabilityRouter(CAPABILITIES, find_spec=lambda module: object())

    decision = router.select_for_mission(
        store, "mission-1", "task-1", ["browser"], idempotency_key="route-1")

    receipt = next(iter(store.get("mission-1").receipts.values()))
    assert decision.capability_id == "dom"
    assert receipt["effect_status"] == "confirmed"
    assert receipt["observed_result"]["capability_id"] == "dom"
