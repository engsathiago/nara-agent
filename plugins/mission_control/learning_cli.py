"""Operator commands for procedural learning and transfer evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from nara_constants import get_nara_home
from plugins.memory import import_provider_module
from plugins.mission_control.consolidation import MissionConsolidator, learning_status_tool
from plugins.mission_control.learning import LearningLab
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_runner import ProcessEvaluator
from plugins.mission_control.store import MissionStore
from plugins.mission_control.learning_fabric_cli import media_command


def register_learning_cli(actions: Any) -> None:
    learn_extract = actions.add_parser(
        "learn-extract", help="Create an inactive procedural candidate from a verified mission")
    learn_extract.add_argument("mission_id")
    learn_extract.add_argument("--name")

    learn_show = actions.add_parser(
        "learn-show", help="Inspect a procedural candidate and its reserved-transfer eval")
    learn_show.add_argument("candidate_id")

    learn_evaluate = actions.add_parser(
        "learn-evaluate", help="Run reserved transfer cases with an executable evaluator")
    learn_evaluate.add_argument("candidate_id")
    learn_evaluate.add_argument("--cases-file", type=Path, required=True)
    learn_evaluate.add_argument("--evaluator", type=Path, required=True)
    learn_evaluate.add_argument("--development-case", action="append", required=True)
    learn_evaluate.add_argument("--timeout", type=float, default=30.0)

    learn_promote = actions.add_parser(
        "learn-promote", help="Promote only a candidate whose reserved-transfer eval passed")
    learn_promote.add_argument("candidate_id")

    learn_rollback = actions.add_parser(
        "learn-rollback", help="Disable a promoted learned skill and reject its active memory")
    learn_rollback.add_argument("candidate_id")

    consolidate = actions.add_parser(
        "learn-consolidate", help="Extract inactive candidates from newly verified missions")
    consolidate.add_argument("--limit", type=int, default=100)
    actions.add_parser("learn-status", help="Show learning consolidation health and pending missions")


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
    if args.mission_action == "learn-status":
        return learning_status_tool()
    lab = open_learning_lab(store)
    candidates = lab.candidate_root
    actions = {
        "learn-media-procedure": lambda: lab.propose_from_media(
            args.source_id, args.repo_claim, args.name, args.step, args.quote,
        ).to_dict(),
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


def open_learning_lab(store: MissionStore | None = None) -> LearningLab:
    store = store or MissionStore.open_default()
    home = get_nara_home()
    candidates = store.path.parent / "learning" / "candidates"
    provider_module = import_provider_module("nara_temporal")
    return LearningLab(
        store,
        provider_module.TemporalMemoryStore(home / "memories" / "nara-temporal.db"),
        candidates,
        home / "skills",
        source_fabric=LearningFabric.open_default(),
    )


def dispatch_learning(store: MissionStore, args: argparse.Namespace, *, llm: Any = None) -> dict[str, Any]:
    if args.mission_action == "learn-media-study":
        from plugins.mission_control.learning_study import study_media

        return study_media(open_learning_lab(store), llm, args.source_id, args.objective,
                           repository_claim_id=args.repo_claim)
    if args.mission_action == "learn-media-procedure":
        return learning_command(store, args)
    if args.mission_action.startswith(("learn-media-", "learn-repo-")):
        return media_command(args)
    return learning_command(store, args)
