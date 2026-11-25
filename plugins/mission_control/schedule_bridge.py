"""Persist mission wake-up intent before creating a canonical Nara cron job."""

from __future__ import annotations

import json
from typing import Any, Callable

from plugins.mission_control.store import MissionNotFoundError, MissionStore, MissionStoreError


def schedule_mission(
    store: MissionStore,
    dispatch_tool: Callable[[str, dict[str, Any]], str],
    *,
    mission_id: str,
    schedule_key: str,
    schedule: str,
    timezone: str,
) -> dict[str, Any]:
    mission = store.get(mission_id)
    if mission is None:
        raise MissionNotFoundError(mission_id)
    spec = {
        "action": "create",
        "schedule": schedule,
        "timezone": timezone,
        "name": f"Nara mission {mission_id}",
        "prompt": (
            f"Resume durable mission {mission_id}. Read Mission Control first, reconcile unknown "
            "effects, execute only the next runnable task, and preserve the same mission ID."
        ),
        "continuity": True,
    }
    store.request_schedule(
        mission_id, schedule_key, spec, idempotency_key=f"schedule-request:{schedule_key}")
    raw = dispatch_tool("cronjob_manage", spec)
    try:
        result = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MissionStoreError("cronjob_manage returned a non-JSON result") from exc
    job = result.get("job") if isinstance(result, dict) else None
    job_id = (job or {}).get("id") if isinstance(job, dict) else None
    if not isinstance(result, dict) or not result.get("success") or not job_id:
        raise MissionStoreError(f"cronjob_manage failed: {result.get('error') if isinstance(result, dict) else raw}")
    store.link_schedule(mission_id, schedule_key, str(job_id), spec)
    return result
