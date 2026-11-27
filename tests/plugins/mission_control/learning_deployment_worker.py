"""Owned crash probe: the parent terminates this process at a publication boundary."""

import argparse
from pathlib import Path
import sys
import threading

from plugins.mission_control import learning_deployment
from plugins.mission_control.cli import mission_command, register_cli
from plugins.mission_control.learning_cli import open_learning_lab


def main():
    identity, stage, marker = sys.argv[1:]
    lab = open_learning_lab()
    memory_class = type(lab.memory)

    def pause():
        Path(marker).write_text(stage, encoding="utf-8")
        # health: allow HX013 -- Intentional owned-process crash boundary; parent kills and joins, watchdog exits after 60s.
        threading.Event().wait(60)
        raise SystemExit("crash-probe watchdog elapsed")

    if stage == "memory-promoted":
        original = memory_class.promote

        def promoted(self, memory_id):
            result = original(self, memory_id)
            pause()
            return result

        memory_class.promote = promoted
    elif stage == "skill-published":
        original = learning_deployment._publish

        def published(destination, content):
            original(destination, content)
            pause()

        learning_deployment._publish = published
    elif stage == "skill-removed":
        original = memory_class.reject

        def removed(self, memory_id):
            pause()
            return original(self, memory_id)

        memory_class.reject = removed
    else:
        raise ValueError("unknown crash stage")
    parser = argparse.ArgumentParser()
    register_cli(parser)
    action = "learn-rollback" if stage == "skill-removed" else "learn-promote"
    raise SystemExit(mission_command(parser.parse_args([action, identity])))


if __name__ == "__main__":
    main()
