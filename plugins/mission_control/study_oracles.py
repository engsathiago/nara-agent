"""Prepare calibrated task-family protocols through the existing mission CLI."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

from nara_cli.config import get_project_root
from plugins.mission_control import study_oracle_zip


FAMILY = "zip-manifest"


def register_oracle_cli(actions):
    actions.add_parser("study-oracles", help="List calibrated study task families")
    command = actions.add_parser("study-oracle-prepare", help="Calibrate and export a generated-curriculum protocol")
    command.add_argument("family", choices=[FAMILY])
    command.add_argument("output", type=Path)
    command.add_argument("--model", required=True, help="Installed local model to exercise through Nara")
    command.add_argument("--base-url", default="http://127.0.0.1:11434/v1")


def _runtime(root):
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=10, check=False)
    changes = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=10, check=False)
    return {"commit": revision.stdout.strip() if revision.returncode == 0 else None,
            "dirty": bool(changes.stdout) if changes.returncode == 0 else None, "python": sys.version.split()[0]}


def _brief():
    return {"task_family": FAMILY, "version": 2,
            "payload_schema": {"type": "object", "additionalProperties": False, "required": ["members"],
                "properties": {"members": {"type": "array", "minItems": 0, "maxItems": 8,
                    "items": {"type": "object", "additionalProperties": False, "required": ["name", "text"],
                        "properties": {"name": {"type": "string", "minLength": 1, "maxLength": 160},
                                       "text": {"type": "string", "minLength": 0, "maxLength": 4096}}}}}},
            "case_contract": {"members": [{"name": "relative ZIP member path, trailing / denotes directory",
                                            "text": "UTF-8 contents; empty for directory entries"}]},
            "bounds": "Exactly one development, one transfer and one canary case. Each has 0-8 unique relative members; "
                      "name <=160 chars, text <=4096 UTF-8 bytes, total content <=16384 bytes. No . or .. path parts.",
            "independence": "Use genuinely different member topologies in each split: member path depth, "
                            "directory/file kind, and presence of non-ASCII names. Renaming otherwise identical "
                            "archives or group IDs is not independent. Include nested regular members and a directory "
                            "in at least one case; another case may be empty or flat.",
            "questions": list(study_oracle_zip.QUESTIONS),
            "teaching_contract": "Choose 1-3 questions from the provided wording. Answer with the Python API "
                                 "method or attribute name, using the source, and cite its supporting span. "
                                 "Do not add a prose sentence around the answer. The explanation must copy one "
                                 "supplied source span exactly, discussing infolist, is_dir, or file_size.",
            "task_result": "The real Nara terminal inspects source.zip and writes manifest.json: sorted regular "
                           "member paths in files; integer total_file_bytes excluding directories; integer directory_count. "
                           "The validator computes truth from actual ZipInfo records; do not generate an answer key."}


def prepare(output, model, base_url):
    parsed = urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
        raise ValueError("this oracle uses an explicit local HTTP model endpoint without credentials")
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError("oracle model must contain 1-200 characters")
    calibration = study_oracle_zip.calibrate()
    if not calibration["passed"]:
        raise ValueError("ZIP oracle calibration failed; protocol was not exported")
    output = output.expanduser().resolve()
    if output.exists():
        raise ValueError("oracle output must be a new directory; existing files are never overwritten")
    runtime_root = get_project_root()
    identity = _runtime(runtime_root)
    source = Path(study_oracle_zip.__file__).read_text(encoding="utf-8-sig")
    output.mkdir(parents=True)
    hashes = {}
    for mode in ("validator", "transfer", "canary"):
        config = {"mode": mode, "model": model, "base_url": base_url,
                  "runtime_root": str(runtime_root), "runtime_identity": identity}
        body = source + "\nif __name__ == '__main__':\n    print(json.dumps(main(" + repr(config) + ")))\n"
        path = output / (mode + ".py")
        path.write_text(body, encoding="utf-8")
        hashes[mode] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / "brief.json").write_text(json.dumps(_brief(), indent=2), encoding="utf-8")
    system = {"family": FAMILY, "model": model, "provider": "local-openai-compatible",
              "runtime": identity, "oracle_sources": hashes}
    (output / "system.json").write_text(json.dumps(system, indent=2), encoding="utf-8")
    (output / "calibration.json").write_text(json.dumps({**calibration, "system": system}, indent=2), encoding="utf-8")
    protocol = {"objective": "Python zipfile documentation: inspect ZIP archive members, directories and uncompressed sizes",
                "domains": ["docs.python.org"], "max_sources": 3, "research_seconds": 120,
                "source_context": {"strategy": "lexical-spans-v1", "max_characters": 6000,
                                   "terms": ["infolist", "is_dir", "file_size"]},
                "evaluator": str(output / "transfer.py"), "system_file": str(output / "system.json"),
                "max_attempts": 2, "max_seconds": 1200, "timeout": 120, "minimum_candidate_score": 1.0,
                "curriculum": {"brief_file": str(output / "brief.json"), "validator": str(output / "validator.py"),
                               "canary_evaluator": str(output / "canary.py"), "minimum_score": 1.0, "minimum_gain": 0.01}}
    path = output / "protocol.json"
    path.write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    return {"protocol_file": str(path), "calibration": calibration, "system": system,
            "status": "prepared", "model_executed": False}


def oracle_command(args):
    if args.mission_action == "study-oracles":
        return [{"family": FAMILY, "execution": "Nara terminal over an actual temporary ZIP",
                 "model_backend": "local HTTP", "calibration": study_oracle_zip.calibrate()}]
    return prepare(args.output, args.model, args.base_url)
