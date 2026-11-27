"""Owned child for crash/restart tests; the model is deterministic and offline."""

import json
from pathlib import Path
import sys
import threading

from plugins.mission_control import register
from plugins.mission_control.cli import register_cli
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.study_cycle import StudyCycle
from tests.plugins.mission_control.test_learning_study import _model, _valid
from tests.plugins.mission_control.test_plugin import _Context


def main():
    import argparse

    argv = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    stage, marker = sys.argv[2], Path(sys.argv[3])

    def stop():
        marker.write_text(stage, encoding="utf-8")
        threading.Event().wait(60)  # health: allow HX013 -- Deliberate crash-test hang; parent kills this owned worker at its durable checkpoint, timeout is a watchdog.
        raise RuntimeError("parent did not terminate the owned worker")

    original = StudyCycle._progress

    def progress(self, status):
        original(self, status)
        pending = self.result.get("pending_call") or {}
        if stage == "practice-result" and status == "practicing" and pending.get("observed_result"):
            stop()
        if stage == "holdout-result" and status == "proving" and pending.get("observed_result"):
            stop()
        if stage == "holdout-complete" and status == "proving" and pending.get("observed_result") and pending.get("candidate_id"):
            stop()
        if stage == "unknown-evaluator" and pending.get("kind") == "evaluator" and not pending.get("observed_result"):
            stop()

    StudyCycle._progress = progress
    evaluate = CompetenceRegistry.evaluate_study

    def record(self, *args, **kwargs):
        result = evaluate(self, *args, **kwargs)
        if stage == "competence-recorded":
            stop()
        return result

    CompetenceRegistry.evaluate_study = record
    ctx = _Context()
    ctx.llm = _model(_valid(), [], stop if stage == "generation" else lambda: None)
    register(ctx)
    parser = argparse.ArgumentParser()
    register_cli(parser)
    raise SystemExit(ctx.command["handler_fn"](parser.parse_args(argv)))


if __name__ == "__main__":
    main()
