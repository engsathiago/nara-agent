"""Connect verified study to isolated native-skill canaries and recoverable activation."""

from __future__ import annotations

import json
from pathlib import Path
import time
import uuid

from plugins.mission_control.evolution import EvolutionLab
from plugins.mission_control.learning_canary import SkillCanaryEvaluator, verify_canary_result
from plugins.mission_control.learning_cli import open_learning_lab
from plugins.mission_control.learning_deployment import skill_artifact
from plugins.mission_control.study_checkpoint import StudyBusyError, read_checkpoint, study_lock, verify_evaluator_result


def prepare_experiment(job, protocol):
    spec = protocol.get("skill_admission")
    if spec is None:
        return
    evolution = EvolutionLab.open_default()
    identity = job.mission_id + ":skill"
    try:
        experiment = evolution.experiment(identity)
    except KeyError:
        experiment = evolution.create_experiment(
            "Native skill: " + protocol["objective"], "skill", experiment_id=identity,
            development_case_ids=protocol["development_case_ids"] + protocol["holdout_case_ids"],
            holdout_case_ids=spec["case_ids"], min_mean_delta=spec["minimum_gain"], max_regressions=0,
            min_candidate_score=spec["minimum_score"])
    if (experiment["holdout_case_ids"] != spec["case_ids"]
            or experiment["min_mean_delta"] != spec["minimum_gain"] or experiment["max_regressions"] != 0
            or experiment["min_candidate_score"] != spec["minimum_score"]):
        raise ValueError("skill experiment differs from the frozen protocol")
    evolution.register_variant(identity, b"", baseline=True, variant_id=identity + ":baseline",
                               metadata={"kind": "no_native_skill"})


class StudyAdmission:
    def __init__(self, jobs, job, protocol, deadline):
        self.jobs, self.job, self.protocol, self.deadline = jobs, job, protocol, deadline
        self.spec = protocol["skill_admission"]
        self.lab = open_learning_lab(jobs.missions)
        self.evolution = EvolutionLab.open_default()
        current = jobs.missions.get(job.mission_id)
        self.state = dict(current.diagnostics.get("skill_admission") or {
            "diagnostic_id": "skill_admission", "status": "observing", "observations": [],
            "pending_call": None, "experiment_id": job.mission_id + ":skill"})

    def _save(self):
        self.jobs.missions.record_diagnostic(self.job.mission_id, self.state,
                                            idempotency_key="skill-admission:" + uuid.uuid4().hex)

    def _receipt(self):
        artifact = self.jobs.artifacts.put_bytes(
            self.job.mission_id, json.dumps(self.state, sort_keys=True).encode(),
            producer_id="skill-admission", media_type="application/json")
        return {"status": self.state["status"], "artifact_id": artifact.artifact_id,
                "candidate_id": self.state.get("candidate_id"), "reason": self.state.get("reason")}

    def _prepare(self, transfer):
        candidate_id = transfer["candidate_id"]
        if self.lab.verified_evaluation(candidate_id) != transfer["evaluation"]:
            raise ValueError("reserved transfer proof changed before skill admission")
        candidate = self.lab.load(candidate_id)
        destination, content = skill_artifact(self.lab, candidate)
        variant = self.evolution.register_variant(
            self.state["experiment_id"], content, variant_id=self.state["experiment_id"] + ":candidate",
            metadata={"candidate_id": candidate_id})
        self.evolution.reload_variant(variant["variant_id"])
        if self.state.get("candidate_id", candidate_id) != candidate_id:
            raise ValueError("skill admission candidate changed")
        self.state.update(candidate_id=candidate_id, variant_id=variant["variant_id"],
                          skill_sha256=variant["content_hash"], skill_name=destination.name)
        self._verify_observations()
        return destination, content

    def _cases(self):
        cases = read_checkpoint(self.spec["files"]["cases_file"])
        cases = cases["cases"] if isinstance(cases, dict) else cases
        if [str(case["case_id"]) for case in cases] != self.spec["case_ids"]:
            raise ValueError("native skill canary cases changed")
        return cases

    def _verify_observations(self):
        cases = {str(case["case_id"]): case for case in self._cases()}
        seen = set()
        for row in self.state["observations"]:
            key = (row["case_id"], row["variant"])
            if key in seen or key[0] not in cases or key[1] not in {"baseline", "candidate"}:
                raise ValueError("native skill canary contains duplicate or undeclared observations")
            seen.add(key)
            verify_canary_result(row["result"], cases[key[0]], self.state["skill_name"],
                                 self.state["skill_sha256"] if key[1] == "candidate" else None,
                                 self.spec["files"]["evaluator"]["sha256"])

    def _observe(self, content):
        cases = self._cases()
        completed = {(row["case_id"], row["variant"]) for row in self.state["observations"]}
        for case in cases:
            for variant in ("baseline", "candidate"):
                key = (str(case["case_id"]), variant)
                if key in completed:
                    continue
                remaining = self.deadline - time.time()
                if remaining < 1:
                    raise ValueError("study job deadline exhausted before native skill canary")
                evaluator = SkillCanaryEvaluator(
                    self.spec["files"]["evaluator"]["path"], self.lab.candidate_root / "canary-evidence",
                    timeout=min(remaining, self.protocol["timeout"]), skill_name=self.state["skill_name"],
                    skill_bytes=content, candidate_variant=variant == "candidate")
                if evaluator.sha256 != self.spec["files"]["evaluator"]["sha256"]:
                    raise ValueError("native skill evaluator changed")
                self.state["pending_call"] = {"case_id": key[0], "variant": variant}
                self._save()
                result = evaluator(None, case)
                verify_evaluator_result(result)
                self.state["observations"].append({**self.state["pending_call"], "result": result})
                self.state["pending_call"] = None
                self._save()

    def _evaluate(self):
        self._verify_observations()
        rows = self.state["observations"]
        scores = {variant: {row["case_id"]: row["result"]["score"] for row in rows if row["variant"] == variant}
                  for variant in ("baseline", "candidate")}
        known = all(row["result"].get("cost_usd") is not None for row in rows)
        cost = sum(row["result"]["cost_usd"] for row in rows) if known else None
        receipt = self._receipt()
        evaluation = self.evolution.evaluate(
            self.state["experiment_id"], self.state["variant_id"], baseline_scores=scores["baseline"],
            candidate_scores=scores["candidate"], evidence_artifact_ids=[receipt["artifact_id"]], cost_usd=cost)
        passed = evaluation["passed"] and all(value >= self.spec["minimum_score"] for value in scores["candidate"].values())
        self.state.update(evaluation=evaluation, status="approved" if passed else "failed")
        if not passed:
            self.state["reason"] = "native skill canary did not meet the frozen correctness and improvement floors"
        self._save()

    def _confirm(self, destination, content):
        if (destination / "SKILL.md").read_bytes() != content:
            raise ValueError("published native skill differs from the tested bytes")
        if self.evolution.active_variant(self.state["experiment_id"]) != self.state["variant_id"]:
            raise ValueError("native skill and active evolution variant differ")
        if self.lab.memory.get("procedure:" + self.state["candidate_id"])["status"] != "active":
            raise ValueError("published native skill has no active procedural memory")

    def _publish(self, destination, content):
        try:
            deployment = self.evolution.promote_canary(
                self.state["experiment_id"], self.state["variant_id"],
                deployment_id=self.state["experiment_id"] + ":deployment")
            if deployment["status"] != "active":
                raise ValueError("skill deployment is no longer eligible for activation")
            self.state.update(status="publishing", deployment_id=deployment["deployment_id"])
            self._save()
            self.lab.promote(self.state["candidate_id"], require_evidence=True)
            self.evolution.activate(deployment["deployment_id"])
            self._confirm(destination, content)
        except StudyBusyError:
            raise
        except (ValueError, OSError) as exc:
            self.state.update(status="publishing", reason=str(exc))
            self._save()
            return {**self._receipt(), "status": "publication_pending"}
        self.state.update(status="active")
        self.state.pop("reason", None)
        self._save()
        return self._receipt()

    def run(self, transfer):
        if self.state["status"] in {"failed", "reconciliation_required", "rolled_back"}:
            return self._receipt()
        destination, content = self._prepare(transfer)
        if self.state["pending_call"]:
            self.state.update(status="reconciliation_required", reason="native skill canary has unconfirmed execution")
            self._save()
            return self._receipt()
        if self.state["status"] == "observing":
            self._observe(content)
            self._evaluate()
        if self.state["status"] == "failed":
            return self._receipt()
        if self.state["status"] == "active":
            self._confirm(destination, content)
            return self._receipt()
        return self._publish(destination, content)

    def rollback(self, reason):
        if self.state["status"] == "rolled_back":
            return self._receipt()
        if not self.state.get("deployment_id"):
            raise ValueError("study has no deployed native skill to roll back")
        try:
            self.lab.rollback(self.state["candidate_id"])
        except ValueError as exc:
            if str(exc) != "promoted skill not found" or self.state["status"] != "publishing":
                raise
            self._cancel_unpublished()
        result = self.evolution.rollback(self.state["deployment_id"], reason)
        self.state.update(status="rolled_back", reason=reason, rollback=result)
        self._save()
        return self._receipt()

    def _cancel_unpublished(self):
        identity = self.state["candidate_id"]
        with study_lock(self.lab.candidate_root, "deployment:" + identity):
            candidate = self.lab.load(identity)
            destination, _ = skill_artifact(self.lab, candidate)
            if destination.exists():
                raise ValueError("native skill appeared during cancellation; retry rollback")
            if self.lab.memory.get("procedure:" + identity)["status"] != "rejected":
                self.lab.memory.reject("procedure:" + identity)
            self.lab._write_json(self.lab._candidate_path(identity), {
                **candidate.to_dict(), "status": "rolled_back", "skill_path": None})
            self.state["unpublished_cancelled"] = True
