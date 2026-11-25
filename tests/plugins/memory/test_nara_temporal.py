from __future__ import annotations

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
