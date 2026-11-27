"""Process exclusion and byte-verified study checkpoints."""

from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3


class StudyBusyError(ValueError):
    """A live executor owns the study lock; this is not a failed experiment."""


@contextmanager
def study_lock(root: Path, plan_id: str):
    # A separate SQLite file provides an OS-released, cross-process lock without
    # holding the competence database's writer lock during inference. Never unlink
    # it: another process may already have its inode open.
    directory = root / "study-locks"
    directory.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(plan_id.encode()).hexdigest() + ".sqlite"
    with closing(sqlite3.connect(directory / name, timeout=0, isolation_level=None)) as conn:
        try:
            conn.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            if exc.sqlite_errorcode in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise StudyBusyError("this study plan is already executing in another process") from exc
            raise
        try:
            yield
        finally:
            conn.rollback()


def read_checkpoint(reference):
    path = Path(reference["path"])
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != reference["sha256"]:
        raise ValueError("study checkpoint is missing or changed")
    return json.loads(content.decode("utf-8-sig"))


def verify_evaluator_result(result):
    for artifact in result["evidence"]:
        path = Path(artifact["path"])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError("study evaluator evidence is missing or changed")
    return result


def initial_result(cycle_id, plan_id, source_id, request_path, request_hash):
    return {
        "kind": "study_cycle_result", "schema_version": 2, "checkpoint_version": 1,
        "cycle_id": cycle_id, "plan_id": plan_id, "source_id": source_id,
        "request_sha256": request_hash, "request_path": str(request_path),
        "attempts": [], "generation_calls_started": 0, "evaluator_calls_started": 0,
        "estimated_cost_usd": 0.0, "cost_unknown": False, "transfer": None,
        "evaluator_usage": [], "pending_call": None, "holdout_started": False,
        "transfer_proof": None, "resume_count": 0,
    }
