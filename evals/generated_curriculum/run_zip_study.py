"""Opt-in real research, curriculum generation and terminal study in a disposable profile."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def cli(repo, root, env, label, *args):
    result = subprocess.run([sys.executable, "-m", "nara_cli.main", "mission", *args],
                            cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8",
                            timeout=60, check=False)
    (root / (label + ".stdout")).write_text(result.stdout, encoding="utf-8")
    (root / (label + ".stderr")).write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"{label} exited {result.returncode}; inspect {root}")
    return json.loads(result.stdout)


def work(repo, root, env):
    deadline = time.monotonic() + 1500
    with (root / "work.stdout").open("w", encoding="utf-8") as stdout, (root / "work.stderr").open("w", encoding="utf-8") as stderr:
        child = subprocess.Popen([sys.executable, "-m", "nara_cli.main", "mission", "study-work"],
                                 cwd=repo, env=env, stdout=stdout, stderr=stderr)
        try:
            while True:
                try:
                    code = child.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("live study outer deadline exhausted")
                    print("Study worker is still executing; archived progress remains in its profile.", flush=True)
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=10)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3.5:4b")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    with urlopen("http://127.0.0.1:11434/api/tags", timeout=10) as response:
        installed = json.load(response)["models"]
    model = next(item for item in installed if item["name"] == args.model)
    root = Path(tempfile.mkdtemp(prefix="nara-live-zip-study-")).resolve()
    print(f"profile: {root}", flush=True)
    write_json(root / "model.json", {"name": model["name"], "digest": model["digest"], "size": model["size"]})
    write_json(root / "config.yaml", {
        "_setup_done": True,
        "model": {"provider": "custom", "default": args.model,
                  "base_url": "http://127.0.0.1:11434/v1", "api_key": "local-eval"},
        "memory": {"provider": "nara_temporal"},
        "auxiliary": {"transient_retries": 0,
                      "nara_curriculum": {"reasoning_effort": "none"},
                      "nara_source_selection": {"reasoning_effort": "none"},
                      "nara_media_study": {"reasoning_effort": "none"}},
    })
    shutil.copytree(repo / "extensions/nara_temporal_memory/nara_temporal", root / "plugins/nara_temporal")
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG"}}
    env["NARA_HOME"] = str(root)
    prepared = cli(repo, root, env, "prepare", "study-oracle-prepare", "zip-manifest",
                   str(root / "protocol"), "--model", args.model)
    gap = cli(repo, root, env, "gap", "gap-record", "archive.zip-manifest",
              "ZIP manifest learning not yet demonstrated",
              "No real-model generated-curriculum transfer evidence exists for this model and runtime; "
              "this records an evidence gap, not an invented baseline failure.", "--impact", "3")
    job = cli(repo, root, env, "enqueue", "study-enqueue", gap["gap_id"],
              "--protocol-file", prepared["protocol_file"])
    write_json(root / "frozen.json", {"job_id": job["mission_id"], "protocol": job["constraints"]["protocol"],
                                     "oracle": prepared["system"], "model_digest": model["digest"],
                                     "study_config_sha256": hashlib.sha256((root / "config.yaml").read_bytes()).hexdigest(),
                                     "auxiliary_reasoning_effort": "none"})
    code = work(repo, root, env)
    jobs = cli(repo, root, env, "jobs", "study-jobs")
    current = next(row for row in jobs if row["job_id"] == job["mission_id"])
    activated = bool(list((root / "skills").glob("nara-learned-*")))
    rollback = None
    if activated:
        rollback = cli(repo, root, env, "rollback", "study-rollback", job["mission_id"],
                       "--reason", "Disposable live validation completed")
    summary = {"profile": str(root), "job_id": job["mission_id"], "worker_exit": code,
               "status": current["status"], "progress": current["progress"],
               "model_digest": model["digest"], "activated_in_temporary_profile": activated,
               "rollback": rollback, "native_skill_remaining": bool(list((root / "skills").glob("nara-learned-*"))),
               "work_stdout_sha256": hashlib.sha256((root / "work.stdout").read_bytes()).hexdigest()}
    write_json(root / "summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
