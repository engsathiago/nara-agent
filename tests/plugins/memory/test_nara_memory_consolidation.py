"""Exact cross-experience recall keeps every source without repeating stale facts."""

from extensions.nara_temporal_memory.nara_temporal import TemporalMemoryStore


def test_exact_facts_share_one_recall_item_but_preserve_both_sources(tmp_path):
    store = TemporalMemoryStore(tmp_path / "memory.db")
    first = store.add(
        "Deployments run in sa-east-1", layer="semantic", source_type="verified_mission",
        source_ref="mission:a", scope="project:nara", status="active",
    )
    second = store.add(
        "Deployments run in sa-east-1", layer="semantic", source_type="verified_mission",
        source_ref="mission:b", scope="project:nara", status="active",
    )
    result = store.search("deployments sa-east-1", scope="project:nara")

    assert len(result["items"]) == 1
    item = result["items"][0]
    assert {item["memory_id"], *item["supporting_memory_ids"]} == {
        first["memory_id"], second["memory_id"],
    }
    assert item["consolidated_memory_count"] == 2
    assert store.get(first["memory_id"])["source_ref"] == "mission:a"
    assert store.get(second["memory_id"])["source_ref"] == "mission:b"
    receipt = store.get_receipt(result["receipt_id"])
    assert receipt["reasons"][item["memory_id"]]["consolidated_memory_count"] == 2


def test_correction_hides_stale_duplicate_only_within_its_scope(tmp_path):
    store = TemporalMemoryStore(tmp_path / "memory.db")
    original = store.add(
        "Deployment region is us-east-1", layer="semantic", source_type="verified_mission",
        source_ref="mission:a", scope="project:nara", status="active",
    )
    duplicate = store.add(
        "Deployment region is us-east-1", layer="semantic", source_type="verified_mission",
        source_ref="mission:b", scope="project:nara", status="active",
    )
    other_scope = store.add(
        "Deployment region is us-east-1", layer="semantic", source_type="verified_mission",
        source_ref="mission:c", scope="project:other", status="active",
    )
    correction = store.add(
        "Deployment region is sa-east-1", layer="semantic", source_type="operator",
        source_ref="correction:1", scope="project:nara", supersedes_id=original["memory_id"],
    )
    store.promote(correction["memory_id"])

    current = store.search("deployment region", scope="project:nara")
    assert [item["memory_id"] for item in current["items"]] == [correction["memory_id"]]
    assert current["suppressed_stale_duplicates"] == 1
    assert store.search("deployment region", scope="project:other")["items"][0]["memory_id"] == other_scope["memory_id"]
    history = store.search("deployment region", scope="project:nara", include_history=True)
    assert {item["memory_id"] for item in history["items"]} == {
        original["memory_id"], duplicate["memory_id"], correction["memory_id"],
    }

    reversal = store.add(
        "Deployment region is us-east-1", layer="semantic", source_type="operator",
        source_ref="correction:2", scope="project:nara", supersedes_id=correction["memory_id"],
    )
    store.promote(reversal["memory_id"])
    restored = store.search("deployment region", scope="project:nara")
    assert [item["memory_id"] for item in restored["items"]] == [reversal["memory_id"]]
    assert restored["items"][0]["supporting_memory_ids"] == [duplicate["memory_id"]]
