"""Bounded source study, development feedback, and one reserved evaluation."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.learning import LearningLab
from plugins.mission_control.learning_github_source import _check_cited_source
from plugins.mission_control.learning_runner import ProcessEvaluator, load_evaluation_cases
from plugins.mission_control.learning_study import study_media
from plugins.mission_control.study_checkpoint import initial_result, read_checkpoint, study_lock, verify_evaluator_result
from plugins.mission_control.study_execution import _archive, execute_study, record_study_proof


class StudyBudgetStop(RuntimeError):
    pass


class StudyEvaluator(ProcessEvaluator):
    def __init__(self, *args, deadline: float, max_calls: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.deadline, self.max_calls = deadline, max_calls
        self.call_timeout, self.calls = self.timeout, 0
        self.on_result = None
        self.on_start = None
        self.replay = {}

    def __call__(self, candidate, case):
        key = (candidate.candidate_id if candidate else None, str(case["case_id"]))
        if key in self.replay:
            return verify_evaluator_result(self.replay[key])
        remaining = self.deadline - time.monotonic()
        if self.calls >= self.max_calls or remaining < 1:
            raise StudyBudgetStop("budget_exhausted")
        self.timeout = min(self.call_timeout, remaining)
        self.calls += 1
        if self.on_start is not None:
            self.on_start(candidate, case)
        result = super().__call__(candidate, case)
        verify_evaluator_result(result)
        if self.on_result is not None:
            self.on_result(result, candidate, case)
        return result


def _validate_protocol(registry, lab, plan, source_id, cases_file, system, max_attempts, max_seconds):
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 5:
        raise ValueError("study max-attempts must be from 1 to 5")
    if not isinstance(max_seconds, (int, float)) or not 1 <= max_seconds <= 3600:
        raise ValueError("study max-seconds must be from 1 to 3600")
    if not isinstance(system, dict) or not system:
        raise ValueError("study system must be a nonempty JSON object")
    if cases_file.stat().st_size > 1_000_000:
        raise ValueError("study cases exceed 1 MB")
    cases = load_evaluation_cases(cases_file, set(plan.development_case_ids))
    if {str(case["case_id"]) for case in cases} != set(plan.development_case_ids + plan.holdout_case_ids):
        raise ValueError("study cases must match exactly the plan's development and reserved cases")
    if len(plan.development_case_ids) > 10 or len(plan.holdout_case_ids) > 20:
        raise ValueError("study cycle supports at most 10 development and 20 reserved cases")
    source = lab.source_fabric.source(source_id)
    _check_cited_source(source)
    versions = {source["source_hash"], "sha256:" + source["source_hash"]}
    if source.get("version"):
        versions.add(source["version"])
    if not any(item["uri"] in {source_id, source["source_uri"]} and item["version"] in versions
               for item in plan.sources):
        raise ValueError("archived source and version must be declared in the study plan")
    budget = registry.gap(plan.gap_id)["budget_usd"]
    if budget is not None and (not math.isfinite(budget) or budget <= 0):
        raise ValueError("study monetary budget must be positive and finite")
    return cases, source, budget


class StudyCycle:
    def __init__(self, registry: CompetenceRegistry, lab: LearningLab, llm: Any,
                 plan_id: str, source_id: str, *, cases_file: Path, evaluator_path: Path,
                 system: dict[str, Any], max_attempts: int = 3, max_seconds: float = 600,
                 timeout: float = 30.0, teaching_material: dict[str, Any] | None = None):
        if llm is None:
            raise ValueError("host model access is unavailable on this surface")
        self.registry, self.lab, self.llm = registry, lab, llm
        self.plan = registry.study_plan(plan_id)
        self.source_id, self.system = source_id, system
        self.teaching_material = teaching_material
        self.max_attempts = max_attempts
        cases, source, self.budget_usd = _validate_protocol(
            registry, lab, self.plan, source_id, cases_file, system, max_attempts, max_seconds)
        self.deadline = time.monotonic() + max_seconds
        by_id = {str(case["case_id"]): case for case in cases}
        self.development = [by_id[case_id] for case_id in self.plan.development_case_ids]
        max_calls = max_attempts * len(self.development) + 2 * len(self.plan.holdout_case_ids)
        self.evaluator = StudyEvaluator(
            evaluator_path, lab.candidate_root / "evidence", timeout=timeout,
            deadline=self.deadline, max_calls=max_calls)
        request = {
            "kind": "study_cycle_request", "schema_version": 2, "resume_protocol": 1,
            "plan": self.plan.to_dict(), "deadline_at": time.time() + max_seconds,
            "source_id": source_id, "source_hash": source["source_hash"], "cases": cases,
            "system": system, "evaluator_sha256": self.evaluator.sha256,
            "evaluator": {"path": str(self.evaluator.archived_path), "sha256": self.evaluator.sha256,
                          "python_script": self.evaluator.python_script},
            "max_generation_calls": max_attempts, "max_evaluator_calls": max_calls,
            "max_seconds": max_seconds, "timeout_per_variant_seconds": timeout,
            "max_output_tokens_per_generation": 2048, "budget_usd": self.budget_usd,
        }
        if teaching_material is not None:
            request["teaching_material"] = teaching_material
        self.request_path, self.request_hash = _archive(lab, request)
        self.cycle_id = registry.claim_study_cycle(plan_id, {
            "path": str(self.request_path), "sha256": self.request_hash,
        })
        self.result = initial_result(self.cycle_id, plan_id, source_id, self.request_path, self.request_hash)
        self.evaluator.on_start = self._before_evaluation
        self.evaluator.on_result = self._observe_evaluation
        self._progress("studying")

    def _progress(self, status):
        self.result.update(status=status, evaluator_calls_started=self.evaluator.calls)
        self.registry.update_study_cycle(self.cycle_id, status, self.result)

    def _finish(self, status):
        self.result.update(status=status, evaluator_calls_started=self.evaluator.calls)
        path, digest = _archive(self.lab, self.result)
        self.result.update(receipt_path=str(path), receipt_sha256=digest)
        self.registry.update_study_cycle(self.cycle_id, status, self.result)
        return self.result

    def _charge(self, cost):
        if not isinstance(cost, bool) and isinstance(cost, (int, float)) and math.isfinite(cost) and cost >= 0:
            self.result["estimated_cost_usd"] += cost
        else:
            self.result["cost_unknown"] = True
        if self.budget_usd is not None:
            if self.result["cost_unknown"]:
                raise StudyBudgetStop("budget_unverifiable")
            if self.result["estimated_cost_usd"] >= self.budget_usd:
                raise StudyBudgetStop("budget_exhausted")

    def _before_evaluation(self, candidate, case):
        self.result["pending_call"] = {
            "kind": "evaluator", "call_number": self.evaluator.calls,
            "case_id": str(case["case_id"]), "variant": "candidate" if candidate else "baseline",
            "candidate_id": candidate.candidate_id if candidate else None,
            "phase": "holdout" if self.result["holdout_started"] else "development",
        }
        self._progress("proving" if self.result["holdout_started"] else "practicing")

    def _observe_evaluation(self, result, candidate, case):
        pending = self.result["pending_call"]
        self.result["evaluator_usage"].append({**pending, "result": result,
            "cost_usd": result.get("cost_usd"), "evidence": result["evidence"]})
        pending["observed_result"] = result
        try:
            self._charge(result.get("cost_usd"))
        finally:
            pending["accounted"] = True
            self._progress("proving" if self.result["holdout_started"] else "practicing")

    def _practice(self, candidate, attempt):
        self._progress("practicing")
        for case in self.development:
            if any(row["case_id"] == str(case["case_id"]) for row in attempt["practice"]):
                continue
            result = self.evaluator(candidate, case)
            attempt["practice"].append({"case_id": str(case["case_id"]), "case": case, **result})
            self.result["pending_call"] = None
            self._progress("practicing")
        attempt["practice_complete"] = True
        self._progress("practicing")
        return all(row["score"] >= self.plan.minimum_candidate_score for row in attempt["practice"])

    def _transfer(self, candidate_id, generation):
        self.result.update(holdout_started=True, frozen_candidate_id=candidate_id)
        self._progress("proving")
        if self.result["transfer_proof"]:
            transfer = record_study_proof(self.registry, self.lab, self.plan.plan_id,
                                          candidate_id, self.result["transfer_proof"])
        else:
            transfer = execute_study(
                self.registry, self.lab, self.plan.plan_id, candidate_id,
                cases_file=self.request_path, evaluator_path=self.evaluator.path,
                evaluator=self.evaluator, system={**self.system,
                    "study_provider": generation["provider"], "study_model": generation["model"]},
                checkpoint=self._save_transfer_proof,
            )
        self.result.update(transfer=transfer, pending_call=None)
        passed = self.result["transfer"]["competence"]["passed"]
        return self._finish("completed" if passed else "holdout_failed")

    def _save_transfer_proof(self, proof):
        self.result.update(transfer_proof=proof, pending_call=None)
        self._progress("proving")

    def _generate(self, feedback):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise StudyBudgetStop("budget_exhausted")
        self.result["generation_calls_started"] += 1
        self.result["pending_call"] = {"kind": "generation", "call_number": self.result["generation_calls_started"]}
        self._progress("studying")
        generation = study_media(
            self.lab, self.llm, self.source_id, self.plan.objective,
            development_feedback=feedback, teaching_material=self.teaching_material, timeout=min(120.0, remaining))
        attempt = {"generation_evidence": generation["evidence"],
                   "usage": generation["usage"], "practice": [], "practice_complete": False,
                   "candidate_id": generation.get("candidate", {}).get("candidate_id")}
        self.result["attempts"].append(attempt)
        self.result["pending_call"] = None
        try:
            self._charge(generation["usage"].get("cost_usd"))
        finally:
            self._progress("studying")
        return generation, attempt

    def run(self):
        try:
            return self._run_attempts()
        except StudyBudgetStop as exc:
            return self._finish(str(exc))
        except (ValueError, OSError, KeyError) as exc:
            self.result.update(error_type=type(exc).__name__, reason=str(exc))
            return self._finish("failed")

    def _run_attempts(self):
        feedback, seen = None, set()
        # Revisit durable attempts first. Completed practice is reused; once
        # reserved evaluation begins no generation path is reachable again.
        index = 0
        while index < len(self.result["attempts"]) or self.result["generation_calls_started"] < self.max_attempts:
            if index < len(self.result["attempts"]):
                attempt = self.result["attempts"][index]
                generation = read_checkpoint(attempt["generation_evidence"])
            else:
                generation, attempt = self._generate(feedback)
            index += 1
            if generation["status"] == "no_procedure":
                self.result["reason"] = generation["reason"]
                return self._finish("declined")
            candidate = self.lab.load(attempt["candidate_id"])
            if self.result["holdout_started"]:
                if candidate.candidate_id == self.result["frozen_candidate_id"]:
                    return self._transfer(candidate.candidate_id, generation)
                continue
            if candidate.steps in seen:
                return self._finish("no_change")
            seen.add(candidate.steps)
            if self._practice(candidate, attempt):
                return self._transfer(candidate.candidate_id, generation)
            feedback = {"previous_steps": list(candidate.steps), "cases": [
                {key: row[key] for key in ("case_id", "case", "score", "feedback") if key in row}
                for row in attempt["practice"]]}
        return self._finish("exhausted")


def run_study_cycle(registry, lab, llm, args):
    with study_lock(lab.candidate_root.parent, args.plan_id):
        if args.mission_action == "study-resume":
            from plugins.mission_control.study_resume import resume_study_cycle

            return resume_study_cycle(registry, lab, llm, args.plan_id)
        return StudyCycle(
            registry, lab, llm, args.plan_id, args.source_id,
            cases_file=args.cases_file, evaluator_path=args.evaluator,
            system=json.loads(args.system_file.read_text(encoding="utf-8-sig")),
            max_attempts=args.max_attempts, max_seconds=args.max_seconds, timeout=args.timeout,
            teaching_material=getattr(args, "teaching_material", None),
        ).run()
