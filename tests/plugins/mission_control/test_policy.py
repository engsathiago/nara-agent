from __future__ import annotations

from plugins.mission_control.policy import PolicyEngine


def _rules():
    return [
        {"rule_id": "confirm-write", "action_pattern": "write_*", "target_pattern": "*",
         "effect": "require_confirmation", "reason": "confirm writes", "priority": 10},
        {"rule_id": "deny-prod", "action_pattern": "deploy", "target_pattern": "*prod*",
         "effect": "deny", "reason": "production disabled", "priority": 5},
    ]


def test_default_is_observe_only_and_does_not_add_refusals(tmp_path):
    engine = PolicyEngine(tmp_path / "policy.db")
    decision = engine.decide("write_file", {"path": "/tmp/example"})

    assert engine.active()["mode"] == "observe_only"
    assert decision.effect == "allow"
    assert decision.would_effect == "allow"
    assert engine.guard_tool("write_file", {"path": "/tmp/example"}) is None


def test_versioned_enforcement_confirmation_explanation_and_rollback(tmp_path):
    engine = PolicyEngine(tmp_path / "policy.db")
    baseline = engine.active()["version_id"]
    staged = engine.stage("test rules", _rules())
    engine.promote(staged["version_id"])

    blocked = engine.guard_tool("write_file", {"path": "/tmp/example"}, actor_id="agent-a")
    decision_id = blocked["message"].split("Decision ", 1)[1].split(";", 1)[0]
    explanation = engine.decision(decision_id)
    assert explanation.effect == "require_confirmation"
    assert explanation.target_hash
    assert "/tmp/example" not in str(explanation.to_dict())

    engine.approve(decision_id, approved_by="owner")
    assert engine.guard_tool(
        "write_file", {"path": "/tmp/example"}, actor_id="agent-a") is None
    assert engine.guard_tool(
        "write_file", {"path": "/tmp/example"}, actor_id="agent-a") is not None
    assert "production disabled" in engine.guard_tool(
        "deploy", {"target": "production"})["message"]

    restored = engine.rollback()
    assert restored["version_id"] == baseline
    assert engine.guard_tool("deploy", {"target": "production"}) is None


def test_same_rule_is_consistent_across_surfaces_and_control_path_cannot_lock_out(tmp_path):
    engine = PolicyEngine(tmp_path / "policy.db")
    staged = engine.stage("consistent", _rules())
    engine.promote(staged["version_id"])

    effects = {
        engine.decide("deploy", {"target": "prod"}, surface=surface).effect
        for surface in ("cli", "voice", "gateway", "subagent", "fleet")
    }
    assert effects == {"deny"}
    assert engine.guard_tool("nara_policy_explain", {"decision_id": "x"}) is None
