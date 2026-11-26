"""Observed system competence, gap queue, and leakage-safe study evaluation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from nara_cli.sqlite_util import open_db, transaction
from plugins.mission_control.contracts import utc_now
from plugins.mission_control.learning_acceptance import validate_minimum_score
from plugins.plugin_storage import plugin_data_dir


DB_SCHEMA_VERSION = 2
GAP_STATES = frozenset({"open", "studying", "practicing", "proving", "resolved", "unresolved"})


def default_competence_path() -> Path:
    return plugin_data_dir("mission-control") / "competence.db"


def _initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS competence_observations (
            observation_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            system_fingerprint TEXT NOT NULL,
            system_json TEXT NOT NULL,
            mission_id TEXT,
            task_id TEXT,
            score REAL NOT NULL,
            verified INTEGER NOT NULL,
            evidence_json TEXT NOT NULL,
            status TEXT NOT NULL,
            observed_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS competence_category_time
            ON competence_observations (category, observed_at, observation_id);
        CREATE TABLE IF NOT EXISTS competence_gaps (
            gap_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            impact INTEGER NOT NULL,
            budget_usd REAL,
            state TEXT NOT NULL,
            source_mission_id TEXT,
            source_task_id TEXT,
            evidence_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (category, source_mission_id, source_task_id, diagnosis)
        );
        CREATE INDEX IF NOT EXISTS competence_gap_queue
            ON competence_gaps (state, impact DESC, created_at);
        CREATE TABLE IF NOT EXISTS study_plans (
            plan_id TEXT PRIMARY KEY,
            gap_id TEXT NOT NULL,
            objective TEXT NOT NULL,
            sources_json TEXT NOT NULL,
            development_case_ids_json TEXT NOT NULL,
            holdout_case_ids_json TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (gap_id) REFERENCES competence_gaps(gap_id)
        );
        CREATE TABLE IF NOT EXISTS study_evaluations (
            evaluation_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            baseline_json TEXT NOT NULL,
            candidate_json TEXT NOT NULL,
            mean_delta REAL NOT NULL,
            regressions INTEGER NOT NULL,
            passed INTEGER NOT NULL,
            evidence_json TEXT NOT NULL,
            evaluated_at TEXT NOT NULL,
            FOREIGN KEY (plan_id) REFERENCES study_plans(plan_id)
        );
    """)
    # DDL and its version marker must survive or roll back together on interruption.
    conn.execute("BEGIN IMMEDIATE")
    current = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if current not in {0, 1, DB_SCHEMA_VERSION}:
        raise RuntimeError(f"unsupported System Competence schema {current}")
    if current < 2:
        conn.execute("ALTER TABLE study_plans ADD COLUMN minimum_candidate_score REAL NOT NULL DEFAULT 0")
    conn.execute(f"PRAGMA user_version={DB_SCHEMA_VERSION}")
    conn.commit()


def _canonical_system(system: dict[str, Any]) -> tuple[str, str]:
    normalized = json.dumps(system, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(normalized.encode()).hexdigest(), normalized


@dataclass(frozen=True)
class StudyPlan:
    plan_id: str
    gap_id: str
    objective: str
    sources: tuple[dict[str, str], ...]
    development_case_ids: tuple[str, ...]
    holdout_case_ids: tuple[str, ...]
    status: str
    created_at: str
    minimum_candidate_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CompetenceRegistry:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    @classmethod
    def open_default(cls) -> CompetenceRegistry:
        return cls(default_competence_path())

    def _connect(self) -> sqlite3.Connection:
        return open_db(
            self.path,
            db_label="plugin-data/mission-control/competence.db",
            foreign_keys=True,
            synchronous_full=True,
            initialize=_initialize,
        )

    def record_observation(
        self,
        category: str,
        system: dict[str, Any],
        score: float,
        *,
        verified: bool,
        evidence_artifact_ids: Iterable[str],
        mission_id: str | None = None,
        task_id: str | None = None,
        observation_id: str | None = None,
    ) -> dict[str, Any]:
        with transaction(self._connect(), immediate=True) as conn:
            identity = self._insert_observation(
                conn, category, system, score, verified=verified,
                evidence_artifact_ids=evidence_artifact_ids, mission_id=mission_id,
                task_id=task_id, observation_id=observation_id)
        return self.observation(identity)

    def _insert_observation(
        self, conn: sqlite3.Connection, category: str, system: dict[str, Any], score: float,
        *, verified: bool, evidence_artifact_ids: Iterable[str],
        mission_id: str | None = None, task_id: str | None = None,
        observation_id: str | None = None,
    ) -> str:
        if not category.strip():
            raise ValueError("competence category is required")
        if not 0.0 <= float(score) <= 1.0:
            raise ValueError("competence score must be between 0 and 1")
        evidence = tuple(sorted(set(evidence_artifact_ids)))
        if verified and not evidence:
            raise ValueError("verified competence requires evidence artifacts")
        fingerprint, encoded_system = _canonical_system(system)
        identity = observation_id or uuid.uuid4().hex
        status = "demonstrated" if verified and score >= 0.8 else "practicing"
        conn.execute(
            """INSERT OR IGNORE INTO competence_observations VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                identity, category.strip(), fingerprint, encoded_system, mission_id, task_id,
                float(score), int(verified), json.dumps(evidence), status, utc_now(),
            ),
        )
        return identity

    def observation(self, observation_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM competence_observations WHERE observation_id = ?",
                (observation_id,),
            ).fetchone()
        if row is None:
            raise KeyError(observation_id)
        return {
            **dict(row),
            "system": json.loads(row["system_json"]),
            "evidence_artifact_ids": json.loads(row["evidence_json"]),
            "verified": bool(row["verified"]),
        }

    def current(self, category: str | None = None) -> list[dict[str, Any]]:
        clause = "WHERE category = ?" if category else ""
        params = (category,) if category else ()
        with transaction(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT * FROM competence_observations {clause} ORDER BY observed_at DESC, observation_id",
                params,
            ).fetchall()
        grouped: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault((row["category"], row["system_fingerprint"]), []).append(row)
        result = []
        for (item_category, fingerprint), observations in grouped.items():
            verified = [row for row in observations if row["verified"]]
            scores = [float(row["score"]) for row in verified or observations]
            latest = observations[0]
            result.append({
                "category": item_category,
                "system_fingerprint": fingerprint,
                "system": json.loads(latest["system_json"]),
                "state": "demonstrated" if verified and max(scores) >= 0.8 else "practicing",
                "best_score": max(scores),
                "sample_count": len(observations),
                "verified_sample_count": len(verified),
                "latest_observed_at": latest["observed_at"],
            })
        return sorted(result, key=lambda item: (item["category"], -item["best_score"]))

    def assess(self, category: str, system: dict[str, Any]) -> dict[str, Any]:
        fingerprint, _ = _canonical_system(system)
        matches = [
            item for item in self.current(category)
            if item["system_fingerprint"] == fingerprint
        ]
        if matches:
            return {**matches[0], "alternatives": []}
        alternatives = [
            {**item, "state": "outdated"} for item in self.current(category)
        ]
        return {
            "category": category,
            "system_fingerprint": fingerprint,
            "system": system,
            "state": "untested",
            "best_score": None,
            "sample_count": 0,
            "verified_sample_count": 0,
            "alternatives": alternatives,
        }

    def record_gap(
        self,
        category: str,
        title: str,
        diagnosis: str,
        *,
        impact: int,
        budget_usd: float | None = None,
        source_mission_id: str | None = None,
        source_task_id: str | None = None,
        evidence_artifact_ids: Iterable[str] = (),
    ) -> dict[str, Any]:
        if not 1 <= int(impact) <= 5:
            raise ValueError("gap impact must be from 1 to 5")
        created_at = utc_now()
        signature = hashlib.sha256(json.dumps(
            [category, source_mission_id, source_task_id, diagnosis],
            ensure_ascii=False,
        ).encode()).hexdigest()[:24]
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO competence_gaps VALUES (
                    ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?
                )""",
                (
                    signature, category.strip(), title.strip(), diagnosis.strip(), int(impact),
                    budget_usd, source_mission_id, source_task_id,
                    json.dumps(sorted(set(evidence_artifact_ids))), created_at, created_at,
                ),
            )
        return self.gap(signature)

    def gap(self, gap_id: str) -> dict[str, Any]:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM competence_gaps WHERE gap_id = ?", (gap_id,)).fetchone()
        if row is None:
            raise KeyError(gap_id)
        return {**dict(row), "evidence_artifact_ids": json.loads(row["evidence_json"])}

    def gaps(self, state: str | None = None) -> list[dict[str, Any]]:
        if state and state not in GAP_STATES:
            raise ValueError(f"unknown gap state: {state}")
        clause = "WHERE state = ?" if state else ""
        params = (state,) if state else ()
        with transaction(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT gap_id FROM competence_gaps {clause} ORDER BY impact DESC, created_at",
                params,
            ).fetchall()
        return [self.gap(row["gap_id"]) for row in rows]

    def transition_gap(self, gap_id: str, state: str) -> dict[str, Any]:
        if state not in GAP_STATES:
            raise ValueError(f"unknown gap state: {state}")
        with transaction(self._connect(), immediate=True) as conn:
            result = conn.execute(
                "UPDATE competence_gaps SET state = ?, updated_at = ? WHERE gap_id = ?",
                (state, utc_now(), gap_id),
            )
            if result.rowcount != 1:
                raise KeyError(gap_id)
        return self.gap(gap_id)

    def create_study_plan(
        self,
        gap_id: str,
        objective: str,
        *,
        sources: Iterable[dict[str, str]],
        development_case_ids: Iterable[str],
        holdout_case_ids: Iterable[str],
        plan_id: str | None = None,
        minimum_candidate_score: float = 0.8,
    ) -> StudyPlan:
        minimum = validate_minimum_score(minimum_candidate_score)
        self.gap(gap_id)
        source_list = tuple(sources)
        development = tuple(dict.fromkeys(str(item) for item in development_case_ids))
        holdout = tuple(dict.fromkeys(str(item) for item in holdout_case_ids))
        if not source_list or any(not item.get("uri") or not item.get("version") for item in source_list):
            raise ValueError("study plan requires versioned source URIs")
        if not development or not holdout:
            raise ValueError("study plan requires separate development and holdout cases")
        if set(development) & set(holdout):
            raise ValueError("development and holdout cases must not overlap")
        identity = plan_id or uuid.uuid4().hex
        created_at = utc_now()
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT INTO study_plans VALUES (?, ?, ?, ?, ?, ?, 'studying', ?, ?)",
                (
                    identity, gap_id, objective.strip(),
                    json.dumps(source_list, sort_keys=True), json.dumps(development),
                    json.dumps(holdout), created_at, minimum,
                ),
            )
        self.transition_gap(gap_id, "studying")
        return self.study_plan(identity)

    def study_plan(self, plan_id: str) -> StudyPlan:
        with transaction(self._connect()) as conn:
            row = conn.execute("SELECT * FROM study_plans WHERE plan_id = ?", (plan_id,)).fetchone()
        if row is None:
            raise KeyError(plan_id)
        return StudyPlan(
            plan_id=row["plan_id"], gap_id=row["gap_id"], objective=row["objective"],
            sources=tuple(json.loads(row["sources_json"])),
            development_case_ids=tuple(json.loads(row["development_case_ids_json"])),
            holdout_case_ids=tuple(json.loads(row["holdout_case_ids_json"])),
            status=row["status"], created_at=row["created_at"],
            minimum_candidate_score=row["minimum_candidate_score"],
        )

    def evaluate_study(
        self,
        plan_id: str,
        *,
        baseline_scores: dict[str, float],
        candidate_scores: dict[str, float],
        system: dict[str, Any],
        evidence_artifact_ids: Iterable[str],
        mission_id: str | None = None,
    ) -> dict[str, Any]:
        plan = self.study_plan(plan_id)
        holdout = set(plan.holdout_case_ids)
        if set(baseline_scores) != holdout or set(candidate_scores) != holdout:
            raise ValueError("study evaluation must contain exactly the reserved holdout cases")
        evidence = tuple(sorted(set(evidence_artifact_ids)))
        if not evidence:
            raise ValueError("study evaluation requires independently inspectable evidence")
        rows = []
        for case_id in plan.holdout_case_ids:
            baseline = float(baseline_scores[case_id])
            candidate = float(candidate_scores[case_id])
            if not 0 <= baseline <= 1 or not 0 <= candidate <= 1:
                raise ValueError("study scores must be between 0 and 1")
            rows.append({
                "case_id": case_id, "baseline": baseline, "candidate": candidate,
                "delta": candidate - baseline,
            })
        mean_delta = sum(item["delta"] for item in rows) / len(rows)
        regressions = sum(item["delta"] < 0 for item in rows)
        below_minimum = [row["case_id"] for row in rows
                         if row["candidate"] < plan.minimum_candidate_score]
        passed = mean_delta > 0 and regressions == 0 and not below_minimum
        evaluation_id = hashlib.sha256(json.dumps(
            [plan_id, rows, evidence, system], sort_keys=True).encode()).hexdigest()[:24]
        gap = self.gap(plan.gap_id)
        observation_id = None
        average = sum(row["candidate"] for row in rows) / len(rows)
        gap_state = "unresolved"
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO study_evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    evaluation_id, plan_id, json.dumps(baseline_scores, sort_keys=True),
                    json.dumps(candidate_scores, sort_keys=True), mean_delta, regressions,
                    int(passed), json.dumps(evidence), utc_now(),
                ),
            )
            conn.execute(
                "UPDATE study_plans SET status = ? WHERE plan_id = ?",
                ("passed" if passed else "failed", plan_id),
            )
            if passed:
                observation_id = self._insert_observation(
                    conn, gap["category"], system, average, verified=True,
                    evidence_artifact_ids=evidence, mission_id=mission_id,
                    observation_id=f"study:{evaluation_id}")
                gap_state = "resolved" if average >= 0.8 else "practicing"
            conn.execute("UPDATE competence_gaps SET state = ?, updated_at = ? WHERE gap_id = ?",
                         (gap_state, utc_now(), plan.gap_id))
        observation = self.observation(observation_id) if observation_id else None
        return {
            "evaluation_id": evaluation_id, "plan_id": plan_id, "gap_id": plan.gap_id,
            "passed": passed, "mean_delta": mean_delta, "regressions": regressions,
            "minimum_candidate_score": plan.minimum_candidate_score,
            "below_minimum": below_minimum,
            "cases": rows, "observation": observation,
        }

    def mark_study_execution(self, plan_id: str, *, failed: bool = False) -> None:
        """Make pending or interrupted executions visible without inventing a score."""
        plan = self.study_plan(plan_id)
        with transaction(self._connect(), immediate=True) as conn:
            conn.execute("UPDATE study_plans SET status = ? WHERE plan_id = ?",
                         ("failed" if failed else "proving", plan_id))
            conn.execute("UPDATE competence_gaps SET state = ?, updated_at = ? WHERE gap_id = ?",
                         ("unresolved" if failed else "proving", utc_now(), plan.gap_id))


COMPETENCE_STATUS_SCHEMA = {
    "name": "nara_competence_status",
    "description": "Inspect demonstrated Nara system competence and the prioritized gap queue.",
    "parameters": {"type": "object", "properties": {
        "category": {"type": "string"}, "gap_state": {"type": "string", "enum": sorted(GAP_STATES)},
    }},
}

GAP_RECORD_SCHEMA = {
    "name": "nara_gap_record",
    "description": "Record an observed capability failure as a durable study gap; never claim success.",
    "parameters": {"type": "object", "properties": {
        "category": {"type": "string"}, "title": {"type": "string"},
        "diagnosis": {"type": "string"}, "impact": {"type": "integer", "minimum": 1, "maximum": 5},
        "mission_id": {"type": "string"}, "task_id": {"type": "string"},
    }, "required": ["category", "title", "diagnosis", "impact"]},
}


def competence_status_tool(category: str = "", gap_state: str = "", **_: Any) -> dict[str, Any]:
    registry = CompetenceRegistry.open_default()
    return {
        "competencies": registry.current(category or None),
        "gaps": registry.gaps(gap_state or None),
    }


def gap_record_tool(
    category: str, title: str, diagnosis: str, impact: int,
    mission_id: str = "", task_id: str = "", **_: Any,
) -> dict[str, Any]:
    return CompetenceRegistry.open_default().record_gap(
        category, title, diagnosis, impact=impact,
        source_mission_id=mission_id or None, source_task_id=task_id or None,
    )
