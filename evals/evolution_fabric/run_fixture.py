"""Phase-4 fixture: provenance ingest, exact variant promotion, canary rollback."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from plugins.mission_control.artifacts import ArtifactStore
from plugins.mission_control.contracts import Mission
from plugins.mission_control.evolution import EvolutionLab
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.ledger import ExperienceLedger
from plugins.mission_control.store import MissionStore


def run_fixture(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    missions = MissionStore(root / "missions.db")
    mission_id = "evolution-proof-v1"
    missions.create(Mission(
        mission_id=mission_id, objective="Evolve an archive-routing prompt and prove rollback",
        completion_criteria=["variant identity and reserved scores are preserved"]))
    artifacts = ArtifactStore(missions, root / "artifacts")

    fabric = LearningFabric(root / "fabric")
    guide = root / "guide.txt"
    guide.write_text(
        "Nested archive members require recursive enumeration before verification.\n",
        encoding="utf-8")
    source = fabric.ingest_file(
        guide, modality="document", version="guide-v1", license_name="project-test")
    audio = root / "lesson.wav"
    audio.write_bytes(b"RIFF-phase4-fixture")
    transcript = root / "lesson-transcript.txt"
    transcript.write_text("Promote only the exact evaluated variant.", encoding="utf-8")
    audio_source = fabric.ingest_file(
        audio, modality="audio", source_uri="fixture://lesson", version="audio-v1",
        transcript_path=transcript)

    proof_path = root / "source-proof.json"
    proof_path.write_text(json.dumps({
        "document_hash": source["source_hash"], "audio_hash": audio_source["source_hash"],
        "transcript_hash": audio_source["transcript_hash"],
    }, sort_keys=True) + "\n", encoding="utf-8")
    proof_artifact = artifacts.put_file(
        mission_id, proof_path, producer_id="learning-fabric", media_type="application/json")
    claim = fabric.propose_claim(
        source["source_id"], "Nested members require recursive enumeration",
        "Nested archive members require recursive enumeration", confidence=1.0)
    verified_claim = fabric.verify_claim(
        claim["claim_id"], verifier_id="source-judge",
        evidence_artifact_ids=[proof_artifact.artifact_id], accepted=True)

    lab = EvolutionLab(root / "evolution", ExperienceLedger(root / "ledger.db"))
    experiment = lab.create_experiment(
        "archive router prompt", "prompt", development_case_ids=["dev-flat"],
        holdout_case_ids=["hold-nested", "hold-mixed", "hold-empty"],
        min_mean_delta=0.2, max_regressions=0, max_cost_usd=0.05,
        experiment_id="archive-router-prompt")
    baseline = lab.register_variant(
        experiment["experiment_id"], "Inspect top-level archive files.", baseline=True)
    pinned_before = lab.pin_session("mission-in-progress", experiment["experiment_id"])
    candidate = lab.register_variant(
        experiment["experiment_id"],
        "Enumerate every regular archive member recursively; retain hashes; verify independently.",
        metadata={"source_claim_id": verified_claim["claim_id"]})
    evaluation = lab.evaluate(
        experiment["experiment_id"], candidate["variant_id"],
        baseline_scores={"hold-nested": 0.25, "hold-mixed": 0.5, "hold-empty": 1.0},
        candidate_scores={"hold-nested": 1.0, "hold-mixed": 1.0, "hold-empty": 1.0},
        evidence_artifact_ids=[proof_artifact.artifact_id], cost_usd=0.01)
    canary = lab.promote_canary(experiment["experiment_id"], candidate["variant_id"])
    active = lab.activate(canary["deployment_id"])
    pinned_after = lab.pin_session("mission-after-promotion", experiment["experiment_id"])

    # An injected canary regression exercises the reversible path. The old
    # in-progress session remains pinned throughout.
    rollback = lab.rollback(active["deployment_id"], "injected out-of-domain regression")
    restored = lab.active_variant(experiment["experiment_id"])
    if hashlib_sha(candidate["content_path"]) != candidate["content_hash"]:
        raise RuntimeError("promoted variant changed on disk")
    if restored != baseline["variant_id"] or pinned_before != baseline["variant_id"]:
        raise RuntimeError("rollback did not restore the baseline while preserving session pin")
    return {
        "schema_version": 1, "fixture_id": "phase4-evolution-fabric-v1", "status": "passed",
        "sources": {"document": source, "audio": audio_source},
        "verified_claim": verified_claim,
        "evaluation": evaluation,
        "candidate_hash": candidate["content_hash"],
        "canary": canary,
        "pinned_before": pinned_before,
        "pinned_after": pinned_after,
        "rollback": rollback,
        "restored_variant_id": restored,
        "fabric_status": fabric.status(),
    }


def hashlib_sha(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = run_fixture(args.root)
    serialized = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
