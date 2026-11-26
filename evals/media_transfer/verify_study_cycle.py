"""Replay archived study-cycle evidence without generating or evaluating again."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def checked_json(path, digest=None):
    content = Path(path).read_bytes()
    if digest is not None and hashlib.sha256(content).hexdigest() != digest:
        raise ValueError(f"evidence hash mismatch: {path}")
    return json.loads(content)


def _source_text(root, request):
    database = root / "plugin-data/mission-control/learning-fabric/learning-fabric.db"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM learning_sources WHERE source_id=?",
                           (request["source_id"],)).fetchone()
    assert row["source_hash"] == request["source_hash"]
    assert hashlib.sha256(Path(row["stored_path"]).read_bytes()).hexdigest() == row["source_hash"]
    transcript = Path(row["transcript_path"]).read_bytes()
    assert hashlib.sha256(transcript).hexdigest() == row["transcript_hash"]
    assert transcript.decode("utf-8", errors="replace") == row["extracted_text"]
    return row["extracted_text"]


def _score(row, case, variant, candidate, digests):
    artifacts = row["evidence"] if "evidence" in row else row[f"{variant}_evidence"]
    if len(artifacts) != 1:
        raise ValueError("office evaluator requires one observation artifact")
    artifact = artifacts[0]
    proof = checked_json(artifact["path"], artifact["sha256"])
    assert proof["case_id"] == case["case_id"]
    digests.add(proof["model_digest"])
    body = proof["request"]
    assert json.loads(body["messages"][1]["content"]) == case["robots"]
    prompt = body["messages"][0]["content"]
    if variant == "candidate":
        assert prompt.endswith("\n".join(candidate["steps"]))
    else:
        assert "Procedimento estudado:" not in prompt
    try:
        answer = json.loads(proof["raw_response"]["message"]["content"])
    except (KeyError, json.JSONDecodeError):
        answer = {}
    labels = [{"id": robot["id"], "balance": robot["balance"], "anchor": "above_character"}
              for robot in case["robots"]]
    checks = [isinstance(answer, dict) and answer.get("refresh_seconds") == 20,
              isinstance(answer, dict) and answer.get("labels") == labels]
    score = sum(checks) / 2
    assert score == (row["score"] if "score" in row else row[variant])
    return score


def verify(root):
    result = checked_json(root / "cycle.stdout")
    receipt = checked_json(result["receipt_path"], result["receipt_sha256"])
    assert receipt == {key: value for key, value in result.items()
                       if key not in {"receipt_path", "receipt_sha256"}}
    request = checked_json(result["request_path"], result["request_sha256"])
    source_text = _source_text(root, request)
    cases = {str(case["case_id"]): case for case in request["cases"]}
    development = request["plan"]["development_case_ids"]
    holdouts = request["plan"]["holdout_case_ids"]
    assert not set(development) & set(holdouts)
    assert result["generation_calls_started"] <= request["max_generation_calls"]
    assert result["evaluator_calls_started"] <= request["max_evaluator_calls"]
    fabric = root / "plugin-data/mission-control/learning-fabric/sources"
    candidates = root / "plugin-data/mission-control/learning/candidates"
    last = None
    models = set()
    for attempt in result["attempts"]:
        ev = attempt["generation_evidence"]
        generation = checked_json(ev["path"], ev["sha256"])
        digest = generation["request_sha256"]
        study = checked_json(fabric / digest[:2] / digest, digest)
        assert study["source_id"] == request["source_id"] and study["source_hash"] == request["source_hash"]
        assert generation["model"] == request["system"]["model"]
        model_input = study["input"]
        for span in model_input["source_spans"]:
            assert span["text"] == source_text[span["start"]:span["end"]]
        assert model_input["objective"] == request["plan"]["objective"]
        if last is None:
            assert "development_feedback" not in model_input
        else:
            expected = {"previous_steps": last["candidate"]["steps"], "cases": [
                {key: row[key] for key in ("case_id", "case", "score", "feedback") if key in row}
                for row in last["practice"]]}
            assert model_input["development_feedback"] == expected
        if attempt["candidate_id"] is None:
            continue
        candidate = checked_json(candidates / f"{attempt['candidate_id']}.json")
        assert candidate["status"] == "candidate"
        assert candidate["steps"] == [item["instruction"] for item in generation["parsed"]["steps"]]
        assert generation["candidate"]["candidate_id"] == candidate["candidate_id"]
        assert [row["case_id"] for row in attempt["practice"]] == development
        for row in attempt["practice"]:
            assert row["case"] == cases[row["case_id"]]
            _score(row, cases[row["case_id"]], "candidate", candidate, models)
        last = {"candidate": candidate, "practice": attempt["practice"]}
    transfer = result["transfer"]
    scores = []
    if transfer is not None:
        evaluation = transfer["evaluation"]
        assert evaluation["holdout_case_ids"] == holdouts
        assert evaluation["minimum_candidate_score"] == request["plan"]["minimum_candidate_score"]
        for row in evaluation["cases"]:
            case = cases[row["case_id"]]
            baseline = _score(row, case, "baseline", last["candidate"], models)
            candidate = _score(row, case, "candidate", last["candidate"], models)
            scores.append({"case_id": row["case_id"], "baseline": baseline, "candidate": candidate})
        minimum = request["plan"]["minimum_candidate_score"]
        passed = (sum(row["candidate"] - row["baseline"] for row in scores) > 0
                  and all(row["candidate"] >= max(minimum, row["baseline"]) for row in scores))
        assert evaluation["passed"] == passed
        assert transfer["competence"]["passed"] == passed
    assert len(models) <= 1
    assert not list((root / "skills").glob("nara-learned-*"))
    return {"status": result["status"], "generation_calls": result["generation_calls_started"],
            "evaluator_calls": result["evaluator_calls_started"],
            "practice_scores": [[row["score"] for row in attempt["practice"]]
                                for attempt in result["attempts"]],
            "reserved_scores": scores, "model_digests": sorted(models),
            "receipts_verified": True, "skill_activated": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    print(json.dumps(verify(parser.parse_args().profile), indent=2))
