"""Evaluate an exact native skill in disposable profiles, without publishing it."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from plugins.mission_control.learning_runner import ProcessEvaluator
from plugins.mission_control.study_checkpoint import read_checkpoint, verify_evaluator_result


class SkillCanaryEvaluator(ProcessEvaluator):
    def __init__(self, *args, skill_name, skill_bytes, candidate_variant, **kwargs):
        super().__init__(*args, **kwargs)
        if not re.fullmatch(r"nara-learned-[\w-]+", skill_name):
            raise ValueError("invalid learned skill name")
        self.skill_name, self.skill_bytes = skill_name, skill_bytes
        self.candidate_variant = candidate_variant
        self.skill_hash = hashlib.sha256(skill_bytes).hexdigest() if candidate_variant else None

    def prepare_request(self, workdir, candidate, case):
        if candidate is not None:
            raise ValueError("native skill canary must not receive procedure JSON")
        request = super().prepare_request(workdir, None, case)
        if self.candidate_variant:
            path = workdir / "profile" / "skills" / self.skill_name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_bytes(self.skill_bytes)
        request["canary"] = {"skill_name": self.skill_name, "variant": "candidate" if self.candidate_variant else "baseline"}
        return request

    def finish_result(self, response, payload, request, workdir):
        path = workdir / "profile" / "skills" / self.skill_name / "SKILL.md"
        observed = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if (observed != self.skill_hash or "observed_skill_sha256" not in payload
                or payload["observed_skill_sha256"] != self.skill_hash):
            raise ValueError("canary did not observe the exact declared native skill")
        record = {"kind": "native_skill_canary", "request": request, "skill_sha256": observed,
                  "evaluator_sha256": self.sha256, "result": response}
        raw = json.dumps(record, sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()
        destination = self.evidence_root / digest[:2] / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != raw:
                raise ValueError("canary evidence bytes changed")
        else:
            with NamedTemporaryFile("wb", dir=destination.parent, delete=False) as output:
                output.write(raw)
                staged = Path(output.name)
            staged.replace(destination)
        return {**response, "skill_sha256": observed,
                "evidence": [*response["evidence"], {"sha256": digest, "path": str(destination), "bytes": len(raw)}]}


def verify_canary_result(result, case, name, digest, evaluator_hash):
    verify_evaluator_result(result)
    receipt = read_checkpoint(result["evidence"][-1])
    original = {key: value for key, value in result.items() if key != "skill_sha256"}
    original["evidence"] = result["evidence"][:-1]
    expected = {"schema_version": 1, "candidate": None, "case": case,
                "canary": {"skill_name": name, "variant": "candidate" if digest else "baseline"}}
    if (receipt.get("kind") != "native_skill_canary" or receipt.get("request") != expected
            or receipt.get("evaluator_sha256") != evaluator_hash or receipt.get("skill_sha256") != digest
            or result.get("skill_sha256") != digest or receipt.get("result") != original):
        raise ValueError("native skill canary evidence does not match its observation")
    return result
