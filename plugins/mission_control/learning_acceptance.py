"""Declared acceptance floors for procedural transfer evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_minimum_score(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("minimum candidate score must be a finite number from 0 to 1")
    return float(value)


def check_minimum_score(report: dict[str, Any]) -> None:
    """Recheck case results rather than trusting the report's aggregate pass flag."""
    minimum = validate_minimum_score(report.get("minimum_candidate_score", 0.0))
    if minimum == 0.0:
        return  # Legacy reports declare relative improvement only.
    cases = report.get("cases") or []
    if not cases:
        raise ValueError("minimum candidate score requires reserved case results")
    for row in cases:
        score = row.get("candidate")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not minimum <= score <= 1:
            raise ValueError("candidate did not meet the declared minimum score on every reserved case")


def check_evaluation_request(report: dict[str, Any], request_path: Path) -> None:
    if not request_path.exists():
        if report.get("evaluation_request_id"):
            raise ValueError("latest evaluation request is missing")
        return  # Historical reports predate durable requests.
    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    fields = ("evaluation_request_id", "candidate_id", "candidate_hash", "minimum_candidate_score",
              "evaluator_sha256", "development_case_ids", "holdout_case_ids")
    if any(request.get(key) != report.get(key) for key in fields):
        raise ValueError("latest evaluation is incomplete or differs from its declared request")
