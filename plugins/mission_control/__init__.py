"""Nara Mission Control plugin."""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import wraps
from typing import Any

from plugins.mission_control.contracts import (
    Artifact,
    Mission,
    MissionEvent,
    Receipt,
    Verification,
    WorkerLease,
)

__all__ = ["Artifact", "Mission", "MissionEvent", "Receipt", "Verification", "WorkerLease"]


def _tool_handler(function: Callable[..., Any]) -> Callable[..., str]:
    """Adapt Mission Control's keyword functions to the plugin tool ABI.

    The host dispatches one positional JSON object and requires a textual tool
    result.  Keeping this adapter at the registration boundary lets the domain
    functions retain their convenient keyword API for tests and internal use.
    """

    @wraps(function)
    def handle(args: dict[str, Any] | None = None, **context: Any) -> str:
        payload = dict(args or {})
        result = function(**payload, **context)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)

    return handle


def register(ctx) -> None:
    from plugins.mission_control.cli import mission_command, register_cli
    from plugins.mission_control.competence import (
        COMPETENCE_STATUS_SCHEMA,
        GAP_RECORD_SCHEMA,
        competence_status_tool,
        gap_record_tool,
    )
    from plugins.mission_control.consolidation import (
        LEARNING_STATUS_SCHEMA,
        learning_status_tool,
        maybe_run_gateway_consolidation,
    )
    from plugins.mission_control.effect_hooks import post_tool_call, pre_tool_call
    from plugins.mission_control.evolution import EVOLUTION_STATUS_SCHEMA, evolution_status_tool
    from plugins.mission_control.fleet import FLEET_STATUS_SCHEMA, fleet_status_tool
    from plugins.mission_control.kanban_bridge import sync_task_status
    from plugins.mission_control.ledger import record_llm_call
    from plugins.mission_control.learning_fabric_tool import register_learning_tools
    from plugins.mission_control.policy import (
        POLICY_CONFIRM_SCHEMA,
        POLICY_EXPLAIN_SCHEMA,
        POLICY_PROMOTE_SCHEMA,
        POLICY_ROLLBACK_SCHEMA,
        POLICY_STAGE_SCHEMA,
        POLICY_STATUS_SCHEMA,
        policy_confirm_tool,
        policy_explain_tool,
        policy_promote_tool,
        policy_rollback_tool,
        policy_stage_tool,
        policy_status_tool,
    )
    from plugins.mission_control.privacy import (
        PRIVACY_CONFIGURE_SCHEMA,
        PRIVACY_EXPORT_SCHEMA,
        PRIVACY_STATUS_SCHEMA,
        privacy_configure_tool,
        privacy_export_tool,
        privacy_status_tool,
    )
    from plugins.mission_control.reverse_lab import (
        REA_ROUTE_SCHEMA,
        REA_STATUS_SCHEMA,
        rea_route_tool,
        rea_status_tool,
    )
    from plugins.mission_control.specialists import (
        SPECIALIST_GET_SCHEMA,
        SPECIALIST_RESOLVE_SCHEMA,
        pre_llm_specialist_context,
        specialist_get_tool,
        specialist_resolve_tool,
    )
    from plugins.mission_control.trading_lab import (
        TRADING_BACKTEST_SCHEMA,
        TRADING_INIT_SCHEMA,
        TRADING_STATUS_SCHEMA,
        trading_backtest_tool,
        trading_init_tool,
        trading_status_tool,
    )
    from plugins.mission_control.workers import (
        claim_from_kanban,
        expire_from_kanban,
        release_from_kanban,
    )
    from plugins.mission_control.voice_bridge import (
        VOICE_PRESENCE_SCHEMA,
        on_voice_transcript,
        on_voice_wake,
        voice_presence_tool,
    )

    from plugins.mission_control.study_background import StudyBackground

    background_study = StudyBackground(ctx)

    def on_housekeeping(log=None):
        consolidation = maybe_run_gateway_consolidation(log)
        return {"consolidation": consolidation, "study": background_study.wake()}

    def handle_cli(args):
        llm = ctx.llm if args.mission_action in {"learn-media-study", "study-run", "study-resume", "study-work"} else None
        return mission_command(args, dispatch_tool=ctx.dispatch_tool, llm=llm)

    def on_completed(*, task_id, run_id=None, **kwargs):
        sync_task_status(task_id=task_id, status="done", run_id=run_id)

    def on_blocked(*, task_id, run_id=None, **kwargs):
        sync_task_status(task_id=task_id, status="blocked", run_id=run_id)

    ctx.register_auxiliary_task(
        "nara_source_selection", display_name="Nara source comparison",
        description="Compare archived sources with cited reasons before procedural study.",
        defaults={"timeout": 120},
    )
    ctx.register_auxiliary_task(
        "nara_media_study", display_name="Nara media study",
        description="Generate source-quoted inactive procedures from archived learning material.",
        defaults={"timeout": 120},
    )
    ctx.register_cli_command(
        name="mission",
        help="Create and inspect durable Nara missions",
        setup_fn=register_cli,
        handler_fn=handle_cli,
        description="Durable mission event log and reconstructed state.",
    )
    ctx.register_hook("kanban_task_completed", on_completed)
    ctx.register_hook("kanban_task_blocked", on_blocked)
    ctx.register_hook("on_gateway_housekeeping", on_housekeeping)
    ctx.register_hook("pre_tool_call", pre_tool_call)
    ctx.register_hook("post_tool_call", post_tool_call)
    ctx.register_hook("kanban_task_claimed", claim_from_kanban)
    ctx.register_hook("on_kanban_worker_exited", release_from_kanban)
    ctx.register_hook("on_kanban_worker_stale_claim", expire_from_kanban)
    ctx.register_hook("post_llm_call", record_llm_call)
    ctx.register_hook("voice_wake_detected", on_voice_wake)
    ctx.register_hook("voice_transcript", on_voice_transcript)
    ctx.register_hook("pre_llm_call", pre_llm_specialist_context)
    ctx.register_tool(
        name="nara_competence_status", toolset="mission_control",
        schema=COMPETENCE_STATUS_SCHEMA, handler=_tool_handler(competence_status_tool), emoji="📈")
    ctx.register_tool(
        name="nara_gap_record", toolset="mission_control",
        schema=GAP_RECORD_SCHEMA, handler=_tool_handler(gap_record_tool), emoji="🧩")
    ctx.register_tool(
        name="nara_evolution_status", toolset="mission_control",
        schema=EVOLUTION_STATUS_SCHEMA, handler=_tool_handler(evolution_status_tool), emoji="🧬")
    ctx.register_tool(
        name="nara_learning_status", toolset="mission_control",
        schema=LEARNING_STATUS_SCHEMA, handler=_tool_handler(learning_status_tool), emoji="📖")
    register_learning_tools(ctx, _tool_handler)
    ctx.register_tool(
        name="nara_specialist_resolve", toolset="mission_control",
        schema=SPECIALIST_RESOLVE_SCHEMA, handler=_tool_handler(specialist_resolve_tool), emoji="🧭")
    ctx.register_tool(
        name="nara_specialist_get", toolset="mission_control",
        schema=SPECIALIST_GET_SCHEMA, handler=_tool_handler(specialist_get_tool), emoji="🪖")
    ctx.register_tool(
        name="nara_fleet_status", toolset="mission_control",
        schema=FLEET_STATUS_SCHEMA, handler=_tool_handler(fleet_status_tool), emoji="🖥️")
    ctx.register_tool(
        name="nara_voice_presence", toolset="mission_control",
        schema=VOICE_PRESENCE_SCHEMA, handler=_tool_handler(voice_presence_tool), emoji="🎙️")
    ctx.register_tool(
        name="nara_trading_init", toolset="mission_control",
        schema=TRADING_INIT_SCHEMA, handler=_tool_handler(trading_init_tool), emoji="📊")
    ctx.register_tool(
        name="nara_trading_backtest", toolset="mission_control",
        schema=TRADING_BACKTEST_SCHEMA, handler=_tool_handler(trading_backtest_tool), emoji="🧪")
    ctx.register_tool(
        name="nara_trading_status", toolset="mission_control",
        schema=TRADING_STATUS_SCHEMA, handler=_tool_handler(trading_status_tool), emoji="📉")
    ctx.register_tool(
        name="nara_rea_route", toolset="mission_control",
        schema=REA_ROUTE_SCHEMA, handler=_tool_handler(rea_route_tool), emoji="🔬")
    ctx.register_tool(
        name="nara_rea_status", toolset="mission_control",
        schema=REA_STATUS_SCHEMA, handler=_tool_handler(rea_status_tool), emoji="🧾")
    ctx.register_tool(
        name="nara_policy_status", toolset="mission_control",
        schema=POLICY_STATUS_SCHEMA, handler=_tool_handler(policy_status_tool), emoji="📜")
    ctx.register_tool(
        name="nara_policy_explain", toolset="mission_control",
        schema=POLICY_EXPLAIN_SCHEMA, handler=_tool_handler(policy_explain_tool), emoji="🔎")
    ctx.register_tool(
        name="nara_policy_confirm", toolset="mission_control",
        schema=POLICY_CONFIRM_SCHEMA, handler=_tool_handler(policy_confirm_tool), emoji="✅")
    ctx.register_tool(
        name="nara_policy_stage", toolset="mission_control",
        schema=POLICY_STAGE_SCHEMA, handler=_tool_handler(policy_stage_tool), emoji="📝")
    ctx.register_tool(
        name="nara_policy_promote", toolset="mission_control",
        schema=POLICY_PROMOTE_SCHEMA, handler=_tool_handler(policy_promote_tool), emoji="🚦")
    ctx.register_tool(
        name="nara_policy_rollback", toolset="mission_control",
        schema=POLICY_ROLLBACK_SCHEMA, handler=_tool_handler(policy_rollback_tool), emoji="↩️")
    ctx.register_tool(
        name="nara_privacy_status", toolset="mission_control",
        schema=PRIVACY_STATUS_SCHEMA, handler=_tool_handler(privacy_status_tool), emoji="🔐")
    ctx.register_tool(
        name="nara_privacy_configure", toolset="mission_control",
        schema=PRIVACY_CONFIGURE_SCHEMA, handler=_tool_handler(privacy_configure_tool), emoji="⚙️")
    ctx.register_tool(
        name="nara_privacy_export", toolset="mission_control",
        schema=PRIVACY_EXPORT_SCHEMA, handler=_tool_handler(privacy_export_tool), emoji="📦")

