"""Deterministic mission progress diagnosis and recovery recommendations."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.contracts import EffectStatus, MissionStatus, load_contract, utc_now
from plugins.mission_control.store import MissionNotFoundError, MissionStore


class MissionSupervisor:
    def __init__(self, missions: MissionStore, competence: CompetenceRegistry | None = None):
        self.missions = missions
        self.competence = competence

    def diagnose(
        self,
        mission_id: str,
        *,
        stale_after_seconds: int = 900,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        mission = self.missions.get(mission_id)
        if mission is None:
            raise MissionNotFoundError(mission_id)
        current = now or datetime.now(UTC)
        issues: list[dict[str, str]] = []
        for payload in mission.receipts.values():
            receipt = load_contract(payload)
            status = getattr(receipt, "effect_status", None)
            if status is EffectStatus.UNKNOWN:
                issues.append({
                    "code": "effect_unknown",
                    "subject": receipt.receipt_id,
                    "next_action": "query the destination and reconcile before retry",
                })
            elif status is EffectStatus.PENDING:
                issues.append({
                    "code": "effect_pending",
                    "subject": receipt.receipt_id,
                    "next_action": "inspect destination state; do not repeat blindly",
                })
        blocked_tasks = [task_id for task_id, status in mission.task_states.items() if status == "blocked"]
        for task_id in blocked_tasks:
            issues.append({
                "code": "task_blocked", "subject": task_id,
                "next_action": "inspect the Kanban block reason and replan or request input",
            })
        updated = datetime.fromisoformat(mission.updated_at)
        age = max(0, int((current - updated).total_seconds()))
        if (
            mission.status not in {MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED}
            and age >= stale_after_seconds
        ):
            issues.append({
                "code": "no_progress", "subject": mission.mission_id,
                "next_action": "resume the next runnable task or record an explicit blocker",
            })
        status = "healthy" if not issues else "attention"
        payload = {
            "diagnostic_id": hashlib.sha256(json.dumps(
                [mission.version, status, issues], sort_keys=True).encode()).hexdigest()[:24],
            "mission_id": mission_id,
            "status": status,
            "mission_version": mission.version,
            "observed_at": utc_now(),
            "age_seconds": age,
            "issues": issues,
        }
        self.missions.record_diagnostic(
            mission_id,
            payload,
            idempotency_key=f"diagnostic:{payload['diagnostic_id']}",
        )
        if self.competence is not None:
            for issue in issues:
                self.competence.record_gap(
                    f"mission.{issue['code']}",
                    f"Resolve {issue['code']} for {issue['subject']}",
                    issue["next_action"],
                    impact=4 if issue["code"] in {"effect_unknown", "task_blocked"} else 3,
                    source_mission_id=mission_id,
                    source_task_id=(issue["subject"] if issue["code"] == "task_blocked" else None),
                )
        return payload
