"""Restore bounded study work without renewing its budget or reusing holdouts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from plugins.mission_control.learning_github_source import _check_cited_source
from plugins.mission_control.study_checkpoint import initial_result, read_checkpoint, verify_evaluator_result
from plugins.mission_control.study_cycle import StudyBudgetStop, StudyCycle, StudyEvaluator
from plugins.mission_control.study_source_context import validate_source_context


def _verify_contract(registry, lab, plan_id, request):
    plan = registry.study_plan(plan_id)
    current = json.loads(json.dumps(plan.to_dict()))
    if {key: value for key, value in current.items() if key != "status"} != {
        key: value for key, value in request["plan"].items() if key != "status"
    }:
        raise ValueError("study plan changed since the cycle was frozen")
    source = lab.source_fabric.source(request["source_id"])
    _check_cited_source(source)
    if source["source_hash"] != request["source_hash"]:
        raise ValueError("study source changed since the cycle was frozen")
    descriptor = request["evaluator"]
    if hashlib.sha256(Path(descriptor["path"]).read_bytes()).hexdigest() != descriptor["sha256"]:
        raise ValueError("archived study evaluator is missing or changed")
    return plan


def _verify_attempts(lab, result):
    for attempt in result["attempts"]:
        generation = read_checkpoint(attempt["generation_evidence"])
        candidate_id = attempt["candidate_id"]
        if candidate_id:
            candidate = json.loads(json.dumps(lab.load(candidate_id).to_dict()))
            if candidate != generation["candidate"]:
                raise ValueError("study candidate changed since generation")
        for row in attempt["practice"]:
            verify_evaluator_result(row)
    for entry in result["evaluator_usage"]:
        verify_evaluator_result(entry["result"])
    if result["holdout_started"] and result["frozen_candidate_id"] not in {
        attempt["candidate_id"] for attempt in result["attempts"]
    }:
        raise ValueError("frozen holdout candidate is missing")


def _restore(registry, lab, llm, row, request):
    cycle = StudyCycle.__new__(StudyCycle)
    cycle.registry, cycle.lab, cycle.llm = registry, lab, llm
    cycle.plan = _verify_contract(registry, lab, row["plan_id"], request)
    cycle.source_id, cycle.system = request["source_id"], request["system"]
    cycle.teaching_material = request.get("teaching_material")
    cycle.source_context = validate_source_context(request.get("source_context"))
    cycle.max_attempts, cycle.budget_usd = request["max_generation_calls"], request["budget_usd"]
    cycle.deadline = time.monotonic() + request["deadline_at"] - time.time()
    cycle.request_path, cycle.request_hash = Path(row["request"]["path"]), row["request"]["sha256"]
    cycle.cycle_id = row["cycle_id"]
    cycle.result = row["result"] or initial_result(
        cycle.cycle_id, cycle.plan.plan_id, cycle.source_id, cycle.request_path, cycle.request_hash)
    _verify_attempts(lab, cycle.result)
    by_id = {str(case["case_id"]): case for case in request["cases"]}
    cycle.development = [by_id[case_id] for case_id in cycle.plan.development_case_ids]
    cycle.evaluator = StudyEvaluator(
        request["evaluator"]["path"], lab.candidate_root / "evidence",
        python_script=request["evaluator"]["python_script"],
        timeout=request["timeout_per_variant_seconds"], deadline=cycle.deadline,
        max_calls=request["max_evaluator_calls"])
    cycle.evaluator.calls = cycle.result["evaluator_calls_started"]
    cycle.evaluator.on_start = cycle._before_evaluation
    cycle.evaluator.on_result = cycle._observe_evaluation
    cycle.evaluator.replay = {
        (entry["candidate_id"], entry["case_id"]): entry["result"]
        for entry in cycle.result["evaluator_usage"] if entry["phase"] == "holdout"
    }
    return cycle


def _reconcile_pending(cycle):
    pending = cycle.result["pending_call"]
    if not pending:
        return True
    if pending["kind"] == "generation":
        # The response may have been produced remotely. Its reserved call is
        # consumed even though no proposal/price was committed here.
        cycle.result["cost_unknown"] = True
        cycle.result.setdefault("interrupted_calls", []).append(pending)
    elif pending.get("observed_result") and pending.get("accounted"):
        observed = verify_evaluator_result(pending["observed_result"])
        if pending["phase"] == "development":
            attempt = cycle.result["attempts"][-1]
            if attempt["candidate_id"] != pending["candidate_id"]:
                raise ValueError("pending practice candidate does not match the checkpoint")
            case = next(case for case in cycle.development if str(case["case_id"]) == pending["case_id"])
            if not any(row["case_id"] == pending["case_id"] for row in attempt["practice"]):
                attempt["practice"].append({"case_id": pending["case_id"], "case": case, **observed})
    else:
        cycle.result["reason"] = "evaluator outcome is unknown; reconcile effects before starting another study"
        return False
    cycle.result["pending_call"] = None
    return True


def resume_study_cycle(registry, lab, llm, plan_id):
    """Called only while the plan's process lock is held."""
    row = registry.study_cycle(plan_id)
    if row is None:
        raise ValueError("study plan has no cycle to resume")
    request = read_checkpoint(row["request"])
    if row["status"] not in {"studying", "practicing", "proving"}:
        result = row["result"]
        receipt = read_checkpoint({"path": result["receipt_path"], "sha256": result["receipt_sha256"]})
        if receipt != {key: value for key, value in result.items() if key not in {"receipt_path", "receipt_sha256"}}:
            raise ValueError("terminal study checkpoint differs from its receipt")
        return result
    if request.get("resume_protocol") != 1:
        raise ValueError("legacy interrupted study has no resumable call journal; create a fresh plan with new holdouts")
    cycle = _restore(registry, lab, llm, row, request)
    cycle.result["resume_count"] += 1
    if not _reconcile_pending(cycle):
        return cycle._finish("reconciliation_required")
    try:
        cycle._charge(0)
    except StudyBudgetStop as exc:
        return cycle._finish(str(exc))
    cycle._progress(row["status"])
    return cycle.run()
