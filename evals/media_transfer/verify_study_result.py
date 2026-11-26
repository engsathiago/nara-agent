"""Verify local generation and transfer artifacts without making model calls.

The printed summary contains hashes/counts, not the copyrighted source text.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from plugins.mission_control.learning_fabric import LearningFabric
from plugins.mission_control.learning_github_source import _check_cited_source


def _read_evidence(path, digest):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("archived evidence hash mismatch")
    return json.loads(raw)


def _verify_generation(root, study):
    fabric = LearningFabric(root / "plugin-data/mission-control/learning-fabric")
    stored = _read_evidence(study["evidence"]["path"], study["evidence"]["sha256"])
    if stored != {key: value for key, value in study.items() if key != "evidence"}:
        raise ValueError("study result differs from the archived response")
    digest = study["request_sha256"]
    request = _read_evidence(fabric.root / "sources" / digest[:2] / digest, digest)
    source = fabric.source(study["source_id"])
    _check_cited_source(source)
    if source["source_hash"] != request["source_hash"]:
        raise ValueError("study source changed")
    spans = request["input"]["source_spans"]
    by_id = {span["id"]: span for span in spans}
    if len(by_id) != len(spans):
        raise ValueError("duplicate source IDs")
    for span in spans:
        if source["extracted_text"][span["start"]:span["end"]] != span["text"]:
            raise ValueError("source excerpt does not match its archived offsets")
    generated = study["parsed"]
    candidate = study["candidate"]
    if candidate["steps"] != [step["instruction"].strip() for step in generated["steps"]]:
        raise ValueError("candidate was edited after generation")
    quotes = [by_id[step["source_span_id"]]["text"] for step in generated["steps"]]
    provenance = []
    for artifact in candidate["evidence_artifact_ids"]:
        digest = artifact.removeprefix("sha256:")
        path = fabric.root / "sources" / digest[:2] / digest
        if digest == source["source_hash"]:
            continue
        item = _read_evidence(path, digest)
        if item.get("kind") == "media_procedure_provenance":
            provenance.append(item)
    if len(provenance) != 1 or provenance[0]["quotes"] != quotes:
        raise ValueError("candidate citations differ from model-selected source excerpts")
    return request, candidate


def _verify_case(row, robots, steps):
    requests, scores, models = {}, {}, set()
    expected = [{**robot, "anchor": "above_character"} for robot in robots]
    for variant in ("baseline", "candidate"):
        evidence = row[variant + "_evidence"]
        if len(evidence) != 1:
            raise ValueError("expected one complete response artifact")
        artifact = _read_evidence(evidence[0]["path"], evidence[0]["sha256"])
        requests[variant] = artifact["request"]
        models.add(artifact["model_digest"])
        if json.loads(artifact["request"]["messages"][1]["content"]) != robots:
            raise ValueError("model input differs from reserved case")
        try:
            answer = json.loads(artifact["raw_response"]["message"]["content"])
        except json.JSONDecodeError:
            answer = None
        scores[variant] = (float(isinstance(answer, dict) and answer.get("refresh_seconds") == 20)
                           + float(isinstance(answer, dict) and answer.get("labels") == expected)) / 2
        if scores[variant] != row[variant]:
            raise ValueError("score differs from independent recomputation")
    baseline = requests["baseline"]["messages"][0]["content"]
    if requests["candidate"]["messages"][0]["content"] != baseline + "\nProcedimento estudado:\n" + "\n".join(steps):
        raise ValueError("evaluated procedure differs from generated candidate")
    requests["candidate"]["messages"][0]["content"] = baseline
    if requests["candidate"] != requests["baseline"]:
        raise ValueError("comparison changed more than the studied procedure")
    return scores["candidate"] - scores["baseline"], models


def _current_evaluation(root, candidate_id, original):
    path = root / "plugin-data/mission-control/learning/candidates" / f"{candidate_id}.eval.json"
    current = json.loads(path.read_bytes())
    if current == original:
        return current
    replay = json.loads((root / "minimum-score-recheck.json").read_bytes())
    if (replay["report"] != current or replay["new_model_calls"] != 0
            or replay["original_result_sha256"] != hashlib.sha256((root / "result.json").read_bytes()).hexdigest()):
        raise ValueError("current evaluation is not the archived-score replay")
    for key in ("candidate_id", "candidate_hash", "evaluator_sha256", "evaluator_path", "cases",
                "development_case_ids", "holdout_case_ids", "mean_delta", "regressions"):
        if current[key] != original[key]:
            raise ValueError("acceptance-floor replay changed observations or evaluator")
    return current


def verify(root):
    outcome = json.loads((root / "result.json").read_text(encoding="utf-8-sig"))
    study, report = outcome["study"], outcome["evaluation"]
    request, candidate = _verify_generation(root, study)
    protocol_path = Path(__file__).with_name("model_study_protocol.json")
    protocol = _read_evidence(protocol_path, outcome["protocol_sha256"])
    if request["input"]["objective"] != protocol["objective"]:
        raise ValueError("study objective differs from frozen protocol")
    candidate_hash = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode()).hexdigest()
    if report["candidate_hash"] != candidate_hash:
        raise ValueError("evaluation candidate changed")
    if hashlib.sha256(Path(report["evaluator_path"]).read_bytes()).hexdigest() != report["evaluator_sha256"]:
        raise ValueError("evaluator archive changed")
    inputs = {case["case_id"]: case["robots"] for case in protocol["cases"] if case["case_id"] != "development"}
    if set(inputs) != {row["case_id"] for row in report["cases"]} or len(inputs) != len(report["cases"]):
        raise ValueError("reserved cases differ from the frozen protocol")
    deltas, models = [], set()
    for row in report["cases"]:
        delta, digests = _verify_case(row, inputs[row["case_id"]], candidate["steps"])
        deltas.append(delta)
        models.update(digests)
    mean, regressions = sum(deltas) / len(deltas), sum(delta < 0 for delta in deltas)
    minimum = report.get("minimum_candidate_score", 0.0)
    passed = mean > 0 and regressions == 0 and all(row["candidate"] >= minimum for row in report["cases"])
    if len(models) != 1 or (mean, regressions, passed) != (report["mean_delta"], report["regressions"], report["passed"]):
        raise ValueError("model or aggregate result changed")
    current = _current_evaluation(root, candidate["candidate_id"], report)
    minimum = current.get("minimum_candidate_score", 0.0)
    below = [row["case_id"] for row in current["cases"] if row["candidate"] < minimum]
    current_passed = mean > 0 and regressions == 0 and not below
    if current["passed"] != current_passed or current.get("below_minimum", []) != below:
        raise ValueError("current minimum-score acceptance disagrees with observations")
    complete = all(row["candidate"] == 1.0 for row in report["cases"])
    persisted = json.loads((root / "plugin-data/mission-control/learning/candidates" / f"{candidate['candidate_id']}.json").read_bytes())
    if outcome["complete_convention"] != complete or list((root / "skills").glob("nara-learned-*")):
        raise ValueError("completion flag changed or a temporary skill remains active")
    if current_passed and complete:
        if persisted["status"] != "rolled_back" or not Path(outcome["rolled_back_skill"], "SKILL.md").is_file():
            raise ValueError("temporary promotion/rollback evidence is missing")
    elif persisted["status"] != "candidate":
        raise ValueError("partial or failed candidate must remain inactive")
    return {"candidate_id": candidate["candidate_id"], "steps": len(candidate["steps"]),
            "study_sha256": study["evidence"]["sha256"], "request_sha256": study["request_sha256"],
            "model_digest": next(iter(models)), "cases": len(deltas), "mean_delta": mean,
            "regressions": regressions, "original_evaluation_passed": passed,
            "minimum_candidate_score": minimum, "below_minimum": below,
            "passed": current_passed, "complete_convention": complete,
            "candidate_status": persisted["status"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    print(json.dumps(verify(parser.parse_args().profile), indent=2))
