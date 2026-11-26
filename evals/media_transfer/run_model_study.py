"""Opt-in live local study through the registered Nara CLI, followed by transfer.

Requires the locally archived source and Ollama model; no external account.
The full source/request stays in the temporary profile, not the public repo.
"""

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
from plugins.mission_control.learning_cli import open_learning_lab
from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_github_source import _check_cited_source
from plugins.mission_control.learning_runner import ProcessEvaluator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    protocol_dir = Path(__file__).resolve().parent
    repo = protocol_dir.parents[1]
    protocol = json.loads((protocol_dir / "model_study_protocol.json").read_text(encoding="utf-8-sig"))
    source = LearningFabric(args.source_root).source(protocol["source_id"])
    _check_cited_source(source)
    root = Path(tempfile.mkdtemp(prefix="nara-model-media-study-"))
    print(f"profile: {root}", flush=True)
    (root / "config.yaml").write_text(json.dumps({
        "model": {"provider": "custom", "default": protocol["model"],
                  "base_url": "http://127.0.0.1:11434/v1"},
        "memory": {"provider": "nara_temporal"},
    }), encoding="utf-8")
    shutil.copytree(repo / "extensions/nara_temporal_memory/nara_temporal", root / "plugins/nara_temporal")
    token = set_nara_home_override(root)
    try:
        LearningFabric.open_default().ingest_file(
            source["stored_path"], modality=source["modality"], source_uri=source["source_uri"],
            transcript_path=source["transcript_path"],
        )
        env = {key: value for key, value in os.environ.items()
               if key in {"PATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG"}}
        env["NARA_HOME"] = str(root)
        result = subprocess.run(
            [sys.executable, "-m", "nara_cli.main", "mission", "learn-media-study",
             source["source_id"], "--objective", protocol["objective"]],
            cwd=repo, env=env, capture_output=True, text=True, timeout=180, check=False,
        )
        (root / "study.stdout").write_text(result.stdout, encoding="utf-8")
        (root / "study.stderr").write_text(result.stderr, encoding="utf-8")
        print(f"study exit: {result.returncode}", flush=True)
        if result.returncode:
            raise RuntimeError(f"registered study command failed; inspect {root}")
        study = json.loads(result.stdout)
        if study["status"] != "candidate":
            print(json.dumps({"study_status": study["status"], "root": str(root)}))
            return
        lab = open_learning_lab()
        candidate_id = study["candidate"]["candidate_id"]
        evaluator = ProcessEvaluator(protocol_dir / "office_labels.py", root / "evaluation-evidence", timeout=120)
        def run(candidate, case):
            print(f"evaluating {case['case_id']} {'candidate' if candidate else 'baseline'}", flush=True)
            return evaluator(candidate, case)
        report = lab.evaluate_transfer(
            candidate_id, protocol["cases"], run, development_case_ids={"development"},
            evaluator_sha256=evaluator.sha256, evaluator_path=str(evaluator.archived_path),
        )
        outcome = {"study": study, "evaluation": report,
                   "protocol_sha256": hashlib.sha256((protocol_dir / "model_study_protocol.json").read_bytes()).hexdigest()}
        if report["passed"]:
            outcome["promoted_skill"] = str(lab.promote(candidate_id, require_evidence=True))
            outcome["rolled_back_skill"] = str(lab.rollback(candidate_id))
        (root / "result.json").write_text(json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"result": str(root / "result.json"), "passed": report["passed"],
                          "mean_delta": report["mean_delta"], "regressions": report["regressions"]}), flush=True)
    finally:
        reset_nara_home_override(token)


if __name__ == "__main__":
    main()
