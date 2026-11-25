"""Narrow bridge from vendored Nara gates to Nara's one policy."""

from __future__ import annotations

from typing import Any, Optional


def nara_authorization_override(
    capability: str, target: Any = "", **context: Any,
) -> Optional[dict[str, Any]]:
    """Return an explicit Nara decision, or ``None`` when it delegates."""

    from nara_agent.nara_security import authorize

    decision = authorize(capability, target, **context)
    if decision.allowed is None:
        return None
    return {
        "allowed": bool(decision.allowed),
        "reason": decision.reason,
        "mode": decision.mode,
        "rule_id": decision.rule_id,
    }


def nara_approval_override(
    capability: str, target: Any = "", **context: Any,
) -> Optional[dict[str, Any]]:
    """Return the standard result shape expected by approval gates."""

    decision = nara_authorization_override(capability, target, **context)
    if decision is None:
        return None
    allowed = bool(decision["allowed"])
    return {
        "approved": allowed,
        "message": None if allowed else f"BLOCKED by Nara policy: {decision['reason']}",
        "nara_policy": True,
        "nara_mode": decision.get("mode"),
        "rule_id": decision.get("rule_id"),
    }
