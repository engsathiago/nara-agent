"""Public-plugin-API bridge between Mission Control and Nara's canonical Kanban queue."""

from __future__ import annotations

import json
from typing import Any, Callable

from plugins.mission_control.store import MissionNotFoundError, MissionStore, MissionStoreError


DispatchTool = Callable[[str, dict[str, Any]], str]


def create_mission_task(
    store: MissionStore,
    dispatch_tool: DispatchTool,
    *,
    mission_id: str,
    request_key: str,
    title: str,
    assignee: str,
    body: str | None = None,
    board: str | None = None,
    priority: int = 0,
    parents: list[str] | None = None,
    goal_mode: bool = True,
) -> dict[str, Any]:
    """Persist intent, idempotently create the canonical task, then link the observed result."""
    if store.get(mission_id) is None:
        raise MissionNotFoundError(mission_id)
    task_args = {
        "title": title,
        "assignee": assignee,
        "body": body,
        "board": board,
        "priority": priority,
        "parents": parents or [],
        "goal_mode": goal_mode,
        "idempotency_key": f"mission:{mission_id}:task:{request_key}",
    }
    task_args = {key: value for key, value in task_args.items() if value is not None}
    store.request_task(mission_id, request_key, task_args)

    raw = dispatch_tool("kanban_create", task_args)
    try:
        result = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MissionStoreError("kanban_create returned a non-JSON result") from exc
    if not isinstance(result, dict) or not result.get("ok") or not result.get("task_id"):
        message = result.get("error") if isinstance(result, dict) else None
        raise MissionStoreError(f"kanban_create failed: {message or raw}")
    store.link_task(
        mission_id, request_key, str(result["task_id"]), str(result.get("status") or "unknown"),
    )
    return result


def sync_task_status(
    *, task_id: str, status: str, run_id: int | None = None, store: MissionStore | None = None,
) -> None:
    active_store = store or MissionStore.open_default()
    suffix = str(run_id) if run_id is not None else "no-run"
    active_store.record_task_status(
        task_id, status, idempotency_key=f"kanban:{task_id}:{suffix}:{status}",
    )
