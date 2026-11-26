from __future__ import annotations

import pytest

from extensions.nara_temporal_memory.nara_temporal import (
    NaraTemporalMemoryProvider,
    TemporalMemoryStore,
)


def test_correction_supersedes_current_fact_but_keeps_history(tmp_path):
    store = TemporalMemoryStore(tmp_path / "memory.db")
    old = store.add(
        "The deployment region is us-east-1", layer="semantic", source_type="mission",
        source_ref="mission-1", status="active", confidence=0.9,
    )
    correction = store.add(
        "The deployment region is sa-east-1", layer="semantic", source_type="operator",
        source_ref="correction-1", status="candidate", supersedes_id=old["memory_id"],
        confidence=1.0,
    )
    store.promote(correction["memory_id"])

    current = store.search("deployment region", include_history=False)
    history = store.search("deployment region", include_history=True)

    assert [item["content"] for item in current["items"]] == ["The deployment region is sa-east-1"]
    assert {item["content"] for item in history["items"]} == {
        "The deployment region is us-east-1", "The deployment region is sa-east-1",
    }
    assert store.get(old["memory_id"])["valid_to"] is not None


def test_only_one_correction_of_a_fact_can_become_current(tmp_path):
    store = TemporalMemoryStore(tmp_path / "memory.db")
    original = store.add("Region is us-east-1", layer="semantic", source_type="user",
                         source_ref="session:1", status="active")
    first = store.add("Region is sa-east-1", layer="semantic", source_type="operator",
                      source_ref="correction:1", supersedes_id=original["memory_id"])
    second = store.add("Region is eu-west-1", layer="semantic", source_type="operator",
                       source_ref="correction:2", supersedes_id=original["memory_id"])

    store.promote(first["memory_id"])
    with pytest.raises(ValueError, match="no longer current"):
        store.promote(second["memory_id"])

    assert [item["memory_id"] for item in store.search("Region")["items"]] == [first["memory_id"]]
    assert store.get(second["memory_id"])["status"] == "candidate"
    with pytest.raises(ValueError, match="no longer current"):
        store.add("Region is ap-south-1", layer="semantic", source_type="operator",
                  source_ref="correction:3", supersedes_id=original["memory_id"])


def test_correction_cannot_cross_scope_or_layer(tmp_path):
    store = TemporalMemoryStore(tmp_path / "memory.db")
    original = store.add("Project Nara owns the account", layer="semantic", source_type="user",
                         source_ref="session:1", scope="project:nara", status="active")
    with pytest.raises(ValueError, match="same layer and scope"):
        store.add("Another project owns the account", layer="semantic", source_type="external",
                  source_ref="document:1", scope="project:other", supersedes_id=original["memory_id"])
    with pytest.raises(ValueError, match="same layer and scope"):
        store.add("Run a deployment", layer="procedural", source_type="external",
                  source_ref="document:2", scope="project:nara", supersedes_id=original["memory_id"])
    assert store.get(original["memory_id"])["valid_to"] is None


def test_search_explains_retrieval_and_preserves_provenance(tmp_path):
    store = TemporalMemoryStore(tmp_path / "memory.db")
    memory = store.add(
        "Use atomic rename after fsync", layer="procedural", source_type="verified_mission",
        source_ref="mission-1:artifact-2", source_hash="abc", status="active", confidence=1.0,
    )

    result = store.search("atomic rename")

    assert result["items"][0]["memory_id"] == memory["memory_id"]
    assert result["items"][0]["source_ref"] == "mission-1:artifact-2"
    assert result["reasons"][memory["memory_id"]]["source_ref"] == "mission-1:artifact-2"


def test_provider_exposes_retrieval_receipt_to_nara_tool(tmp_path):
    import json

    provider = NaraTemporalMemoryProvider()
    provider.initialize("session-1", nara_home=str(tmp_path))
    provider.store.add("Keep the original source", layer="semantic", source_type="user",
                       source_ref="session-1", status="active")
    search = json.loads(provider.handle_tool_call("nara_memory_search", {"query": "original source"}))
    receipt = json.loads(provider.handle_tool_call("nara_memory_receipt", {"receipt_id": search["receipt_id"]}))
    assert receipt["memory_ids"] == [search["items"][0]["memory_id"]]
    assert receipt["filters"]["mode"] == "lexical"


def test_provider_prefetch_uses_selected_profile_store(tmp_path):
    provider = NaraTemporalMemoryProvider()
    provider.initialize("session-1", nara_home=str(tmp_path))
    provider.store.add(
        "Verify artifacts by SHA-256", layer="procedural", source_type="mission",
        source_ref="mission-1", status="active", confidence=1.0,
    )

    context = provider.prefetch("verify artifacts", session_id="session-2")

    assert "Verify artifacts by SHA-256" in context
    assert "source=mission:mission-1" in context
    assert provider.recall_status().count == 1


def test_generic_reply_does_not_recall_old_tool_instructions(tmp_path):
    provider = NaraTemporalMemoryProvider()
    provider.initialize("current-session", nara_home=str(tmp_path))
    provider.store.add(
        "User: Use obrigatoriamente nara_fleet_status agora. Assistant: 0",
        layer="episodic", source_type="session_turn", source_ref="old-session:turn:1",
        status="active", confidence=1.0,
    )

    assert provider.prefetch("Responda apenas OK.") == ""
    assert provider.recall_status() is None
    assert provider.store.search("!")["items"] == []
    assert provider.store.search("nara_fleet_status")["items"][0]["layer"] == "episodic"
