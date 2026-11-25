"""Runtime hooks that bind real tool calls to mission effect receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import EffectStatus, Receipt
from plugins.mission_control.ledger import ExperienceLedger
from plugins.mission_control.policy import PolicyEngine
from plugins.mission_control.privacy import redact_sensitive
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.store import MissionStore, MissionStoreError


LARGE_RESULT_BYTES = 16 * 1024


def _receipt_id(mission_id: str, task_id: str, tool_call_id: str) -> str:
    digest = hashlib.sha256(f"{mission_id}\0{task_id}\0{tool_call_id}".encode()).hexdigest()
    return f"tool:{digest}"


def _target(args: dict[str, Any]) -> str:
    for key in ("path", "file_path", "url", "target", "command", "cmd", "query"):
        value = args.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(redact_sensitive(value, key=key)).strip()[:1000]
    safe_args = redact_sensitive(args)
    return json.dumps(safe_args, sort_keys=True, ensure_ascii=False, default=str)[:1000] or "(no target)"


def _result_bytes(result: Any) -> bytes:
    if isinstance(result, bytes):
        return result
    if isinstance(result, str):
        return result.encode("utf-8", errors="replace")
    return json.dumps(result, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


def pre_tool_call(
    tool_name: str = "",
    args: dict[str, Any] | None = None,
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
    **_: Any,
) -> dict[str, str] | None:
    """Persist intent before a real tool call belonging to a linked mission task."""
    if tool_name and isinstance(args, dict):
        policy_result = PolicyEngine.open_default().guard_tool(
            tool_name, args, surface="runtime", actor_id=session_id or "runtime-agent")
        if policy_result:
            return policy_result
    if not (tool_name and task_id and tool_call_id and isinstance(args, dict)):
        return
    missions = MissionStore.open_default()
    mission = missions.mission_for_task(task_id)
    if mission is None:
        return
    ReceiptStore(missions).prepare(Receipt(
        receipt_id=_receipt_id(mission.mission_id, task_id, tool_call_id),
        mission_id=mission.mission_id,
        task_id=task_id,
        intention=f"execute tool {tool_name}",
        agent_id=session_id or "runtime-agent",
        tool=tool_name,
        target=_target(args),
        idempotency_key=f"tool-call:{tool_call_id}",
        adapter_version="runtime-hook-v1",
    ))
    ExperienceLedger.open_default().record(
        event_id=f"tool-start:{mission.mission_id}:{tool_call_id}",
        kind="tool.started",
        mission_id=mission.mission_id,
        task_id=task_id,
        session_id=session_id or None,
        agent_id=session_id or "runtime-agent",
        status="pending",
        tool=tool_name,
        payload={"argument_keys": sorted(args), "target": _target(args)},
    )


def post_tool_call(
    tool_name: str = "",
    result: Any = None,
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
    status: str = "",
    error_type: str | None = None,
    error_message: str | None = None,
    duration_ms: int = 0,
    **_: Any,
) -> None:
    """Settle a prepared runtime receipt and offload large results by hash."""
    if not (task_id and tool_call_id):
        return
    missions = MissionStore.open_default()
    mission = missions.mission_for_task(task_id)
    if mission is None:
        return
    receipt_id = _receipt_id(mission.mission_id, task_id, tool_call_id)
    receipts = ReceiptStore(missions)
    if receipts.get(mission.mission_id, receipt_id) is None:
        return
    content = _result_bytes(result)
    artifact_ids: list[str] = []
    observed_result: dict[str, Any] = {
        "status": status or "unknown",
        "duration_ms": duration_ms,
        "result_sha256": hashlib.sha256(content).hexdigest(),
        "result_size_bytes": len(content),
    }
    if len(content) >= LARGE_RESULT_BYTES:
        artifact = ArtifactStore(
            missions, Path(missions.path).parent / "artifacts",
        ).put_bytes(
            mission.mission_id,
            content,
            producer_id=session_id or "runtime-agent",
            media_type="application/json" if not isinstance(result, (str, bytes)) else "text/plain",
            metadata={"tool": tool_name, "tool_call_id": tool_call_id, "kind": "tool-result"},
        )
        artifact_ids.append(artifact.artifact_id)
        observed_result["result_offloaded"] = True
    normalized = status.lower()
    if normalized == "ok":
        effect_status = EffectStatus.CONFIRMED
    elif normalized == "cancelled" or "timeout" in (error_type or "").lower():
        effect_status = EffectStatus.UNKNOWN
    else:
        effect_status = EffectStatus.FAILED
    try:
        receipts.settle(
            mission.mission_id,
            receipt_id,
            effect_status,
            observed_result=observed_result,
            artifact_ids=artifact_ids,
            error=error_message,
            idempotency_key=f"tool-settle:{tool_call_id}:{effect_status.value}",
        )
    except MissionStoreError:
        # Duplicate terminal observer delivery is harmless; incompatible state
        # remains visible in the durable receipt and must not be overwritten.
        current = receipts.get(mission.mission_id, receipt_id)
        if current is None or current.effect_status is not effect_status:
            raise
    ExperienceLedger.open_default().record(
        event_id=f"tool-end:{mission.mission_id}:{tool_call_id}",
        kind="tool.completed",
        mission_id=mission.mission_id,
        task_id=task_id,
        session_id=session_id or None,
        agent_id=session_id or "runtime-agent",
        status="ok" if effect_status is EffectStatus.CONFIRMED else effect_status.value,
        tool=tool_name,
        duration_ms=duration_ms,
        payload={
            "error_type": error_type,
            "result_sha256": observed_result["result_sha256"],
            "result_size_bytes": observed_result["result_size_bytes"],
            "artifact_ids": artifact_ids,
        },
    )
    if effect_status is not EffectStatus.CONFIRMED:
        CompetenceRegistry(Path(missions.path).parent / "competence.db").record_gap(
            f"tool.{tool_name or 'unknown'}",
            f"Recover failed {tool_name or 'tool'} execution",
            (
                f"effect_status={effect_status.value}; error_type={error_type or 'unknown'}; "
                f"result_sha256={observed_result['result_sha256']}"
            ),
            impact=4 if effect_status is EffectStatus.UNKNOWN else 3,
            source_mission_id=mission.mission_id,
            source_task_id=task_id,
            evidence_artifact_ids=artifact_ids,
        )
