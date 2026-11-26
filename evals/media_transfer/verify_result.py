"""Recompute the archived result without calling a model."""

import hashlib
import json
from pathlib import Path


def verify(root: Path) -> dict:
    report = json.loads((root / "report.json").read_text(encoding="utf-8-sig"))
    for filename, key in (("office_labels.py", "evaluator_sha256"),
                          ("office_labels_cases.json", "cases_sha256"),
                          ("office_labels_candidate.json", "definition_sha256")):
        if hashlib.sha256((root.parent / filename).read_bytes()).hexdigest() != report[key]:
            raise ValueError(f"frozen protocol changed: {filename}")
    cases = json.loads((root.parent / "office_labels_cases.json").read_text(encoding="utf-8-sig"))["cases"]
    inputs = {case["case_id"]: case["robots"] for case in cases if case["case_id"] != "development"}
    definition = json.loads((root.parent / "office_labels_candidate.json").read_text(encoding="utf-8-sig"))
    if set(inputs) != {row["case_id"] for row in report["cases"]}:
        raise ValueError("reserved cases differ from the frozen protocol")
    deltas = []
    digests = set()
    for row in report["cases"]:
        robots = inputs[row["case_id"]]
        expected = [{**robot, "anchor": "above_character"} for robot in robots]
        scores = {}
        requests = {}
        for variant in ("baseline", "candidate"):
            artifacts = row[variant + "_evidence"]
            if len(artifacts) != 1:
                raise ValueError("expected one complete model evidence artifact")
            artifact = artifacts[0]
            raw = (root / artifact["path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != artifact["sha256"]:
                raise ValueError("model evidence changed")
            evidence = json.loads(raw)
            requests[variant] = evidence["request"]
            digests.add(evidence["model_digest"])
            if json.loads(evidence["request"]["messages"][1]["content"]) != robots:
                raise ValueError("model did not receive the reserved input")
            answer = json.loads(evidence["raw_response"]["message"]["content"])
            score = (float(answer.get("refresh_seconds") == 20)
                     + float(answer.get("labels") == expected)) / 2
            if score != row[variant]:
                raise ValueError("recorded score differs from independently recomputed score")
            scores[variant] = score
        baseline_prompt = requests["baseline"]["messages"][0]["content"]
        expected_prompt = baseline_prompt + "\nProcedimento estudado:\n" + "\n".join(definition["steps"])
        if requests["candidate"]["messages"][0]["content"] != expected_prompt:
            raise ValueError("candidate prompt differs from frozen procedure")
        requests["candidate"]["messages"][0]["content"] = baseline_prompt
        if requests["baseline"] != requests["candidate"]:
            raise ValueError("comparison changed more than the studied procedure")
        deltas.append(scores["candidate"] - scores["baseline"])
    if len(digests) != 1:
        raise ValueError("model changed across comparisons")
    mean = sum(deltas) / len(deltas)
    regressions = sum(value < 0 for value in deltas)
    if mean != report["mean_delta"] or regressions != report["regressions"]:
        raise ValueError("aggregate result differs")
    return {"cases": len(deltas), "mean_delta": mean, "regressions": regressions,
            "passed": mean > 0 and regressions == 0, "model_digest": next(iter(digests))}


if __name__ == "__main__":
    print(json.dumps(verify(Path(__file__).parent / "result_2026_11_26"), indent=2))
