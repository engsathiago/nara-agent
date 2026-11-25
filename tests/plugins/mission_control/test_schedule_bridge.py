from __future__ import annotations

import json

import pytest

from plugins.mission_control.contracts import Mission
from plugins.mission_control.schedule_bridge import schedule_mission
from plugins.mission_control.store import MissionStore, MissionStoreError


def test_schedule_intent_precedes_canonical_cron_creation(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-1", objective="daily report", completion_criteria=["report delivered"],
    ))
    observed = {}

    def dispatch(name, args):
        observed["name"] = name
        observed["args"] = args
        observed["before"] = store.get("mission-1").schedules["daily"]["status"]
        return json.dumps({"success": True, "job": {"id": "cron-1"}})

    schedule_mission(
        store, dispatch, mission_id="mission-1", schedule_key="daily",
        schedule="0 9 * * *", timezone="America/Sao_Paulo",
    )

    assert observed["name"] == "cronjob_manage"
    assert observed["before"] == "requested"
    assert store.get("mission-1").schedules["daily"]["job_id"] == "cron-1"


def test_schedule_failure_keeps_retriable_intent(tmp_path):
    store = MissionStore(tmp_path / "missions.db")
    store.create(Mission(
        mission_id="mission-1", objective="daily report", completion_criteria=["report delivered"],
    ))

    with pytest.raises(MissionStoreError, match="cronjob_manage failed"):
        schedule_mission(
            store, lambda _name, _args: json.dumps({"success": False, "error": "offline"}),
            mission_id="mission-1", schedule_key="daily",
            schedule="0 9 * * *", timezone="America/Sao_Paulo",
        )

    assert store.get("mission-1").schedules["daily"]["status"] == "requested"
