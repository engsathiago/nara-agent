"""Self-contained ZIP oracle, exported byte-for-byte into frozen study protocols."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
import zipfile


QUESTIONS = {
    "Which ZipFile method returns member metadata records?": ("infolist", {"infolist", "zipfile.infolist"}),
    "Which ZipInfo method identifies a directory entry?": ("is_dir", {"is_dir", "zipinfo.is_dir"}),
    "Which ZipInfo attribute holds uncompressed bytes?": ("file_size", {"file_size", "zipinfo.file_size"}),
}


def members(payload):
    if not isinstance(payload, dict) or set(payload) != {"members"}:
        raise ValueError("ZIP payload must contain only members")
    rows = payload["members"]
    if not isinstance(rows, list) or len(rows) > 8:
        raise ValueError("ZIP case supports 0-8 members")
    names, size = set(), 0
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"name", "text"}:
            raise ValueError("ZIP member requires name and text")
        name, text = row["name"], row["text"]
        if (not isinstance(name, str) or not 1 <= len(name) <= 160 or name in names
                or name.startswith("/") or "\\" in name or "\x00" in name
                or any(part in {".", "..", ""} for part in name.rstrip("/").split("/"))):
            raise ValueError("ZIP case member must have a unique relative name")
        if not isinstance(text, str) or len(text.encode()) > 4096 or (name.endswith("/") and text):
            raise ValueError("ZIP case text exceeds bounds or populates a directory")
        names.add(name)
        size += len(text.encode())
    if size > 16384:
        raise ValueError("ZIP case uncompressed content exceeds 16 KiB")
    return rows


def build_archive(path, rows):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for row in rows:
            info = zipfile.ZipInfo(row["name"], date_time=(2026, 1, 1, 0, 0, 0))
            archive.writestr(info, row["text"].encode())
    return path


def reference_manifest(path):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        return {"files": sorted(info.filename for info in infos if not info.is_dir()),
                "total_file_bytes": sum(info.file_size for info in infos if not info.is_dir()),
                "directory_count": sum(info.is_dir() for info in infos)}


def grade_manifest(observed, expected):
    if not isinstance(observed, dict) or set(observed) != set(expected):
        return 0.0
    if type(observed.get("total_file_bytes")) is not int or type(observed.get("directory_count")) is not int:
        return 0.0
    return float(observed == expected)


def calibrate():
    with TemporaryDirectory(prefix="nara-zip-calibration-") as folder:
        path = Path(folder) / "sample.zip"
        build_archive(path, [{"name": "nested/", "text": ""},
                             {"name": "nested/item.txt", "text": "ação"}, {"name": "root.txt", "text": "z"}])
        truth = {"files": ["nested/item.txt", "root.txt"], "total_file_bytes": 7, "directory_count": 1}
        reference = reference_manifest(path)
        proposals = [
            ("correct", truth, 1), ("missed_nested", {**truth, "files": ["root.txt"]}, 0),
            ("directory_as_file", {**truth, "files": ["nested/", *truth["files"]]}, 0),
            ("characters_not_bytes", {**truth, "total_file_bytes": 5}, 0),
            ("bool_as_count", {**truth, "directory_count": True}, 0),
            ("extra_field", {**truth, "invented": True}, 0),
            ("no_artifact", None, 0),
        ]
        probes = [{"name": name, "observed": grade_manifest(value, reference), "expected": score}
                  for name, value, score in proposals]
        empty = Path(folder) / "empty.zip"
        build_archive(empty, [])
        empty_truth = {"files": [], "total_file_bytes": 0, "directory_count": 0}
        probes.append({"name": "empty_archive", "observed": grade_manifest(empty_truth, reference_manifest(empty)), "expected": 1})
        return {"family": "zip-manifest", "version": 1, "passed": reference == truth and all(
            row["observed"] == row["expected"] for row in probes), "probes": probes}


def _validate_teaching(material, source):
    spans = {span["id"]: span["text"] for span in source["spans"]}
    explanation = material["explanation"]
    if explanation not in spans.values() or not any(term in explanation for term in ("infolist", "is_dir", "file_size")):
        raise ValueError("ZIP explanation must quote a relevant supplied source span exactly")
    for question in material["questions"]:
        if question["question"] not in QUESTIONS:
            raise ValueError("ZIP question is outside the calibrated fact set")
        term, accepted = QUESTIONS[question["question"]]
        answer = question["answer"].strip().strip("`").removesuffix("()").casefold()
        if answer not in accepted:
            raise ValueError("ZIP question answer contradicts the runtime API")
        if not any(term in spans.get(cite["id"], "") for cite in question["citations"]):
            raise ValueError("ZIP question lacks a relevant source citation")


def validate_curriculum(case):
    package, seen = case["curriculum"], {}
    if sorted(row["split"] for row in package["cases"]) != ["canary", "development", "transfer"]:
        raise ValueError("ZIP oracle requires exactly one case per split")
    _validate_teaching(package["teaching_material"], case["source"])
    for row in package["cases"]:
        entries = members(row["payload"])
        # Renaming members/group IDs cannot disguise an identical structural task.
        shape = tuple(sorted((len(PurePosixPath(item["name"]).parts), item["name"].endswith("/"),
                              not item["name"].isascii()) for item in entries))
        if shape in seen and seen[shape] != row["split"]:
            raise ValueError("ZIP topology repeats across development and reserved splits")
        seen[shape] = row["split"]
    return {"accepted_cases": len(package["cases"]), "independence": "distinct ZIP member topologies across splits"}


def _await_gateway(child, home):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError("temporary gateway exited before readiness")
        try:
            state = json.loads((home / "gateway_state.json").read_text(encoding="utf-8-sig"))
        except (FileNotFoundError, json.JSONDecodeError):
            state = {}
        if state.get("pid") == child.pid and state.get("gateway_state") == "running":
            return
        try:
            child.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            continue
    raise TimeoutError("temporary gateway readiness exceeded 20 seconds")


@contextmanager
def owned_gateway(command, env, home):
    with (home / "oracle-gateway.stdout").open("w", encoding="utf-8") as stdout, (home / "oracle-gateway.stderr").open("w", encoding="utf-8") as stderr:
        child = subprocess.Popen(command, cwd=home, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        try:
            _await_gateway(child, home)
            yield child
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=2)
            (home / "oracle-gateway.json").write_text(json.dumps({"pid": child.pid, "returncode": child.returncode,
                                                                 "reaped": child.poll() is not None}), encoding="utf-8")


def _run_agent(config, prompt, skill_name):
    home = Path(os.environ["NARA_HOME"])
    settings = {"_setup_done": True, "model": {"provider": "custom", "default": config["model"],
                "base_url": config["base_url"], "api_key": "local-eval"},
                "agent": {"max_turns": 4, "run_budget_seconds": 85, "reasoning_effort": "none"},
                "terminal": {"backend": "local", "cwd": str(Path.cwd())},
                "auxiliary": {"transient_retries": 0}, "gateway": {"multiplex_profiles": False}}
    (home / "config.yaml").write_text(json.dumps(settings), encoding="utf-8")
    env = {key: value for key, value in os.environ.items()
           if key in {"PATH", "SYSTEMROOT", "WINDIR", "TZ", "LANG", "PYTHONPATH", "NARA_HOME"}}
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [config["runtime_root"], env.get("PYTHONPATH")]))
    command = [sys.executable, "-m", "nara_cli.main", "-z", prompt, "-t", "terminal",
               "--provider", "custom", "-m", config["model"], "--usage-file", str(Path("usage.json").resolve())]
    if skill_name:
        command.extend(["-s", skill_name])
    gateway = [sys.executable, "-m", "nara_cli.main", "gateway", "run", "--quiet"]
    with owned_gateway(gateway, env, home):
        result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90, check=False)
    Path("agent.stdout").write_text(result.stdout, encoding="utf-8")
    Path("agent.stderr").write_text(result.stderr, encoding="utf-8")
    usage_path = Path("usage.json")
    usage = json.loads(usage_path.read_text(encoding="utf-8-sig")) if usage_path.is_file() else {}
    if result.returncode:
        reason = usage.get("turn_exit_reason") or result.stderr[-300:]
        raise RuntimeError(f"Nara execution did not complete (exit {result.returncode}, {reason}); no task score assigned")
    if not usage:
        raise RuntimeError("Nara execution did not produce a usage receipt")
    return usage


def execute_case(request, config):
    case = request["case"]
    rows = members({key: value for key, value in case.items() if key != "case_id"})
    archive = build_archive(Path("source.zip"), rows)
    expected = reference_manifest(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    prompt = (
        "Inspect the ZIP file source.zip in the current directory using the terminal. Do not extract it or modify it. "
        "Write manifest.json with exactly these fields: files (lexicographically sorted regular-member paths, "
        "including nested paths, excluding directory entries), total_file_bytes (sum of uncompressed byte sizes "
        "of those regular members), directory_count (number of directory entries). All counts must be integers. "
        "Work only in this temporary directory. Do not install packages or access the network. "
        "After writing the JSON file, finish with a brief confirmation."
    )
    if request.get("candidate"):
        prompt += "\nStudied procedure:\n" + "\n".join(request["candidate"]["steps"])
    skill_name, observed_skill = None, None
    if request.get("canary"):
        path = Path(os.environ["NARA_HOME"]) / "skills" / request["canary"]["skill_name"] / "SKILL.md"
        if path.is_file():
            skill_name = request["canary"]["skill_name"]
            observed_skill = hashlib.sha256(path.read_bytes()).hexdigest()
    usage = _run_agent(config, prompt, skill_name)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError("agent changed the ZIP under evaluation")
    answer_path = Path("manifest.json")
    try:
        answer = json.loads(answer_path.read_text(encoding="utf-8-sig")) if answer_path.is_file() else None
    except json.JSONDecodeError:
        answer = None
    score = grade_manifest(answer, expected)
    report = {"case_id": case["case_id"], "archive_sha256": digest, "observed": answer,
              "expected": expected, "score": score, "usage": usage,
              "model": config["model"], "runtime_identity": config["runtime_identity"],
              "native_skill_sha256": observed_skill, "native_preload": skill_name}
    Path("evaluation.json").write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    result = {"score": score, "artifact_paths": ["source.zip", "evaluation.json", "agent.stdout", "agent.stderr", "usage.json",
              "profile/oracle-gateway.json", "profile/oracle-gateway.stdout", "profile/oracle-gateway.stderr"],
              "feedback": json.dumps({"observed": answer, "expected": expected}),
              "observed_skill_sha256": observed_skill}
    cost = usage.get("total_including_auxiliary", {}).get("estimated_cost_usd")
    if (cost is not None and usage.get("cost_status") in {"actual", "estimated", "included"}
            and usage.get("auxiliary", {}).get("api_calls", 0) == 0):
        result["cost_usd"] = cost
    return result


def main(config):
    request = json.load(sys.stdin)
    if config["mode"] != "validator":
        return execute_case(request, config)
    calibration = calibrate()
    try:
        if not calibration["passed"]:
            raise ValueError("ZIP oracle calibration failed")
        validation = validate_curriculum(request["case"])
        report = {"passed": True, "validation": validation, "calibration": calibration}
    except (ValueError, KeyError, TypeError) as exc:
        report = {"passed": False, "reason": str(exc), "calibration": calibration}
    Path("validation.json").write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    return {"score": float(report["passed"]), "artifact_paths": ["validation.json"], "cost_usd": 0.0,
            "feedback": report.get("reason", "ZIP cases and source-cited facts passed the calibrated oracle")}
