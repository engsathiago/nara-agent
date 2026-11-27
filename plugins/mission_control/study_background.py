"""Wake bounded profile-scoped study work without blocking gateway maintenance."""

from __future__ import annotations

from contextvars import copy_context
import json
import logging
from pathlib import Path
import threading
import time

from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.store import MissionStore
from plugins.mission_control.study_jobs import StudyJobs
from plugins.mission_control.study_checkpoint import StudyBusyError


class StudyBackground:
    def __init__(self, ctx):
        self.ctx = ctx
        self._lock = threading.Lock()
        self._threads = {}
        self._started = {}

    def wake(self):
        config = self.ctx.get_config("study_background", {})
        if not config.get("enabled", False):
            return {"state": "disabled"}
        interval = config.get("interval_seconds", 600)
        if not isinstance(interval, (int, float)) or not 60 <= interval <= 86400:
            raise ValueError("study background interval must be from 60 to 86400 seconds")
        key = str(MissionStore.open_default().path)
        with self._lock:
            thread = self._threads.get(key)
            if thread is not None and thread.is_alive():
                return {"state": "running"}
            now = time.monotonic()
            if now - self._started.get(key, -float("inf")) < interval:
                return {"state": "not_due"}
            context = copy_context()
            thread = threading.Thread(target=context.run, args=(self._run, config),
                                      name="nara-study-worker", daemon=True)
            self._threads[key], self._started[key] = thread, now
            thread.start()
            return {"state": "started"}

    def _run(self, config):
        logger = logging.getLogger(__name__)
        try:
            registry = CompetenceRegistry.open_default()
            jobs = StudyJobs(MissionStore.open_default(), registry, self.ctx.dispatch_tool, self.ctx.llm)
            pending = [job for job in jobs.jobs() if job.status in {"planned", "running", "verifying"}]
            if not pending:
                protocols = config.get("protocols", {})
                for gap in registry.gaps("open"):
                    if gap["category"] in protocols:
                        jobs.enqueue(gap["gap_id"], protocols[gap["category"]])
                        break
            report = jobs.run_once()
            if report["status"] != "idle":
                logger.info("Background study: %s", report)
        except StudyBusyError:
            logger.debug("Another executor owns the background study queue")
        except Exception:
            logger.exception("Background study failed; inspect study-jobs and the mission event log")


def register_job_cli(actions):
    command = actions.add_parser("study-enqueue", help="Freeze a study protocol and queue it as a durable mission")
    command.add_argument("gap_id")
    command.add_argument("--protocol-file", type=Path, required=True)
    actions.add_parser("study-work", help="Run or resume one pending study job")
    actions.add_parser("study-jobs", help="Inspect durable study jobs and their progress")


def job_command(store, args, dispatch, llm):
    jobs = StudyJobs(store, CompetenceRegistry.open_default(), dispatch, llm)
    if args.mission_action == "study-enqueue":
        return jobs.enqueue(args.gap_id, json.loads(args.protocol_file.read_text(encoding="utf-8-sig")))
    if args.mission_action == "study-work":
        return jobs.run_once()
    return [{"job_id": job.mission_id, "status": job.status, "gap_id": job.constraints["gap_id"],
             "progress": job.diagnostics.get("study_state")} for job in jobs.jobs()]
