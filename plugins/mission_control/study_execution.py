"""Join reserved study plans to the existing executable transfer evaluator."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import utc_now
from plugins.mission_control.learning import LearningLab
from plugins.mission_control.learning_runner import ProcessEvaluator, load_evaluation_cases
from plugins.mission_control.store import MissionStore


def register_study_cli(actions: Any) -> None:
    command = actions.add_parser(
        "study-evaluate", help="Execute a reserved study and record verified competence evidence")
    command.add_argument("plan_id")
    command.add_argument("candidate_id")
    command.add_argument("--cases-file", type=Path, required=True)
    command.add_argument("--evaluator", type=Path, required=True)
    command.add_argument("--system-file", type=Path, required=True)
    command.add_argument("--timeout", type=float, default=30.0)
    show = actions.add_parser("study-show", help="Inspect a study plan and its gap state")
    show.add_argument("plan_id")
    cycle = actions.add_parser("study-run", help="Run bounded source study, practice and reserved evaluation")
    cycle.add_argument("plan_id")
    cycle.add_argument("source_id")
    cycle.add_argument("--cases-file", type=Path, required=True)
    cycle.add_argument("--evaluator", type=Path, required=True)
    cycle.add_argument("--system-file", type=Path, required=True)
    cycle.add_argument("--max-attempts", type=int, default=3)
    cycle.add_argument("--max-seconds", type=float, default=600.0)
    cycle.add_argument("--timeout", type=float, default=30.0)


def _archive(lab: LearningLab, payload: dict[str, Any]) -> tuple[Path, str]:
    encoded = (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    path = lab.candidate_root.parent / "studies" / f"{digest}.json"
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("archived study receipt is missing or changed")
    else:
        lab._write_json(path, payload)
    return path, digest


def execute_study(
    registry: CompetenceRegistry, lab: LearningLab, plan_id: str, candidate_id: str,
    *, cases_file: Path, evaluator_path: Path, system: dict[str, Any], timeout: float = 30.0,
    evaluator: ProcessEvaluator | None = None,
) -> dict[str, Any]:
    """Evaluate both variants; never accept caller-supplied scores or activate a skill."""
    plan = registry.study_plan(plan_id)
    if not isinstance(system, dict) or not system:
        raise ValueError("study system must be a nonempty JSON object")
    cases = load_evaluation_cases(cases_file, set(plan.development_case_ids))
    reserved = set(plan.holdout_case_ids)
    expected = reserved | set(plan.development_case_ids)
    if {str(case["case_id"]) for case in cases} != expected:
        raise ValueError("study cases must match exactly the plan's development and reserved cases")
    # Run in the plan's order; development inputs never reach the evaluator.
    by_id = {str(case["case_id"]): case for case in cases}
    ordered = [by_id[case_id] for case_id in plan.holdout_case_ids]
    candidate = lab.load(candidate_id)
    evaluator = evaluator or ProcessEvaluator(evaluator_path, lab.candidate_root / "evidence", timeout=timeout)
    bound_system = {
        **system, "procedure_candidate_id": candidate_id,
        "procedure_candidate_sha256": hashlib.sha256(
            json.dumps(candidate.to_dict(), sort_keys=True).encode()).hexdigest(),
        "procedure_state": candidate.status, "evaluator_sha256": evaluator.sha256,
    }
    request = {
        "schema_version": 1, "kind": "study_evaluation_request", "plan": plan.to_dict(),
        "attempt_id": uuid.uuid4().hex, "started_at": utc_now(),
        "candidate": candidate.to_dict(), "system": bound_system, "cases": cases,
        "evaluator_sha256": evaluator.sha256, "evaluator_path": str(evaluator.archived_path),
        "timeout_per_variant_seconds": timeout,
    }
    request_path, request_hash = _archive(lab, request)
    registry.mark_study_execution(plan_id)
    try:
        report = lab.evaluate_transfer(
            candidate_id, ordered, evaluator, development_case_ids=set(plan.development_case_ids),
            evaluator_sha256=evaluator.sha256, evaluator_path=str(evaluator.archived_path),
            minimum_candidate_score=plan.minimum_candidate_score,
        )
        # The same byte checks used by promotion also apply to failed studies.
        verified = lab.verified_evaluation(candidate_id)
        if verified != report:
            raise ValueError("study evaluation was superseded before recording competence")
        receipt_path, receipt_hash = _archive(lab, {
            "schema_version": 1, "kind": "study_evaluation_result", "plan": plan.to_dict(),
            "request_path": str(request_path), "request_sha256": request_hash,
            "system": bound_system, "evaluation": report,
        })
        result = registry.evaluate_study(
            plan_id, baseline_scores={row["case_id"]: row["baseline"] for row in report["cases"]},
            candidate_scores={row["case_id"]: row["candidate"] for row in report["cases"]},
            system=bound_system, evidence_artifact_ids=[f"sha256:{receipt_hash}"],
            mission_id=registry.gap(plan.gap_id)["source_mission_id"],
        )
    except (ValueError, OSError, KeyError, sqlite3.DatabaseError) as exc:
        failure_path, _ = _archive(lab, {
            "schema_version": 1, "kind": "study_evaluation_failure",
            "plan_id": plan_id, "request_path": str(request_path), "request_sha256": request_hash,
            "error_type": type(exc).__name__, "failed_at": utc_now(),
        })
        registry.mark_study_execution(plan_id, failed=True)
        raise ValueError(f"study execution failed: {exc}; receipt: {failure_path}") from exc
    return {"plan_id": plan_id, "candidate_id": candidate_id,
            "evaluation": report, "competence": result,
            "receipt_path": str(receipt_path), "receipt_sha256": receipt_hash}


def competence_command(store: MissionStore, args: Any, *, llm: Any = None) -> dict[str, Any] | list[dict[str, Any]]:
    registry = CompetenceRegistry.open_default()
    handlers = {
        "competence": lambda: registry.current(args.category),
        "gap-list": lambda: registry.gaps(args.state),
        "gap-record": lambda: registry.record_gap(
            args.category, args.title, args.diagnosis, impact=args.impact, budget_usd=args.budget_usd,
            source_mission_id=args.mission_id, source_task_id=args.task_id,
            evidence_artifact_ids=args.evidence or ()),
        "study-plan": lambda: registry.create_study_plan(
            args.gap_id, args.objective, sources=args.source,
            development_case_ids=args.development_case, holdout_case_ids=args.holdout_case,
            minimum_candidate_score=args.minimum_candidate_score).to_dict(),
    }
    try:
        if args.mission_action in handlers:
            return handlers[args.mission_action]()
        if args.mission_action == "study-show":
            plan = registry.study_plan(args.plan_id)
            return {"plan": plan.to_dict(), "gap": registry.gap(plan.gap_id),
                    "cycle": registry.study_cycle(plan.plan_id)}
        from plugins.mission_control.learning_cli import open_learning_lab

        if args.mission_action == "study-run":
            from plugins.mission_control.study_cycle import run_study_cycle

            return run_study_cycle(registry, open_learning_lab(store), llm, args)
        return execute_study(
            registry, open_learning_lab(store), args.plan_id, args.candidate_id, cases_file=args.cases_file,
            evaluator_path=args.evaluator,
            system=json.loads(args.system_file.read_text(encoding="utf-8-sig")), timeout=args.timeout,
        )
    except (OSError, KeyError) as exc:
        raise ValueError(f"study input or evidence unavailable: {exc}") from exc
