"""Run independent transfer cases in separate processes and retain their evidence."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any


def load_evaluation_cases(path: Path, development_case_ids: set[str]) -> list[dict[str, Any]]:
    cases = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(cases, dict):
        cases = cases.get("cases")
    if not isinstance(cases, list) or any(
        not isinstance(case, dict) or not case.get("case_id") for case in cases
    ):
        raise ValueError("cases file must contain cases with unique case_id values")
    ids = [str(case["case_id"]) for case in cases]
    if len(ids) != len(set(ids)) or not development_case_ids <= set(ids):
        raise ValueError("case ids must be unique and development cases must exist")
    return cases


class ProcessEvaluator:
    def __init__(self, path: Path | str, evidence_root: Path | str, *, timeout: float = 30.0):
        self.path = Path(path).resolve()
        if not self.path.is_file():
            raise ValueError(f"evaluator file not found: {self.path}")
        if not 1 <= timeout <= 120:
            raise ValueError("evaluator timeout must be between 1 and 120 seconds")
        self.timeout = timeout
        self.evidence_root = Path(evidence_root)
        source = self.path.read_bytes()
        self.sha256 = hashlib.sha256(source).hexdigest()
        self.archived_path = self.evidence_root / self.sha256[:2] / self.sha256
        self.archived_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.archived_path.exists():
            with NamedTemporaryFile("wb", dir=self.archived_path.parent, delete=False) as output:
                output.write(source)
                staged = Path(output.name)
            staged.replace(self.archived_path)
            self.archived_path.chmod(self.path.stat().st_mode & 0o777)

    def __call__(self, candidate, case: dict[str, Any]) -> dict[str, Any]:
        with TemporaryDirectory(prefix="nara-transfer-case-") as temp:
            workdir = Path(temp).resolve()
            (workdir / "profile").mkdir()
            request = {"schema_version": 1, "case": case,
                       "candidate": candidate.to_dict() if candidate is not None else None}
            command = ([sys.executable, str(self.archived_path)] if self.path.suffix == ".py"
                       else [str(self.archived_path)])
            allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG", "PYTHONPATH"}
            env = {key: value for key, value in os.environ.items() if key in allowed}
            env["NARA_HOME"] = str(workdir / "profile")
            try:
                result = subprocess.run(
                    command, input=json.dumps(request, ensure_ascii=False), text=True,
                    capture_output=True, cwd=workdir, env=env, timeout=self.timeout, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError(f"evaluator timed out after {self.timeout:g}s") from exc
            if result.returncode:
                raise ValueError(f"evaluator exited {result.returncode}: {result.stderr[-500:]}")
            if len(result.stdout) > 65536:
                raise ValueError("evaluator response exceeds 64 KiB")
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise ValueError("evaluator must print one JSON result") from exc
            if not isinstance(payload, dict):
                raise ValueError("evaluator result must be an object")
            score = payload.get("score")
            if isinstance(score, bool) or not isinstance(score, (float, int)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("evaluator score must be a finite number from 0 to 1")
            paths = payload.get("artifact_paths")
            if not isinstance(paths, list) or not paths or len(paths) > 20:
                raise ValueError("evaluator must provide 1-20 artifact paths")
            evidence = []
            for name in paths:
                if not isinstance(name, str) or not name or Path(name).is_absolute():
                    raise ValueError("evaluator artifact path must be relative")
                artifact = (workdir / name).resolve()
                if not artifact.is_relative_to(workdir) or not artifact.is_file():
                    raise ValueError(f"evaluator artifact is missing or outside workdir: {name}")
                if artifact.stat().st_size > 10_000_000:
                    raise ValueError("evaluator artifact exceeds 10 MB")
                content = artifact.read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                destination = self.evidence_root / digest[:2] / digest
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    with NamedTemporaryFile("wb", dir=destination.parent, delete=False) as output:
                        output.write(content)
                        staged = Path(output.name)
                    staged.replace(destination)
                evidence.append({"sha256": digest, "path": str(destination), "bytes": len(content)})
            return {"score": float(score), "evidence": evidence}
