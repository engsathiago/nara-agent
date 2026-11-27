"""Owned crash probe for native-skill admission; no external model or web access."""

import argparse
import json
from pathlib import Path
import sys
import threading

from plugins.mission_control import register
from plugins.mission_control.cli import register_cli
from plugins.mission_control.evolution import EvolutionLab
from plugins.mission_control.study_admission import StudyAdmission
from tests.plugins.mission_control.test_learning_study import _model
from tests.plugins.mission_control.test_plugin import _Context
from tests.plugins.mission_control.test_study_jobs import proposal


def main():
    stage, marker = sys.argv[1:]

    def pause():
        Path(marker).write_text(stage, encoding="utf-8")
        # health: allow HX013 -- Owned crash probe; the parent kills and joins this process, with a 60s watchdog.
        threading.Event().wait(60)
        raise SystemExit("admission crash watchdog elapsed")

    save = StudyAdmission._save

    def checkpoint(self):
        save(self)
        if ((stage == "pending" and self.state["pending_call"])
                or (stage == "observed" and len(self.state["observations"]) == 1)):
            pause()

    activate = EvolutionLab.activate

    def activated(self, deployment_id):
        result = activate(self, deployment_id)
        if stage == "activated":
            pause()
        return result

    StudyAdmission._save = checkpoint
    EvolutionLab.activate = activated
    ctx = _Context()
    ctx.llm = _model(proposal(), [])

    def dispatch(name, args):
        url = "https://docs.example.org/repository"
        if name == "web_search":
            return json.dumps({"success": True, "data": {"web": [{"url": url}]}})
        return json.dumps({"results": [{"url": url,
            "content": "Inspect the pinned commit in the repository before running unfamiliar code."}]})

    ctx.dispatch_tool = dispatch
    register(ctx)
    parser = argparse.ArgumentParser()
    register_cli(parser)
    raise SystemExit(ctx.command["handler_fn"](parser.parse_args(["study-work"])))


if __name__ == "__main__":
    main()
