"""Versioned Evolution Lab with frozen gates, canaries, session pins, and rollback."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import utc_now
from plugins.mission_control.ledger import ExperienceLedger
from plugins.plugin_storage import plugin_data_dir


VARIANT_KINDS = frozenset({"skill", "prompt", "router", "tool", "plugin", "code"})


def default_evolution_root() -> Path:
    return plugin_data_dir("mission-control") / "evolution"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
            baseline_variant_id TEXT, development_json TEXT NOT NULL, holdout_json TEXT NOT NULL,
            min_mean_delta REAL NOT NULL, max_regressions INTEGER NOT NULL,
            max_cost_usd REAL, status TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS variants (
            variant_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, version INTEGER NOT NULL,
            content_hash TEXT NOT NULL, content_path TEXT NOT NULL, metadata_json TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id),
            UNIQUE (experiment_id, version)
        );
        CREATE TABLE IF NOT EXISTS evolution_evaluations (
            evaluation_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, variant_id TEXT NOT NULL,
            evaluated_hash TEXT NOT NULL, baseline_json TEXT NOT NULL, candidate_json TEXT NOT NULL,
            mean_delta REAL NOT NULL, regressions INTEGER NOT NULL, cost_usd REAL NOT NULL,
            evidence_json TEXT NOT NULL, passed INTEGER NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deployments (
            deployment_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, variant_id TEXT NOT NULL,
            stage TEXT NOT NULL, previous_variant_id TEXT, status TEXT NOT NULL,
            reason TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS session_variant_pins (
            session_id TEXT NOT NULL, experiment_id TEXT NOT NULL, variant_id TEXT NOT NULL,
            pinned_at TEXT NOT NULL, PRIMARY KEY (session_id, experiment_id)
        );
    """)
    conn.execute("PRAGMA user_version=1")
    conn.commit()


class EvolutionLab:
    def __init__(self, root: Path | str, ledger: ExperienceLedger | None = None):
        self.root = Path(root)
        self.db_path = self.root / "evolution.db"
        self.ledger = ledger

    @classmethod
    def open_default(cls) -> EvolutionLab:
        return cls(default_evolution_root(), ExperienceLedger.open_default())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.db_path, db_label="plugin-data/mission-control/evolution/evolution.db",
            foreign_keys=True, synchronous_full=True, initialize=_initialize)

    def _write_blob(self, content: bytes) -> tuple[str, Path]:
        digest = hashlib.sha256(content).hexdigest()
        destination = self.root / "variants" / digest[:2] / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            with NamedTemporaryFile("wb", dir=destination.parent, delete=False) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            temporary.replace(destination)
        return digest, destination

    def create_experiment(
        self, name: str, kind: str, *, development_case_ids: list[str],
        holdout_case_ids: list[str], min_mean_delta: float = 0.01,
        max_regressions: int = 0, max_cost_usd: float | None = None,
        experiment_id: str | None = None,
    ) -> dict[str, Any]:
        if kind not in VARIANT_KINDS:
            raise ValueError(f"unsupported evolution kind: {kind}")
        if not development_case_ids or not holdout_case_ids:
            raise ValueError("evolution requires development and holdout cases")
        if set(development_case_ids) & set(holdout_case_ids):
            raise ValueError("development and holdout cases must not overlap")
        identity = experiment_id or uuid.uuid4().hex
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT INTO experiments VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 'open', ?)",
                (identity, name, kind, json.dumps(development_case_ids), json.dumps(holdout_case_ids),
                 float(min_mean_delta), int(max_regressions), max_cost_usd, utc_now()))
        return self.experiment(identity)

    def experiment(self, experiment_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,)).fetchone()
        if row is None:
            raise KeyError(experiment_id)
        return {
            **dict(row), "development_case_ids": json.loads(row["development_json"]),
            "holdout_case_ids": json.loads(row["holdout_json"]),
        }

    def register_variant(
        self, experiment_id: str, content: bytes | str, *, metadata: dict[str, Any] | None = None,
        baseline: bool = False,
    ) -> dict[str, Any]:
        self.experiment(experiment_id)
        raw = content.encode() if isinstance(content, str) else content
        digest, path = self._write_blob(raw)
        with transaction(self._connect(), immediate=True) as conn:
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM variants WHERE experiment_id = ?",
                (experiment_id,)).fetchone()[0])
            identity = f"{experiment_id}:v{version}:{digest[:12]}"
            status = "baseline" if baseline else "candidate"
            conn.execute(
                "INSERT INTO variants VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (identity, experiment_id, version, digest, str(path),
                 json.dumps(metadata or {}, sort_keys=True), status, utc_now()))
            if baseline:
                conn.execute(
                    "UPDATE experiments SET baseline_variant_id = ? WHERE experiment_id = ?",
                    (identity, experiment_id))
                conn.execute(
                    "INSERT INTO deployments VALUES (?, ?, ?, 'active', NULL, 'active', 'baseline', ?)",
                    (uuid.uuid4().hex, experiment_id, identity, utc_now()))
        return self.variant(identity)

    def variant(self, variant_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM variants WHERE variant_id = ?", (variant_id,)).fetchone()
        if row is None:
            raise KeyError(variant_id)
        return {**dict(row), "metadata": json.loads(row["metadata_json"])}

    def reload_variant(self, variant_id: str) -> bytes:
        variant = self.variant(variant_id)
        content = Path(variant["content_path"]).read_bytes()
        observed = hashlib.sha256(content).hexdigest()
        if observed != variant["content_hash"]:
            raise RuntimeError(f"variant identity mismatch: expected {variant['content_hash']}, got {observed}")
        return content

    def evaluate(
        self, experiment_id: str, variant_id: str, *, baseline_scores: dict[str, float],
        candidate_scores: dict[str, float], evidence_artifact_ids: list[str], cost_usd: float = 0.0,
    ) -> dict[str, Any]:
        experiment = self.experiment(experiment_id)
        variant = self.variant(variant_id)
        if variant["experiment_id"] != experiment_id:
            raise ValueError("variant belongs to another experiment")
        holdout = set(experiment["holdout_case_ids"])
        if set(baseline_scores) != holdout or set(candidate_scores) != holdout:
            raise ValueError("evaluation must contain exactly the frozen holdout")
        if not evidence_artifact_ids:
            raise ValueError("evolution evaluation requires evidence artifacts")
        evaluated_hash = hashlib.sha256(self.reload_variant(variant_id)).hexdigest()
        deltas = [candidate_scores[key] - baseline_scores[key] for key in experiment["holdout_case_ids"]]
        mean_delta = sum(deltas) / len(deltas)
        regressions = sum(delta < 0 for delta in deltas)
        within_cost = experiment["max_cost_usd"] is None or cost_usd <= experiment["max_cost_usd"]
        passed = (
            evaluated_hash == variant["content_hash"]
            and mean_delta >= experiment["min_mean_delta"]
            and regressions <= experiment["max_regressions"]
            and within_cost
        )
        identity = hashlib.sha256(json.dumps(
            [experiment_id, variant_id, baseline_scores, candidate_scores, evidence_artifact_ids],
            sort_keys=True).encode()).hexdigest()[:24]
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO evolution_evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (identity, experiment_id, variant_id, evaluated_hash,
                 json.dumps(baseline_scores, sort_keys=True), json.dumps(candidate_scores, sort_keys=True),
                 mean_delta, regressions, float(cost_usd), json.dumps(evidence_artifact_ids),
                 int(passed), utc_now()))
            conn.execute(
                "UPDATE variants SET status = ? WHERE variant_id = ?",
                ("evaluated_pass" if passed else "evaluated_fail", variant_id))
        if self.ledger:
            self.ledger.record(
                kind="evolution.evaluated", status="passed" if passed else "failed",
                cost_usd=cost_usd, payload={
                    "experiment_id": experiment_id, "variant_id": variant_id,
                    "mean_delta": mean_delta, "regressions": regressions,
                    "evaluated_hash": evaluated_hash,
                })
        return {
            "evaluation_id": identity, "passed": passed, "mean_delta": mean_delta,
            "regressions": regressions, "evaluated_hash": evaluated_hash,
            "cost_usd": cost_usd,
        }

    def _latest_passed(self, variant_id: str) -> bool:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT passed FROM evolution_evaluations WHERE variant_id = ? ORDER BY created_at DESC LIMIT 1",
                (variant_id,)).fetchone()
        return bool(row and row["passed"])

    def active_variant(self, experiment_id: str) -> str | None:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                """SELECT variant_id FROM deployments WHERE experiment_id = ? AND status = 'active' AND stage = 'active'
                   ORDER BY created_at DESC LIMIT 1""", (experiment_id,)).fetchone()
        return str(row["variant_id"]) if row else None

    def promote_canary(self, experiment_id: str, variant_id: str) -> dict[str, Any]:
        if not self._latest_passed(variant_id):
            raise ValueError("only an evaluated passing variant can enter canary")
        # Re-read immediately before promotion to prove exported identity.
        self.reload_variant(variant_id)
        previous = self.active_variant(experiment_id)
        identity = uuid.uuid4().hex
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT INTO deployments VALUES (?, ?, ?, 'canary', ?, 'active', NULL, ?)",
                (identity, experiment_id, variant_id, previous, utc_now()))
            conn.execute("UPDATE variants SET status = 'canary' WHERE variant_id = ?", (variant_id,))
        return self.deployment(identity)

    def activate(self, deployment_id: str) -> dict[str, Any]:
        deployment = self.deployment(deployment_id)
        if deployment["stage"] != "canary" or deployment["status"] != "active":
            raise ValueError("deployment is not an active canary")
        self.reload_variant(deployment["variant_id"])
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "UPDATE deployments SET status = 'superseded' WHERE experiment_id = ? AND status = 'active' AND deployment_id != ?",
                (deployment["experiment_id"], deployment_id))
            conn.execute("UPDATE deployments SET stage = 'active' WHERE deployment_id = ?", (deployment_id,))
            conn.execute("UPDATE variants SET status = 'active' WHERE variant_id = ?", (deployment["variant_id"],))
        return self.deployment(deployment_id)

    def deployment(self, deployment_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM deployments WHERE deployment_id = ?", (deployment_id,)).fetchone()
        if row is None:
            raise KeyError(deployment_id)
        return dict(row)

    def rollback(self, deployment_id: str, reason: str) -> dict[str, Any]:
        deployment = self.deployment(deployment_id)
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "UPDATE deployments SET status = 'rolled_back', reason = ? WHERE deployment_id = ?",
                (reason, deployment_id))
            conn.execute("UPDATE variants SET status = 'rolled_back' WHERE variant_id = ?", (deployment["variant_id"],))
            if deployment["previous_variant_id"]:
                restore_id = uuid.uuid4().hex
                conn.execute(
                    "INSERT INTO deployments VALUES (?, ?, ?, 'active', ?, 'active', ?, ?)",
                    (restore_id, deployment["experiment_id"], deployment["previous_variant_id"],
                     deployment["variant_id"], f"rollback:{reason}", utc_now()))
        return {"rolled_back": deployment["variant_id"], "restored": deployment["previous_variant_id"], "reason": reason}

    def pin_session(self, session_id: str, experiment_id: str) -> str:
        with transaction(self._connect()) as conn:
            existing = conn.execute(
                "SELECT variant_id FROM session_variant_pins WHERE session_id = ? AND experiment_id = ?",
                (session_id, experiment_id)).fetchone()
            if existing:
                return str(existing["variant_id"])
        active = self.active_variant(experiment_id)
        if active is None:
            active = self.experiment(experiment_id)["baseline_variant_id"]
        if active is None:
            raise ValueError("experiment has no baseline or active variant")
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO session_variant_pins VALUES (?, ?, ?, ?)",
                (session_id, experiment_id, active, utc_now()))
            pinned = conn.execute(
                "SELECT variant_id FROM session_variant_pins WHERE session_id = ? AND experiment_id = ?",
                (session_id, experiment_id)).fetchone()
        return str(pinned["variant_id"])

    def status(self, experiment_id: str | None = None) -> dict[str, Any]:
        clause = "WHERE experiment_id = ?" if experiment_id else ""
        params = (experiment_id,) if experiment_id else ()
        with transaction(self._connect()) as conn:
            experiments = [dict(row) for row in conn.execute(
                f"SELECT * FROM experiments {clause} ORDER BY created_at", params).fetchall()]
            deployments = [dict(row) for row in conn.execute(
                f"SELECT * FROM deployments {clause} ORDER BY created_at", params).fetchall()]
        return {"experiments": experiments, "deployments": deployments}


EVOLUTION_STATUS_SCHEMA = {
    "name": "nara_evolution_status",
    "description": "Inspect evaluated variants, canaries, active versions, and rollback history.",
    "parameters": {"type": "object", "properties": {"experiment_id": {"type": "string"}}},
}


def evolution_status_tool(experiment_id: str = "", **_: Any) -> dict[str, Any]:
    return EvolutionLab.open_default().status(experiment_id or None)
