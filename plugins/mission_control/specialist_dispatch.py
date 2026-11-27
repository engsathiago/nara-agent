"""Supply selected specialist instructions through the native pre-tool hook."""

from __future__ import annotations

import copy
import logging
import sqlite3
from typing import Any

from nara_cli.config import load_config_readonly
from plugins.mission_control import effect_hooks
from plugins.mission_control.specialist_bindings import digest, freeze_call
from plugins.mission_control.specialists import SpecialistResolver


logger = logging.getLogger(__name__)


def _tasks(args: dict) -> list[dict]:
    if args.get("action"):
        return []
    tasks = args.get("tasks")
    if tasks is None:
        tasks = [args]
    if not isinstance(tasks, list) or not tasks:
        return []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("goal"), str) or not task["goal"].strip():
            return []
        if task.get("context") is not None and not isinstance(task["context"], str):
            return []
    return tasks


def _enabled() -> bool:
    config = load_config_readonly() or {}
    entries = (config.get("plugins") or {}).get("entries") or {}
    settings = entries.get("mission_control") or {}
    return (settings.get("settings") or {}).get("specialist_delegation", True) is not False


def _bind_task(task: dict, resolver: SpecialistResolver) -> dict | None:
    decision = resolver.resolve(task["goal"], category=task.get("task_category"))
    selected = decision["selected"]
    if selected is None:
        return None
    loaded = resolver.load_selected(selected["source"], selected["specialist_id"])
    instructions = loaded["instructions"]
    if not isinstance(instructions, str) or not instructions.strip():
        raise ValueError("selected specialist has empty instructions")
    prompt_hash = digest(instructions)
    if prompt_hash != selected["prompt_hash"] or prompt_hash != loaded["prompt_hash"]:
        raise ValueError("selected specialist prompt hash changed during preparation")
    label = f"{selected['source']}:{selected['specialist_id']}"
    origin = f"Skill file: {loaded['path']}\n" if selected["source"] == "skill" else ""
    section = (f"[Nara specialist {label}; sha256={prompt_hash}; decision={decision['decision_id']}]\n"
               f"{origin}{instructions}\n[End Nara specialist instructions]")
    task["context"] = "\n\n".join(part for part in (task.get("context"), section) if part)
    return {"selected": selected, "decision_id": decision["decision_id"],
            "instructions": instructions, "model_recommendation": decision["model"]}


def _prepare(args: dict) -> dict:
    prepared = copy.deepcopy(args)
    resolver = SpecialistResolver.open_default()
    bindings = [_bind_task(task, resolver) for task in _tasks(prepared)]
    return {"args": prepared, "specialists": bindings}


def pre_tool_call(tool_name: str = "", args: dict[str, Any] | None = None,
                  session_id: str = "", tool_call_id: str = "", **kwargs: Any) -> dict | None:
    """Compose before effect preparation so receipts describe the actual dispatch."""
    prepared = args
    if tool_name == "delegate_task" and isinstance(args, dict) and _tasks(args):
        try:
            if _enabled():
                prepared = freeze_call(args, session_id, tool_call_id, lambda: _prepare(args))["args"]
        except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as exc:
            logger.exception("Specialist delegation preparation failed")
            return {"action": "error", "message": f"Specialist delegation preparation failed: {exc}"}
    directive = effect_hooks.pre_tool_call(tool_name=tool_name, args=prepared, session_id=session_id,
                                          tool_call_id=tool_call_id, **kwargs)
    if directive is not None:
        return directive
    if prepared != args:
        return {"action": "modify", "args": prepared}
    return None
