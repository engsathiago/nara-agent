"""Opt-in bounded real-model practice, frozen before its reserved evaluation."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from nara_constants import reset_nara_home_override, set_nara_home_override
from plugins.mission_control.competence import CompetenceRegistry
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_github_source import _check_cited_source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    protocol_path = folder / "study_cycle_protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8-sig"))
    source = LearningFabric(args.source_root).source(protocol["source_id"])
    _check_cited_source(source)
    root = Path(tempfile.mkdtemp(prefix="nara-live-study-cycle-"))
    print(f"profile: {root}", flush=True)
    (root / "config.yaml").write_text(json.dumps({
        "model": {"provider": "custom", "default": protocol["model"],
                  "base_url": "http://127.0.0.1:11434/v1"},
        "memory": {"provider": "nara_temporal"},
        "auxiliary": {"transient_retries": 0, "nara_media_study": {"reasoning_effort": "none"}},
    }), encoding="utf-8")
    shutil.copytree(repo / "extensions/nara_temporal_memory/nara_temporal", root / "plugins/nara_temporal")
    token = set_nara_home_override(root)
    try:
        LearningFabric.open_default().ingest_file(
            source["stored_path"], modality=source["modality"], source_uri=source["source_uri"],
            transcript_path=source["transcript_path"], license_name=source.get("license"))
        registry = CompetenceRegistry.open_default()
        gap = registry.record_gap(
            "office.display-convention", "Transfer the demonstrated office display convention",
            "Previous frozen source-ID proposal scored 0.5 on reserved convention cases; "
            "this cycle uses a separate development case and new reserved inputs.", impact=3)
        plan = registry.create_study_plan(
            gap["gap_id"], protocol["objective"],
            sources=[{"uri": source["source_id"], "version": source["source_hash"]}],
            development_case_ids=protocol["development_case_ids"],
            holdout_case_ids=protocol["holdout_case_ids"],
            minimum_candidate_score=protocol["minimum_candidate_score"])
        system = root / "system.json"
        system.write_text(json.dumps({"model": protocol["model"], "provider": "ollama-local",
                                     "task": "office-display-convention"}), encoding="utf-8")
        env = {key: value for key, value in os.environ.items()
               if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG"}}
        env["NARA_HOME"] = str(root)
        result = subprocess.run(
            [sys.executable, "-m", "nara_cli.main", "mission", "study-run", plan.plan_id,
             source["source_id"], "--cases-file", str(protocol_path),
             "--evaluator", str(folder / "office_labels_practice.py"), "--system-file", str(system),
             "--max-attempts", str(protocol["max_attempts"]),
             "--max-seconds", str(protocol["max_seconds"]), "--timeout", "120"],
            cwd=repo, env=env, capture_output=True, text=True, timeout=900, check=False)
        (root / "cycle.stdout").write_text(result.stdout, encoding="utf-8")
        (root / "cycle.stderr").write_text(result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"study command exited {result.returncode}; inspect {root}")
        report = json.loads(result.stdout)
        summary = {"profile": str(root), "plan_id": plan.plan_id, "status": report["status"],
                   "generation_calls_started": report["generation_calls_started"],
                   "evaluator_calls_started": report["evaluator_calls_started"],
                   "receipt_sha256": report["receipt_sha256"],
                   "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
                   "gap_state": registry.gap(plan.gap_id)["state"],
                   "skill_activated": bool(list((root / "skills").glob("nara-learned-*")))}
        (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2), flush=True)
    finally:
        reset_nara_home_override(token)


if __name__ == "__main__":
    main()
