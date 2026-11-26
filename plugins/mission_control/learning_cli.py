"""Operator commands for procedural learning and transfer evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from nara_constants import get_nara_home
from plugins.memory import import_provider_module
from plugins.mission_control.consolidation import MissionConsolidator
from plugins.mission_control.learning import LearningLab
from plugins.mission_control.learning_runner import ProcessEvaluator
from plugins.mission_control.store import MissionStore


def _show(lab: LearningLab, args: argparse.Namespace, candidates: Path) -> dict[str, Any]:
    payload = lab.load(args.candidate_id).to_dict()
    eval_path = candidates / f"{args.candidate_id}.eval.json"
    payload["evaluation"] = (
        json.loads(eval_path.read_text(encoding="utf-8-sig")) if eval_path.exists() else None
    )
    return payload


def _evaluate(lab: LearningLab, args: argparse.Namespace, candidates: Path) -> dict[str, Any]:
    cases = json.loads(args.cases_file.read_text(encoding="utf-8-sig"))
    if isinstance(cases, dict):
        cases = cases.get("cases")
    if not isinstance(cases, list) or any(
        not isinstance(case, dict) or not case.get("case_id") for case in cases
    ):
        raise ValueError("cases file must contain cases with unique case_id values")
    ids = [str(case["case_id"]) for case in cases]
    if len(ids) != len(set(ids)) or not set(args.development_case) <= set(ids):
        raise ValueError("case ids must be unique and development cases must exist")
    evaluator = ProcessEvaluator(args.evaluator, candidates / "evidence", timeout=args.timeout)
    return lab.evaluate_transfer(
        args.candidate_id, cases, evaluator,
        development_case_ids=set(args.development_case),
        evaluator_sha256=evaluator.sha256,
        evaluator_path=str(evaluator.archived_path),
    )


def learning_command(store: MissionStore, args: argparse.Namespace) -> dict[str, Any]:
    home = get_nara_home()
    candidates = store.path.parent / "learning" / "candidates"
    provider_module = import_provider_module("nara_temporal")
    lab = LearningLab(
        store,
        provider_module.TemporalMemoryStore(home / "memories" / "nara-temporal.db"),
        candidates,
        home / "skills",
    )
    actions = {
        "learn-extract": lambda: lab.extract(args.mission_id, name=args.name).to_dict(),
        "learn-show": lambda: _show(lab, args, candidates),
        "learn-evaluate": lambda: _evaluate(lab, args, candidates),
        "learn-promote": lambda: {
            "skill_path": str(lab.promote(args.candidate_id, require_evidence=True)),
            "status": "promoted",
        },
        "learn-rollback": lambda: {
            "skill_path": str(lab.rollback(args.candidate_id)),
            "status": "rolled_back",
        },
        "learn-consolidate": lambda: MissionConsolidator(
            store, lab, store.path.parent / "learning" / "consolidation.db"
        ).run_once(limit=args.limit),
    }
    return actions[args.mission_action]()
