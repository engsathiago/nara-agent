from __future__ import annotations

from pathlib import Path

import pytest

from plugins.mission_control.learning_fabric import LearningFabric


@pytest.mark.parametrize("transcript", [False, True])
def test_reingestion_rejects_corrupted_archived_evidence(tmp_path, transcript):
    fabric = LearningFabric(tmp_path / "fabric")
    original = tmp_path / "lesson.txt"
    original.write_text("Preserve evidence before learning.", encoding="utf-8")
    supplied = tmp_path / "speech.txt"
    supplied.write_text("Check the reserved cases.", encoding="utf-8")
    kwargs = {"transcript_path": supplied} if transcript else {}
    source = fabric.ingest_file(original, modality="document", **kwargs)
    archived = Path(source["transcript_path" if transcript else "stored_path"])
    archived.write_bytes(b"corrupted archive")

    with pytest.raises(ValueError, match="archived learning evidence.*changed"):
        LearningFabric(fabric.root).ingest_file(original, modality="document", **kwargs)

    assert archived.read_bytes() == b"corrupted archive"
    assert fabric.source(source["source_id"])["source_hash"] == source["source_hash"]


def test_document_claim_requires_exact_source_quote_and_verification(tmp_path):
    fabric = LearningFabric(tmp_path / "fabric")
    document = tmp_path / "guide.txt"
    document.write_text("Atomic replacement preserves the old file until commit.\n", encoding="utf-8")
    source = fabric.ingest_file(
        document, modality="document", version="v1", license_name="MIT")
    claim = fabric.propose_claim(
        source["source_id"], "Atomic replacement preserves the old file",
        "Atomic replacement preserves the old file", confidence=0.9)

    assert source["extraction_status"] == "extracted"
    assert fabric.search("atomic replacement") == []
    verified = fabric.verify_claim(
        claim["claim_id"], verifier_id="judge", evidence_artifact_ids=["sha256:doc"], accepted=True)
    assert verified["status"] == "verified"
    assert fabric.search("atomic replacement")[0]["claim_id"] == claim["claim_id"]


def test_audio_without_transcript_stays_unextracted_then_uses_supplied_transcript(tmp_path):
    fabric = LearningFabric(tmp_path / "fabric")
    audio = tmp_path / "lesson.wav"
    audio.write_bytes(b"RIFF-not-a-real-fixture-wave")
    pending = fabric.ingest_file(audio, modality="audio", source_uri="file:///lesson.wav")
    transcript = tmp_path / "lesson.txt"
    transcript.write_text("Use a reserved holdout before promotion.", encoding="utf-8")
    extracted = fabric.ingest_file(
        audio, modality="audio", source_uri="file:///lesson.wav", transcript_path=transcript)

    assert pending["extraction_status"] == "needs_extraction"
    assert pending["extracted_text"] is None
    assert extracted["extraction_status"] == "transcript_supplied"
    assert extracted["transcript_hash"] is not None
    assert "reserved holdout" in extracted["extracted_text"]
