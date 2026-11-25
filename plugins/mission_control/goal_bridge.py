"""Project a mission completion contract into Nara's existing session goal."""

from __future__ import annotations

import time

from nara_cli.goals import GoalContract, GoalState, load_goal, save_goal
from plugins.mission_control.store import MissionNotFoundError, MissionStore, MissionStoreError


def bind_mission_goal(store: MissionStore, mission_id: str, session_id: str) -> GoalState:
    mission = store.get(mission_id)
    if mission is None:
        raise MissionNotFoundError(mission_id)
    if not session_id.strip():
        raise MissionStoreError("session_id is required to bind a mission goal")
    existing = load_goal(session_id)
    if existing is not None and existing.status == "active" and existing.goal != mission.objective:
        raise MissionStoreError("session already has a different active goal")
    state = existing or GoalState(
        goal=mission.objective,
        created_at=time.time(),
        contract=GoalContract(
            outcome=mission.objective,
            verification="Every mission completion criterion has independent PASS evidence.",
            constraints="Preserve confirmed effects and reconcile unknown effects before retrying.",
            boundaries=f"Mission {mission.mission_id} and its linked tasks and artifacts.",
            stop_when="A required external input or unavailable capability blocks observable progress.",
        ),
        subgoals=list(mission.completion_criteria),
    )
    save_goal(session_id, state)
    store.bind_goal(mission_id, {
        "session_id": session_id,
        "goal": state.goal,
        "criteria": list(mission.completion_criteria),
        "authority": "mission_control",
    })
    return state
