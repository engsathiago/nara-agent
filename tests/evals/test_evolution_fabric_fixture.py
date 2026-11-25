from __future__ import annotations

from evals.evolution_fabric.run_fixture import run_fixture


def test_exact_variant_and_multimodal_provenance_survive_canary_rollback(tmp_path):
    result = run_fixture(tmp_path)

    assert result["status"] == "passed"
    assert result["sources"]["document"]["extraction_status"] == "extracted"
    assert result["sources"]["audio"]["extraction_status"] == "transcript_supplied"
    assert result["verified_claim"]["status"] == "verified"
    assert result["evaluation"]["passed"] is True
    assert result["canary"]["stage"] == "canary"
    assert result["pinned_before"] == result["rollback"]["restored"]
    assert result["pinned_after"] == result["rollback"]["rolled_back"]
    assert result["restored_variant_id"] == result["rollback"]["restored"]
