"""Durable study jobs projected from the existing mission event log."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
from types import SimpleNamespace
import uuid

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import Mission, Verification, VerificationStatus
from plugins.mission_control.learning_acceptance import validate_minimum_score
from plugins.mission_control.learning_cli import open_learning_lab
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_runner import load_evaluation_cases
from plugins.mission_control.study_checkpoint import StudyBusyError, read_checkpoint, study_lock
from plugins.mission_control.study_cycle import run_study_cycle
from plugins.mission_control.study_research import SourceResearch, research_options
from plugins.mission_control.study_source_selection import SourceSelection
from plugins.mission_control.study_admission import StudyAdmission, prepare_experiment
from plugins.mission_control.study_admission_protocol import freeze_admission
from plugins.mission_control.verification import VerificationService


CRITERION = "Demonstrate the missing procedure on reserved transfer cases"
ADMISSION_CRITERION = "Activate the exact native skill after its reserved canary"


def _freeze_bytes(root, content, suffix, mode=0o600):
    digest = hashlib.sha256(content).hexdigest()
    path = root / (digest + suffix)
    root.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError("frozen study input changed")
    else:
        with NamedTemporaryFile("wb", dir=root, delete=False) as output:
            output.write(content)
            staged = Path(output.name)
        staged.chmod(mode)
        staged.replace(path)
    return {"path": str(path), "sha256": digest}


def _freeze_inputs(root, spec, names=("cases_file", "system_file", "evaluator")):
    files = {}
    for name in names:
        source = Path(spec[name])
        if source.stat().st_size > 1_000_000:
            raise ValueError("study protocol input exceeds 1 MB")
        content = source.read_bytes()
        if len(content) > 1_000_000:
            raise ValueError("study protocol input exceeds 1 MB")
        suffix = ".json" if name != "evaluator" else (".py" if source.suffix == ".py" else ".bin")
        files[name] = _freeze_bytes(root / "inputs", content, suffix, source.stat().st_mode & 0o777)
    return files


def freeze_protocol(root, spec):
    objective, domains = research_options(spec["objective"], spec.get("domains", []),
                                           spec.get("max_sources", 3), spec.get("research_seconds", 120))
    attempts, seconds, timeout = spec.get("max_attempts", 3), spec.get("max_seconds", 600), spec.get("timeout", 30)
    if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= 5:
        raise ValueError("study max-attempts must be from 1 to 5")
    if not 1 <= seconds <= 3600 or not 1 <= timeout <= 120:
        raise ValueError("study deadline or evaluator timeout is outside supported bounds")
    files = _freeze_inputs(root, spec)
    development = list(dict.fromkeys(spec["development_case_ids"]))
    cases = load_evaluation_cases(Path(files["cases_file"]["path"]), set(development))
    holdout = [str(case["case_id"]) for case in cases if str(case["case_id"]) not in development]
    if not development or not holdout or len(development) > 10 or len(holdout) > 20:
        raise ValueError("study requires 1-10 development and 1-20 reserved cases")
    system = read_checkpoint(files["system_file"])
    if not isinstance(system, dict) or not system:
        raise ValueError("study system must be a nonempty JSON object")
    payload = {"schema_version": 2, "objective": objective, "domains": domains,
               "max_sources": spec.get("max_sources", 3), "research_seconds": spec.get("research_seconds", 120),
               "max_attempts": attempts, "max_seconds": seconds, "timeout": timeout,
               "development_case_ids": development, "holdout_case_ids": holdout,
               "minimum_candidate_score": validate_minimum_score(spec.get("minimum_candidate_score", 0.8)),
               "files": files}
    admission = freeze_admission(root, spec.get("skill_admission"), development + holdout, _freeze_inputs)
    if admission is not None:
        payload.update(schema_version=3, skill_admission=admission)
    return _freeze_bytes(root, json.dumps(payload, sort_keys=True).encode(), ".json")


class StudyJobs:
    def __init__(self, missions, registry, dispatch, llm):
        self.missions, self.registry, self.dispatch, self.llm = missions, registry, dispatch, llm
        self.root = missions.path.parent / "learning" / "study-jobs"
        self.artifacts = ArtifactStore(missions, missions.path.parent / "artifacts")

    def enqueue(self, gap_id, spec):
        gap = self.registry.gap(gap_id)
        with study_lock(self.root, "queue"):
            protocol = freeze_protocol(self.root, spec)
            identity = "study-job-" + hashlib.sha256((gap_id + protocol["sha256"]).encode()).hexdigest()[:24]
            existing = self.missions.get(identity)
            if existing is not None:
                if existing.status == "draft":
                    existing = self.missions.transition(identity, "planned", actor_id="study-queue")
                return existing.to_dict()
            mission = self.missions.create(Mission(
                mission_id=identity, objective="Study: " + spec["objective"], completion_criteria=[CRITERION, ADMISSION_CRITERION] if spec.get("skill_admission") is not None else [CRITERION],
                constraints={"study_job": True, "gap_id": gap_id, "protocol": protocol, "impact": gap["impact"]},
                budget={"max_seconds": spec.get("max_seconds", 600), "budget_usd": gap["budget_usd"]},
            ), actor_id="study-queue")
            return self.missions.transition(mission.mission_id, "planned", actor_id="study-queue").to_dict()

    def jobs(self):
        return [mission for mission in self.missions.list() if mission.constraints.get("study_job")]

    def _checkpoint(self, identity, state):
        self.missions.record_diagnostic(identity, {"diagnostic_id": "study_state", **state},
                                        idempotency_key="study-state:" + uuid.uuid4().hex)

    def _protocol(self, mission):
        protocol = read_checkpoint(mission.constraints["protocol"])
        files = [*protocol["files"].values(), *protocol.get("skill_admission", {}).get("files", {}).values()]
        for reference in files:
            if hashlib.sha256(Path(reference["path"]).read_bytes()).hexdigest() != reference["sha256"]:
                raise ValueError("frozen study input changed")
        return protocol

    def run_once(self):
        # OS-owned lock protects queue selection as well as the entire live job;
        # no timestamp or persisted running flag is treated as process liveness.
        with study_lock(self.root, "worker"):
            pending = [job for job in self.jobs() if job.status in {"planned", "running", "verifying"}]
            if not pending:
                return {"status": "idle"}
            job = sorted(pending, key=lambda m: (-m.constraints["impact"], m.created_at))[0]
            return self._run_job(job)

    def _run_job(self, job):
        state = dict(job.diagnostics.get("study_state") or {})
        if job.status == "planned":
            self.missions.transition(job.mission_id, "running", actor_id="study-worker")
        try:
            protocol = self._protocol(job)
            prepare_experiment(job, protocol)
            if not state:
                state = {"phase": "ready", "deadline_at": time.time() + protocol["max_seconds"]}
                self._checkpoint(job.mission_id, state)
            if state["phase"] in {"research_running", "selection_running"}:
                raise ValueError("interrupted research or selection has unconfirmed usage; reconcile before retry")
            if state["phase"] == "ready":
                self._research(job, protocol, state)
            result = self._study(job, protocol, state)
            state.update(phase="finished", result=result)
            self._checkpoint(job.mission_id, state)
            return self._finish(job, protocol, state, result)
        except StudyBusyError:
            return {"job_id": job.mission_id, "status": "busy"}
        except (ValueError, OSError, KeyError) as exc:
            return self._failed(job, state, exc)

    def _failed(self, job, state, error):
        admission = self.missions.get(job.mission_id).diagnostics.get("skill_admission") or {}
        if admission.get("deployment_id") and admission.get("status") in {"publishing", "active"}:
            try:
                StudyAdmission(self, job, {"skill_admission": {}}, 0).rollback("admission failed: " + str(error))
            except (ValueError, OSError) as cleanup:
                self.missions.record_diagnostic(job.mission_id, {
                    "diagnostic_id": "admission_cleanup", "reason": str(cleanup), "original_error": str(error)},
                    idempotency_key="admission-cleanup:" + uuid.uuid4().hex)
                return {"job_id": job.mission_id, "status": "reconciliation_required", "reason": str(cleanup)}
        result = {"status": "failed", "reason": str(error), "error_type": type(error).__name__}
        state.update(phase="finished", result=result)
        self._checkpoint(job.mission_id, state)
        return self._settle(job, result)

    def _finish(self, job, protocol, state, result):
        if protocol.get("skill_admission") and result["status"] == "completed":
            admitted = StudyAdmission(self, job, protocol, state["deadline_at"]).run(result["transfer"])
            if admitted["status"] == "publication_pending":
                return {"job_id": job.mission_id, "status": "publication_pending", "admission": admitted}
            result = {**result, "admission": admitted}
            if admitted["status"] != "active":
                result.update(status="admission_failed", reason=admitted.get("reason"))
            state.update(result=result)
            self._checkpoint(job.mission_id, state)
        return self._settle(job, result)

    def rollback(self, job_id, reason):
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
            raise ValueError("study rollback requires a reason of 1-2000 characters")
        with study_lock(self.root, "worker"):
            job = self.missions.get(job_id)
            if job is None or not job.constraints.get("study_job"):
                raise ValueError("unknown study job")
            return StudyAdmission(self, job, {"skill_admission": {}}, 0).rollback(reason)

    def _research(self, job, protocol, state):
        remaining = state["deadline_at"] - time.time()
        if remaining < 1:
            raise ValueError("study job deadline exhausted")
        research = SourceResearch(
            self.missions, LearningFabric.open_default(), self.dispatch,
            self.registry.gap(job.constraints["gap_id"]), protocol["objective"],
            domains=protocol["domains"], max_sources=protocol["max_sources"],
            max_seconds=min(remaining, protocol["research_seconds"]))
        state.update(phase="research_running", research_mission_id=research.mission_id)
        self._checkpoint(job.mission_id, state)
        result = research.run()
        state.update(phase="sources_ready", research=result)
        self._checkpoint(job.mission_id, state)
        if not result["sources"]:
            raise ValueError("research did not acquire a usable source")

    def _selected_source(self, job, protocol, state):
        sources = state["research"]["sources"]
        # Protocol v1 jobs keep their original search-rank choice on replay.
        if protocol["schema_version"] == 1:
            return sources[0]
        selection = SourceSelection(self.artifacts, LearningFabric.open_default(), self.llm, job.mission_id)
        if "selection_artifact_id" not in state:
            remaining = state["deadline_at"] - time.time()
            if remaining < 1:
                raise ValueError("study job deadline exhausted before source selection")

            def on_start(request_id):
                state.update(phase="selection_running", selection_request_artifact_id=request_id)
                self._checkpoint(job.mission_id, state)

            receipt = selection.run(sources, protocol["objective"], min(120, remaining), on_start)
            state.update(phase="sources_selected", selection_artifact_id=receipt)
            self._checkpoint(job.mission_id, state)
        return selection.restore(state["selection_artifact_id"], sources, protocol["objective"])

    def _study(self, job, protocol, state):
        if state["phase"] == "finished":
            return state["result"]
        if not state["research"]["sources"]:
            raise ValueError("research did not acquire a usable source")
        source = self._selected_source(job, protocol, state)
        plan_id = job.mission_id
        try:
            plan = self.registry.study_plan(plan_id)
        except KeyError:
            plan = self.registry.create_study_plan(
                job.constraints["gap_id"], protocol["objective"], plan_id=plan_id,
                sources=[{"uri": source["source_id"], "version": source["source_hash"]}],
                development_case_ids=protocol["development_case_ids"], holdout_case_ids=protocol["holdout_case_ids"],
                minimum_candidate_score=protocol["minimum_candidate_score"])
        state.update(phase="studying", plan_id=plan.plan_id)
        self._checkpoint(job.mission_id, state)
        cycle = self.registry.study_cycle(plan.plan_id)
        remaining = state["deadline_at"] - time.time()
        if cycle is None and remaining < 1:
            raise ValueError("study job deadline exhausted")
        files = {key: Path(value["path"]) for key, value in protocol["files"].items()}
        args = SimpleNamespace(
            mission_action="study-resume" if cycle else "study-run", plan_id=plan.plan_id,
            source_id=source["source_id"], cases_file=files["cases_file"], evaluator=files["evaluator"],
            system_file=files["system_file"], max_attempts=protocol["max_attempts"],
            max_seconds=remaining, timeout=protocol["timeout"])
        return run_study_cycle(self.registry, open_learning_lab(self.missions), self.llm, args)

    def _settle(self, job, result):
        artifact = self.artifacts.put_bytes(
            job.mission_id, json.dumps(result, sort_keys=True).encode(),
            producer_id="study-worker", media_type="application/json")
        if result["status"] == "completed" and result["transfer"]["competence"]["passed"]:
            lab = open_learning_lab(self.missions)
            if lab.verified_evaluation(result["transfer"]["candidate_id"]) != result["transfer"]["evaluation"]:
                raise ValueError("study transfer evidence changed before mission settlement")
            current = self.missions.get(job.mission_id)
            existing = current.verifications.get("study-proof")
            if existing is None:
                VerificationService(self.missions, self.artifacts).record(Verification(
                    verification_id="study-proof", mission_id=job.mission_id, criterion=CRITERION,
                    verifier_id="study-proof-verifier", executor_id="study-worker", status=VerificationStatus.PASS,
                    evidence_artifact_ids=[artifact.artifact_id], method="reserved-transfer",
                    explanation="Exact candidate and reserved evaluator evidence passed the predeclared floor"))
            elif existing["status"] != "pass" or existing["evidence_artifact_ids"] != [artifact.artifact_id]:
                raise ValueError("existing study job proof does not match the verified result")
            if ADMISSION_CRITERION in current.completion_criteria:
                admitted = result["admission"]
                proof = json.loads(self.artifacts.read_bytes(job.mission_id, admitted["artifact_id"]))
                if proof["status"] != "active" or proof["candidate_id"] != result["transfer"]["candidate_id"]:
                    raise ValueError("native skill admission proof does not match the completed study")
                if "skill-proof" not in current.verifications:
                    VerificationService(self.missions, self.artifacts).record(Verification(
                        verification_id="skill-proof", mission_id=job.mission_id, criterion=ADMISSION_CRITERION,
                        verifier_id="native-skill-verifier", executor_id="study-worker", status=VerificationStatus.PASS,
                        evidence_artifact_ids=[admitted["artifact_id"]], method="native-skill-canary",
                        explanation="Frozen native skill canary passed and the same bytes are active"))
                elif current.verifications["skill-proof"]["evidence_artifact_ids"] != [admitted["artifact_id"]]:
                    raise ValueError("native skill proof changed before settlement")
            if self.missions.get(job.mission_id).status == "running":
                self.missions.transition(job.mission_id, "verifying", actor_id="study-worker")
            self.missions.transition(job.mission_id, "completed", actor_id="study-worker")
        else:
            self.registry.transition_gap(job.constraints["gap_id"], "unresolved")
            self.missions.transition(job.mission_id, "failed", actor_id="study-worker", reason=result["status"])
        return {"job_id": job.mission_id, "status": result["status"], "result_artifact_id": artifact.artifact_id, "reason": result.get("reason")}
