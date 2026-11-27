"""Freeze independent native-skill canary inputs before source research begins."""

from pathlib import Path

from plugins.mission_control.learning_acceptance import validate_minimum_score
from plugins.mission_control.learning_runner import load_evaluation_cases


def freeze_admission(root, spec, occupied, freeze_inputs):
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ValueError("skill_admission must declare canary cases and an evaluator")
    files = freeze_inputs(root, spec, names=("cases_file", "evaluator"))
    cases = load_evaluation_cases(Path(files["cases_file"]["path"]), set())
    identities = [str(case["case_id"]) for case in cases]
    if not 1 <= len(identities) <= 5 or set(identities) & set(occupied):
        raise ValueError("skill canary requires 1-5 cases disjoint from development and transfer")
    minimum = validate_minimum_score(spec.get("minimum_score", 1.0))
    gain = validate_minimum_score(spec.get("minimum_gain", 0.01))
    if minimum <= 0 or gain <= 0:
        raise ValueError("skill canary requires positive correctness and improvement floors")
    return {"files": files, "case_ids": identities, "minimum_score": minimum, "minimum_gain": gain}
