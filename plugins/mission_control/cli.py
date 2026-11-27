"""Operator CLI for the durable Mission Control store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid
from typing import Any, Callable

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.capability_router import CapabilityRouter
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import (
    ContractError,
    EffectStatus,
    Mission,
    MissionStatus,
    Receipt,
    VerificationStatus,
)
from plugins.mission_control.kanban_bridge import create_mission_task
from plugins.mission_control.ledger import ExperienceLedger
from plugins.mission_control.learning_cli import dispatch_learning, register_learning_cli
from plugins.mission_control.learning_fabric_cli import register_media_cli
from plugins.mission_control.goal_bridge import bind_mission_goal
from plugins.mission_control.receipts import ReceiptStore
from plugins.mission_control.schedule_bridge import schedule_mission
from plugins.mission_control.store import MissionNotFoundError, MissionStore, MissionStoreError
from plugins.mission_control.supervisor import MissionSupervisor
from plugins.mission_control.study_execution import register_study_cli, competence_command
from plugins.mission_control.verification import VerificationService


def register_cli(parser: argparse.ArgumentParser) -> None:
    actions = parser.add_subparsers(dest="mission_action")

    create = actions.add_parser("create", help="Create a durable draft mission")
    create.add_argument("objective")
    create.add_argument("--criterion", action="append", required=True, dest="criteria")
    create.add_argument("--mission-id")
    create.add_argument("--session-id")
    create.add_argument("--idempotency-key")

    listing = actions.add_parser("list", help="List durable missions")
    listing.add_argument("--status", choices=[status.value for status in MissionStatus])

    show = actions.add_parser("show", help="Show a mission and optionally its immutable events")
    show.add_argument("mission_id")
    show.add_argument("--events", action="store_true")

    transition = actions.add_parser("transition", help="Apply a validated mission status transition")
    transition.add_argument("mission_id")
    transition.add_argument("status", choices=[status.value for status in MissionStatus])
    transition.add_argument("--reason")
    transition.add_argument("--actor", default="user")
    transition.add_argument("--idempotency-key")

    task_add = actions.add_parser("task-add", help="Create and link a task in the canonical Kanban queue")
    task_add.add_argument("mission_id")
    task_add.add_argument("title")
    task_add.add_argument("--assignee", required=True)
    task_add.add_argument("--request-key", required=True)
    task_add.add_argument("--body")
    task_add.add_argument("--board")
    task_add.add_argument("--priority", type=int, default=0)
    task_add.add_argument("--parent", action="append", dest="parents")
    task_add.add_argument("--single-turn", action="store_true")

    receipt_prepare = actions.add_parser(
        "receipt-prepare", help="Persist an external-effect intent before executing it")
    receipt_prepare.add_argument("mission_id")
    receipt_prepare.add_argument("task_id")
    receipt_prepare.add_argument("intention")
    receipt_prepare.add_argument("--agent", required=True)
    receipt_prepare.add_argument("--tool", required=True)
    receipt_prepare.add_argument("--target", required=True)
    receipt_prepare.add_argument("--idempotency-key", required=True)
    receipt_prepare.add_argument("--receipt-id")
    receipt_prepare.add_argument("--adapter-version")

    receipt_settle = actions.add_parser(
        "receipt-settle", help="Confirm, fail, or mark an external effect unknown")
    receipt_settle.add_argument("mission_id")
    receipt_settle.add_argument("receipt_id")
    receipt_settle.add_argument("status", choices=[status.value for status in EffectStatus if status is not EffectStatus.PENDING])
    receipt_settle.add_argument("--idempotency-key", required=True)
    receipt_settle.add_argument("--observed-result", type=_json_object, default={})
    receipt_settle.add_argument("--artifact", action="append", dest="artifacts")
    receipt_settle.add_argument("--error")
    receipt_settle.add_argument("--verification-method")
    receipt_settle.add_argument(
        "--verification-status", choices=[status.value for status in VerificationStatus])
    receipt_settle.add_argument("--destination-operation-id")

    artifact_add = actions.add_parser(
        "artifact-add", help="Store a content-addressed file and link it to a mission")
    artifact_add.add_argument("mission_id")
    artifact_add.add_argument("path", type=Path)
    artifact_add.add_argument("--producer", required=True)
    artifact_add.add_argument("--media-type", default="application/octet-stream")
    artifact_add.add_argument("--metadata", type=_json_object, default={})

    artifact_show = actions.add_parser(
        "artifact-show", help="Show and optionally verify a mission artifact")
    artifact_show.add_argument("mission_id")
    artifact_show.add_argument("artifact_id")
    artifact_show.add_argument("--verify", action="store_true")

    verify_artifact = actions.add_parser(
        "verify-artifact", help="Independently verify an artifact against a mission criterion")
    verify_artifact.add_argument("mission_id")
    verify_artifact.add_argument("criterion")
    verify_artifact.add_argument("artifact_id")
    verify_artifact.add_argument("--verifier", required=True)
    verify_artifact.add_argument("--executor", required=True)
    verify_artifact.add_argument("--method", default="sha256")
    verify_artifact.add_argument("--verification-id")

    start = actions.add_parser(
        "start", help="Bind the existing session goal and start a planned mission")
    start.add_argument("mission_id")
    start.add_argument("--session-id", required=True)

    capabilities = actions.add_parser(
        "capabilities", help="Inspect real execution routes in reliability order")
    capabilities.add_argument("--require", action="append", dest="required")

    route = actions.add_parser(
        "route", help="Select and receipt the least-fragile route for a mission task")
    route.add_argument("mission_id")
    route.add_argument("task_id")
    route.add_argument("--require", action="append", required=True, dest="required")
    route.add_argument("--idempotency-key", required=True)

    supervise = actions.add_parser(
        "supervise", help="Diagnose stalled tasks and uncertain effects without guessing success")
    supervise.add_argument("mission_id")
    supervise.add_argument("--stale-seconds", type=int, default=900)

    schedule = actions.add_parser(
        "schedule", help="Persist a wake-up intent and create a canonical cron job")
    schedule.add_argument("mission_id")
    schedule.add_argument("schedule")
    schedule.add_argument("--timezone", required=True)
    schedule.add_argument("--schedule-key", required=True)

    ledger = actions.add_parser(
        "ledger", help="Show the mission-task-agent-turn-tool-artifact evidence tree")
    ledger.add_argument("mission_id")

    competence = actions.add_parser(
        "competence", help="Show observed competence separately from model capabilities")
    competence.add_argument("--category")

    gap_list = actions.add_parser("gap-list", help="Show the prioritized competence-gap queue")
    gap_list.add_argument("--state")

    gap_record = actions.add_parser("gap-record", help="Record a real failure as a study gap")
    gap_record.add_argument("category")
    gap_record.add_argument("title")
    gap_record.add_argument("diagnosis")
    gap_record.add_argument("--impact", type=int, required=True)
    gap_record.add_argument("--budget-usd", type=float)
    gap_record.add_argument("--mission-id")
    gap_record.add_argument("--task-id")
    gap_record.add_argument("--evidence", action="append")

    study_plan = actions.add_parser(
        "study-plan", help="Reserve development and holdout cases before studying")
    study_plan.add_argument("gap_id")
    study_plan.add_argument("objective")
    study_plan.add_argument("--source", action="append", type=_json_object, required=True)
    study_plan.add_argument("--development-case", action="append", required=True)
    study_plan.add_argument("--holdout-case", action="append", required=True)
    study_plan.add_argument("--minimum-candidate-score", type=float, default=0.8)

    register_study_cli(actions)
    register_learning_cli(actions)
    register_media_cli(actions)

    rebuild = actions.add_parser("rebuild", help="Rebuild and verify a projection from its event log")
    rebuild.add_argument("mission_id")
    parser.set_defaults(func=mission_command)


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))


def _json_object(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError("value must be a JSON object")
    return payload


def mission_command(
    args: argparse.Namespace,
    *,
    dispatch_tool: Callable[[str, dict[str, Any]], str] | None = None,
    llm: Any = None,
) -> int:
    action = getattr(args, "mission_action", None)
    if not action:
        print("Usage: nara mission {create|list|show|transition|task-add|rebuild}")
        return 2
    store = MissionStore.open_default()
    try:
        if action == "create":
            mission = Mission(
                mission_id=args.mission_id or uuid.uuid4().hex,
                objective=args.objective,
                completion_criteria=args.criteria,
                session_id=args.session_id,
            )
            _print(store.create(mission, idempotency_key=args.idempotency_key).to_dict())
        elif action == "list":
            _print([mission.to_dict() for mission in store.list(status=args.status)])
        elif action == "show":
            mission = store.get(args.mission_id)
            if mission is None:
                raise MissionNotFoundError(args.mission_id)
            payload = mission.to_dict()
            if args.events:
                payload["events"] = [event.to_dict() for event in store.events(args.mission_id)]
            _print(payload)
        elif action == "transition":
            mission = store.transition(
                args.mission_id, args.status, actor_id=args.actor, reason=args.reason,
                idempotency_key=args.idempotency_key,
            )
            _print(mission.to_dict())
        elif action == "task-add":
            if dispatch_tool is None:
                raise MissionStoreError("Kanban dispatch is unavailable on this surface")
            result = create_mission_task(
                store, dispatch_tool, mission_id=args.mission_id, request_key=args.request_key,
                title=args.title, assignee=args.assignee, body=args.body, board=args.board,
                priority=args.priority, parents=args.parents, goal_mode=not args.single_turn,
            )
            _print(result)
        elif action == "receipt-prepare":
            receipt = Receipt(
                receipt_id=args.receipt_id or uuid.uuid4().hex,
                mission_id=args.mission_id,
                task_id=args.task_id,
                intention=args.intention,
                agent_id=args.agent,
                tool=args.tool,
                target=args.target,
                idempotency_key=args.idempotency_key,
                adapter_version=args.adapter_version,
            )
            _print(ReceiptStore(store).prepare(receipt).to_dict())
        elif action == "receipt-settle":
            receipt = ReceiptStore(store).settle(
                args.mission_id,
                args.receipt_id,
                args.status,
                observed_result=args.observed_result,
                artifact_ids=args.artifacts,
                error=args.error,
                verification_method=args.verification_method,
                verification_status=args.verification_status,
                destination_operation_id=args.destination_operation_id,
                idempotency_key=args.idempotency_key,
            )
            _print(receipt.to_dict())
        elif action == "artifact-add":
            artifact = ArtifactStore(store, store.path.parent / "artifacts").put_file(
                args.mission_id,
                args.path,
                producer_id=args.producer,
                media_type=args.media_type,
                metadata=args.metadata,
            )
            _print(artifact.to_dict())
        elif action == "artifact-show":
            artifacts = ArtifactStore(store, store.path.parent / "artifacts")
            artifact = artifacts.get(args.mission_id, args.artifact_id)
            if artifact is None:
                raise MissionStoreError(f"unknown artifact: {args.artifact_id}")
            payload = artifact.to_dict()
            if args.verify:
                payload["content_verified"] = artifacts.verify(args.mission_id, args.artifact_id)
            _print(payload)
        elif action == "verify-artifact":
            artifacts = ArtifactStore(store, store.path.parent / "artifacts")
            verification = VerificationService(store, artifacts).verify_artifact(
                args.mission_id,
                args.criterion,
                args.artifact_id,
                verifier_id=args.verifier,
                executor_id=args.executor,
                method=args.method,
                verification_id=args.verification_id,
            )
            _print(verification.to_dict())
        elif action == "start":
            goal = bind_mission_goal(store, args.mission_id, args.session_id)
            mission = store.get(args.mission_id)
            if mission is None:
                raise MissionNotFoundError(args.mission_id)
            if mission.status is MissionStatus.DRAFT:
                mission = store.transition(
                    args.mission_id, MissionStatus.PLANNED,
                    actor_id="mission-leader", idempotency_key="leader:planned")
            if mission.status is MissionStatus.PLANNED:
                mission = store.transition(
                    args.mission_id, MissionStatus.RUNNING,
                    actor_id="mission-leader", idempotency_key="leader:running")
            _print({"mission": mission.to_dict(), "goal": json.loads(goal.to_json())})
        elif action == "capabilities":
            router = CapabilityRouter()
            payload: dict[str, Any] = {"capabilities": router.inventory()}
            if args.required:
                payload["decision"] = router.select(args.required).to_dict()
            _print(payload)
        elif action == "route":
            decision = CapabilityRouter().select_for_mission(
                store, args.mission_id, args.task_id, args.required,
                idempotency_key=args.idempotency_key,
            )
            _print(decision.to_dict())
        elif action == "supervise":
            _print(MissionSupervisor(store, CompetenceRegistry.open_default()).diagnose(
                args.mission_id, stale_after_seconds=args.stale_seconds))
        elif action == "schedule":
            if dispatch_tool is None:
                raise MissionStoreError("cron dispatch is unavailable on this surface")
            _print(schedule_mission(
                store,
                dispatch_tool,
                mission_id=args.mission_id,
                schedule_key=args.schedule_key,
                schedule=args.schedule,
                timezone=args.timezone,
            ))
        elif action == "ledger":
            _print(ExperienceLedger.open_default().mission_tree(store, args.mission_id))
        elif action in {"competence", "gap-list", "gap-record", "study-plan", "study-evaluate", "study-show", "study-run", "study-resume"}:
            _print(competence_command(store, args, llm=llm))
        elif action.startswith("learn-"):
            _print(dispatch_learning(store, args, llm=llm))
        elif action == "rebuild":
            mission = store.rebuild_projection(args.mission_id)
            _print({"mission": mission.to_dict(), "projection_verified": store.verify_projection(args.mission_id)})
        return 0
    except (ContractError, MissionStoreError, ValueError) as exc:
        _print({"error": type(exc).__name__, "message": str(exc)})
        return 1

