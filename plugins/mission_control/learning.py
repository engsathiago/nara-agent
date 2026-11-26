"""Extract, evaluate, promote, and roll back procedural learning from verified missions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, Callable, Iterable, Protocol

from plugins.mission_control.contracts import EffectStatus, MissionStatus, load_contract, utc_now
from plugins.mission_control.store import MissionNotFoundError, MissionStore, completion_blockers

if TYPE_CHECKING:
    from plugins.mission_control.learning_fabric import LearningFabric


class ProceduralMemory(Protocol):
    def add(self, content: str, **kwargs: Any) -> dict[str, Any]: ...
    def get(self, memory_id: str) -> dict[str, Any]: ...
    def promote(self, memory_id: str) -> dict[str, Any]: ...
    def reject(self, memory_id: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ProcedureCandidate:
    candidate_id: str
    mission_id: str
    name: str
    description: str
    steps: tuple[str, ...]
    evidence_artifact_ids: tuple[str, ...]
    source_event_count: int
    created_at: str
    version: int = 1
    status: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    return "-".join(part for part in normalized.split("-") if part)[:60] or "learned-procedure"


def _candidate_fingerprint(mission_id: str, name: str, steps: list[str] | tuple[str, ...],
                           artifacts: list[str] | tuple[str, ...]) -> str:
    return hashlib.sha256(json.dumps(
        [mission_id, name, list(steps), sorted(set(artifacts))], sort_keys=True,
    ).encode()).hexdigest()[:20]


class LearningLab:
    def __init__(
        self,
        missions: MissionStore,
        memory: ProceduralMemory,
        candidate_root: Path | str,
        skill_root: Path | str,
        source_fabric: LearningFabric | None = None,
    ):
        self.missions = missions
        self.memory = memory
        self.candidate_root = Path(candidate_root)
        self.skill_root = Path(skill_root)
        self.source_fabric = source_fabric

    def _candidate_path(self, candidate_id: str) -> Path:
        return self.candidate_root / f"{candidate_id}.json"

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(path)

    def extract(self, mission_id: str, *, name: str | None = None) -> ProcedureCandidate:
        mission = self.missions.get(mission_id)
        if mission is None:
            raise MissionNotFoundError(mission_id)
        if mission.status is not MissionStatus.COMPLETED or completion_blockers(mission):
            raise ValueError("procedures can only be extracted from independently verified missions")
        steps = []
        artifacts: list[str] = []
        for payload in mission.receipts.values():
            receipt = load_contract(payload)
            if getattr(receipt, "effect_status", None) is not EffectStatus.CONFIRMED:
                continue
            steps.append(
                f"Execute {receipt.tool} for {receipt.intention}; verify the observed target before continuing.")
            artifacts.extend(receipt.artifact_ids)
        for payload in mission.verifications.values():
            verification = load_contract(payload)
            method = getattr(verification, "method", "")
            criterion = getattr(verification, "criterion", "")
            if method and criterion:
                steps.append(f"Prove '{criterion}' using {method} and retain the evidence artifact.")
            artifacts.extend(getattr(verification, "evidence_artifact_ids", []))
        steps = list(dict.fromkeys(steps))
        if not steps:
            raise ValueError("verified mission contains no reusable observed procedure")
        candidate_name = name or f"Procedure learned from {mission.objective}"
        fingerprint = _candidate_fingerprint(mission_id, candidate_name, steps, artifacts)
        candidate = ProcedureCandidate(
            candidate_id=fingerprint,
            mission_id=mission_id,
            name=candidate_name,
            description=f"Verified procedure derived from mission {mission_id}.",
            steps=tuple(steps),
            evidence_artifact_ids=tuple(sorted(set(artifacts))),
            source_event_count=len(self.missions.events(mission_id)),
            created_at=utc_now(),
        )
        existing_path = self._candidate_path(candidate.candidate_id)
        if existing_path.exists():
            existing = self.load(candidate.candidate_id)
            try:
                self.memory.get(f"procedure:{candidate.candidate_id}")
            except KeyError:
                if existing.status != "candidate":
                    raise ValueError("promoted procedure has no matching memory; manual repair required")
                # Repair a prior interrupted extraction below.
            else:
                return existing
        self._write_json(existing_path, candidate.to_dict())
        self.memory.add(
            "\n".join(candidate.steps),
            layer="procedural",
            source_type="verified_mission",
            source_ref=f"mission:{mission_id}:candidate:{candidate.candidate_id}",
            mission_id=mission_id,
            status="candidate",
            confidence=0.8,
            memory_id=f"procedure:{candidate.candidate_id}",
            metadata={"candidate": candidate.to_dict()},
        )
        return candidate

    def load(self, candidate_id: str) -> ProcedureCandidate:
        payload = json.loads(self._candidate_path(candidate_id).read_text(encoding="utf-8-sig"))
        payload["steps"] = tuple(payload["steps"])
        payload["evidence_artifact_ids"] = tuple(payload["evidence_artifact_ids"])
        allowed = {field.name for field in fields(ProcedureCandidate)}
        candidate = ProcedureCandidate(**{key: value for key, value in payload.items() if key in allowed})
        if candidate.candidate_id != candidate_id or _candidate_fingerprint(
            candidate.mission_id, candidate.name, candidate.steps, candidate.evidence_artifact_ids,
        ) != candidate_id:
            raise ValueError("procedure candidate content does not match its identity")
        return candidate

    def propose_from_media(
        self, source_id: str, repository_claim_id: str, name: str,
        steps: list[str], quotes: list[str],
    ) -> ProcedureCandidate:
        """Keep a sourced media procedure inactive until reserved transfer passes."""
        if self.source_fabric is None:
            raise ValueError("media procedure proposals require a Learning Fabric")
        from plugins.mission_control.learning_github_source import _check_cited_source

        fabric = self.source_fabric
        source = fabric.source(source_id)
        _check_cited_source(source)
        claim = fabric.claim(repository_claim_id)
        if (claim["source_id"] != source_id or claim["status"] != "verified"
                or claim["verifier_id"] != "github-public-rest-v1"):
            raise ValueError("media procedure requires a verified repository from the same source")
        clean_name = name.strip()
        clean_steps = [step.strip() for step in steps]
        if (not clean_name or len(clean_name) > 120 or "\n" in clean_name or "\r" in clean_name
                or not 1 <= len(clean_steps) <= 12 or len(clean_steps) != len(quotes)
                or any(not step or len(step) > 500 or "\n" in step or "\r" in step for step in clean_steps)):
            raise ValueError("provide a name and one bounded step with an exact quote for each step")
        text = source["extracted_text"] or ""
        if any(not quote.strip() or len(quote) > 2000 or quote not in text for quote in quotes):
            raise ValueError("each procedure step requires an exact quote in the extracted source")
        provenance = {
            "kind": "media_procedure_provenance", "schema_version": 1,
            "source_id": source_id, "source_uri": source["source_uri"],
            "source_hash": source["source_hash"], "version": source["version"],
            "license": source["license"] or "unknown",
            "repository_claim_id": repository_claim_id,
            "name": clean_name, "steps": clean_steps, "quotes": quotes,
        }
        raw = json.dumps(provenance, sort_keys=True, ensure_ascii=False).encode()
        provenance_hash, _ = fabric._store(raw)
        artifacts = [f"sha256:{source['source_hash']}", f"sha256:{provenance_hash}",
                     *claim["evidence_artifact_ids"]]
        origin = f"media:{source_id}"
        fingerprint = _candidate_fingerprint(origin, clean_name, clean_steps, artifacts)
        candidate = ProcedureCandidate(
            candidate_id=fingerprint, mission_id=origin, name=clean_name,
            description=f"Unverified media procedure from {source['source_uri']}; use only after reserved transfer evaluation.",
            steps=tuple(clean_steps), evidence_artifact_ids=tuple(sorted(set(artifacts))),
            source_event_count=0, created_at=utc_now(),
        )
        existing_path = self._candidate_path(candidate.candidate_id)
        if existing_path.exists():
            existing = self.load(candidate.candidate_id)
            try:
                self.memory.get(f"procedure:{candidate.candidate_id}")
            except KeyError:
                if existing.status != "candidate":
                    raise ValueError("promoted media procedure has no matching memory; manual repair required")
            else:
                return existing
        self._write_json(existing_path, candidate.to_dict())
        self.memory.add(
            "\n".join(candidate.steps), layer="procedural", source_type="external_media",
            source_ref=f"{origin}:candidate:{candidate.candidate_id}",
            source_hash=source["source_hash"], status="candidate", confidence=0.3,
            memory_id=f"procedure:{candidate.candidate_id}",
            metadata={"candidate": candidate.to_dict(), "provenance_hash": provenance_hash},
        )
        return candidate

    def _check_media_origin(self, candidate: ProcedureCandidate) -> None:
        if not candidate.mission_id.startswith("media:"):
            return
        if self.source_fabric is None:
            raise ValueError("media procedure evaluation requires a Learning Fabric")
        from plugins.mission_control.learning_github_source import _check_cited_source

        fabric = self.source_fabric
        source_id = candidate.mission_id.removeprefix("media:")
        source = fabric.source(source_id)
        _check_cited_source(source)
        expected_artifacts = set(candidate.evidence_artifact_ids)
        if f"sha256:{source['source_hash']}" not in expected_artifacts:
            raise ValueError("media procedure lost its source evidence")
        provenance = None
        for artifact_id in expected_artifacts:
            if not artifact_id.startswith("sha256:") or artifact_id == f"sha256:{source['source_hash']}":
                continue
            fabric._check_archived_evidence([artifact_id])
            digest = artifact_id[7:]
            path = fabric.root / "sources" / digest[:2] / digest
            if path.stat().st_size > 100_000:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except (UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and payload.get("kind") == "media_procedure_provenance":
                provenance = payload
        if provenance is None or (
            provenance.get("source_id") != source_id
            or provenance.get("source_hash") != source["source_hash"]
            or provenance.get("name") != candidate.name
            or provenance.get("steps") != list(candidate.steps)
            or any(quote not in (source["extracted_text"] or "") for quote in provenance.get("quotes", []))
            or len(provenance.get("quotes", [])) != len(candidate.steps)
        ):
            raise ValueError("media procedure provenance is missing or has changed")
        claim = fabric.claim(provenance["repository_claim_id"])
        if (claim["source_id"] != source_id or claim["status"] != "verified"
                or claim["verifier_id"] != "github-public-rest-v1"
                or not set(claim["evidence_artifact_ids"]) <= expected_artifacts):
            raise ValueError("media procedure repository evidence is no longer verified")

    def evaluate_transfer(
        self,
        candidate_id: str,
        cases: Iterable[dict[str, Any]],
        runner: Callable[[ProcedureCandidate | None, dict[str, Any]], float | dict[str, Any]],
        *,
        development_case_ids: set[str],
        evaluator_sha256: str | None = None,
        evaluator_path: str | None = None,
    ) -> dict[str, Any]:
        candidate = self.load(candidate_id)
        self._check_media_origin(candidate)
        case_list = list(cases)
        holdout = [case for case in case_list if str(case["case_id"]) not in development_case_ids]
        if not holdout:
            raise ValueError("transfer evaluation requires at least one reserved holdout case")
        rows = []
        for case in holdout:
            baseline_result = runner(None, case)
            candidate_result = runner(candidate, case)
            baseline = float(baseline_result["score"] if isinstance(baseline_result, dict) else baseline_result)
            learned = float(candidate_result["score"] if isinstance(candidate_result, dict) else candidate_result)
            rows.append({
                "case_id": str(case["case_id"]),
                "baseline": baseline,
                "candidate": learned,
                "delta": learned - baseline,
                "baseline_evidence": baseline_result.get("evidence", []) if isinstance(baseline_result, dict) else [],
                "candidate_evidence": candidate_result.get("evidence", []) if isinstance(candidate_result, dict) else [],
            })
        mean_delta = sum(row["delta"] for row in rows) / len(rows)
        regressions = sum(row["delta"] < 0 for row in rows)
        report = {
            "schema_version": 1,
            "candidate_id": candidate_id,
            "candidate_hash": hashlib.sha256(json.dumps(candidate.to_dict(), sort_keys=True).encode()).hexdigest(),
            "evaluator_sha256": evaluator_sha256,
            "evaluator_path": evaluator_path,
            "development_case_ids": sorted(development_case_ids),
            "holdout_case_ids": [row["case_id"] for row in rows],
            "mean_delta": mean_delta,
            "regressions": regressions,
            "passed": mean_delta > 0 and regressions == 0,
            "cases": rows,
            "evaluated_at": utc_now(),
        }
        self._write_json(self.candidate_root / f"{candidate_id}.eval.json", report)
        return report

    def promote(self, candidate_id: str, *, require_evidence: bool = False) -> Path:
        candidate = self.load(candidate_id)
        self._check_media_origin(candidate)
        report_path = self.candidate_root / f"{candidate_id}.eval.json"
        if not report_path.is_file():
            raise ValueError("candidate has no reserved transfer evaluation")
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        if not report.get("passed"):
            raise ValueError("candidate did not pass reserved transfer evaluation")
        expected_hash = hashlib.sha256(json.dumps(candidate.to_dict(), sort_keys=True).encode()).hexdigest()
        if report.get("candidate_id") != candidate_id or (
            report.get("candidate_hash") is not None and report["candidate_hash"] != expected_hash
        ):
            raise ValueError("candidate changed after transfer evaluation")
        if require_evidence:
            if report.get("candidate_hash") != expected_hash or not report.get("evaluator_sha256"):
                raise ValueError("promotion requires an executable evaluator and exact candidate hash")
            evaluator_path = Path(report.get("evaluator_path") or "")
            if not evaluator_path.is_file() or hashlib.sha256(evaluator_path.read_bytes()).hexdigest() != report["evaluator_sha256"]:
                raise ValueError("evaluator source is missing or changed")
            if not report.get("cases"):
                raise ValueError("promotion requires reserved transfer cases")
            for row in report["cases"]:
                for key in ("baseline_evidence", "candidate_evidence"):
                    if not row.get(key):
                        raise ValueError("promotion requires evidence from both variants")
                    for artifact in row[key]:
                        path = Path(artifact["path"])
                        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
                            raise ValueError("transfer evidence is missing or changed")
        skill_name = f"nara-learned-{_slug(candidate.name)}-{candidate.candidate_id[:8]}"
        destination = self.skill_root / skill_name
        destination.mkdir(parents=True, exist_ok=True)
        procedure = "\n".join(
            f"{index}. {step}" for index, step in enumerate(candidate.steps, start=1))
        body = (
            "---\n"
            f"name: {skill_name}\n"
            f"description: {json.dumps(candidate.description, ensure_ascii=False)}\n"
            f"version: 1.0.0\n"
            "author: Nara Evolution Lab\n"
            "metadata:\n"
            f"  {'source_media' if candidate.mission_id.startswith('media:') else 'source_mission'}: {candidate.mission_id}\n"
            f"  candidate_id: {candidate.candidate_id}\n"
            "---\n\n"
            f"# {candidate.name}\n\n"
            "## Procedure\n\n"
            f"{procedure}\n\n"
            "## Verification\n\n"
            "Re-run the target task's independent completion criteria and preserve evidence.\n"
        )
        (destination / "SKILL.md").write_text(body, encoding="utf-8")
        self.memory.promote(f"procedure:{candidate.candidate_id}")
        promoted = {**candidate.to_dict(), "status": "promoted", "skill_path": str(destination)}
        self._write_json(self._candidate_path(candidate_id), promoted)
        return destination

    def rollback(self, candidate_id: str) -> Path:
        candidate = self.load(candidate_id)
        active = next(self.skill_root.glob(f"nara-learned-*-{candidate.candidate_id[:8]}"), None)
        if active is None:
            raise ValueError("promoted skill not found")
        disabled = active.with_name(active.name + ".disabled")
        if disabled.exists():
            disabled = active.with_name(active.name + f".disabled-{hashlib.sha256(utc_now().encode()).hexdigest()[:8]}")
        active.replace(disabled)
        memory = self.memory.get(f"procedure:{candidate.candidate_id}")
        if memory["status"] == "active":
            self.memory.reject(memory["memory_id"])
        rolled_back = {**candidate.to_dict(), "status": "rolled_back", "skill_path": str(disabled)}
        self._write_json(self._candidate_path(candidate_id), rolled_back)
        return disabled
