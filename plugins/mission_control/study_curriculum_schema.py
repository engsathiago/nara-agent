"""Bound generated teaching material and keep exercise groups out of reserved splits."""

import json

from plugins.mission_control.learning_acceptance import validate_minimum_score
from plugins.mission_control.study_checkpoint import read_checkpoint
from plugins.mission_control.study_payload_schema import payload_schema, validate_payload
from plugins.mission_control.study_teaching_schema import apply_schema, resolve_teaching, teaching_schema


SPLITS = {"development": 10, "transfer": 20, "canary": 5}


def freeze_curriculum(root, spec, freeze_inputs):
    if not isinstance(spec, dict):
        raise ValueError("curriculum must declare a brief, validator and native canary evaluator")
    limit = spec.get("max_generations", 1)
    if type(limit) is not int or not 1 <= limit <= 3:
        raise ValueError("curriculum max_generations must be an integer from 1 to 3")
    references = {}
    for name, source in (("brief", spec["brief_file"]), ("validator", spec["validator"]),
                         ("canary_evaluator", spec["canary_evaluator"])):
        field = "system_file" if name == "brief" else "evaluator"
        references[name] = freeze_inputs(root, {field: source}, names=(field,))[field]
    brief = read_checkpoint(references["brief"])
    if not isinstance(brief, dict) or not brief or len(json.dumps(brief)) > 16000:
        raise ValueError("curriculum brief must be a nonempty object of at most 16000 characters")
    schema = payload_schema(brief)
    teaching = teaching_schema(brief)
    score = validate_minimum_score(spec.get("minimum_score", 1.0))
    gain = validate_minimum_score(spec.get("minimum_gain", 0.01))
    if score <= 0 or gain <= 0:
        raise ValueError("curriculum admission floors must be positive")
    frozen = {"files": references, "minimum_score": score, "minimum_gain": gain}
    if teaching is not None:
        frozen["teaching_format"] = teaching["mode"]
    if schema is not None:
        frozen["payload_format"] = "typed-object-v1"
    if "max_generations" in spec:
        frozen["max_generations"] = limit
    return frozen


def curriculum_version(spec):
    if spec.get("teaching_format") == "source-span-v1":
        return 8
    if "max_generations" in spec:
        return 7
    if spec.get("payload_format") == "typed-object-v1":
        return 6
    return 4


def curriculum_schema(spans, payload_contract=None, teaching_contract=None):
    field = "payload" if payload_contract is not None else "payload_json"
    text = {"type": "string", "minLength": 1, "maxLength": 2000}
    question = {"type": "object", "additionalProperties": False, "properties": {
        "question": text, "answer": text,
        "source_span_ids": {"type": "array", "minItems": 1, "maxItems": 3,
                            "items": {"type": "string", "enum": [span["id"] for span in spans]}},
    }, "required": ["question", "answer", "source_span_ids"]}
    case = {"type": "object", "additionalProperties": False, "properties": {
        "case_id": {"type": "string", "minLength": 1, "maxLength": 120},
        "split": {"type": "string", "enum": list(SPLITS)},
        "group_id": {"type": "string", "minLength": 1, "maxLength": 120},
        field: payload_contract if payload_contract is not None else {"type": "string", "minLength": 2, "maxLength": 8000},
    }, "required": ["case_id", "split", "group_id", field]}
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "explanation": {"type": "string", "maxLength": 4000},
        "questions": {"type": "array", "maxItems": 5, "items": question},
        "cases": {"type": "array", "maxItems": 35, "items": case},
        "decline_reason": {"type": "string", "maxLength": 1000},
    }, "required": ["explanation", "questions", "cases", "decline_reason"]}
    return apply_schema(schema, spans, teaching_contract)


def _text(value, limit, label):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"curriculum {label} must be nonempty text of at most {limit} characters")
    return value


def _questions(items, spans):
    if not isinstance(items, list) or not 1 <= len(items) <= 5:
        raise ValueError("curriculum requires 1-5 source-grounded questions")
    by_id = {span["id"]: span for span in spans}
    resolved = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"question", "answer", "source_span_ids"}:
            raise ValueError("curriculum question must include answer and source spans")
        ids = item["source_span_ids"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 3
                or any(not isinstance(key, str) or key not in by_id for key in ids) or len(set(ids)) != len(ids)):
            raise ValueError("curriculum question must cite distinct supplied source spans")
        resolved.append({"question": _text(item["question"], 2000, "question"),
                         "answer": _text(item["answer"], 2000, "answer"),
                         "citations": [by_id[key] for key in ids]})
    return resolved


def _payload(item, contract):
    if contract is None:
        return json.loads(_text(item["payload_json"], 8000, "payload_json"))
    value = item["payload"]
    validate_payload(value, contract)
    if len(json.dumps(value, sort_keys=True, allow_nan=False)) > 8000:
        raise ValueError("curriculum payload exceeds 8000 serialized characters")
    return value


def _cases(items, payload_contract=None):
    field = "payload" if payload_contract is not None else "payload_json"
    if not isinstance(items, list) or not 3 <= len(items) <= 35:
        raise ValueError("curriculum requires separate development, transfer and canary cases")
    resolved, identities, groups, payloads = [], set(), {}, set()
    counts = dict.fromkeys(SPLITS, 0)
    for item in items:
        if not isinstance(item, dict) or set(item) != {"case_id", "split", "group_id", field}:
            raise ValueError("curriculum case requires identity, split, group and JSON payload")
        identity = _text(item["case_id"], 120, "case_id")
        group = _text(item["group_id"], 120, "group_id").strip().casefold()
        split = item["split"]
        if not isinstance(split, str) or split not in SPLITS or identity in identities:
            raise ValueError("curriculum has a duplicate identity or unknown split")
        payload = _payload(item, payload_contract)
        if not isinstance(payload, dict) or not payload or "case_id" in payload:
            raise ValueError("curriculum payload must be an object without case_id")
        canonical = json.dumps(payload, sort_keys=True, allow_nan=False)
        if canonical in payloads or (group in groups and groups[group] != split):
            raise ValueError("curriculum repeats a case or leaks a group across splits")
        identities.add(identity)
        groups[group] = split
        payloads.add(canonical)
        counts[split] += 1
        resolved.append({"case_id": identity, "split": split, "group_id": group, "payload": payload})
    if any(not 1 <= counts[split] <= limit for split, limit in SPLITS.items()):
        raise ValueError("curriculum split counts exceed the declared bounds")
    return resolved


def resolve_curriculum(parsed, spans, payload_contract=None, teaching_contract=None):
    parsed = resolve_teaching(parsed, spans, teaching_contract)
    if not isinstance(parsed, dict) or set(parsed) != {"explanation", "questions", "cases", "decline_reason"}:
        raise ValueError("curriculum requires explanation, questions, cases and decline_reason")
    reason = parsed["decline_reason"]
    if not isinstance(reason, str) or len(reason) > 1000:
        raise ValueError("curriculum decline reason exceeds its bounds")
    if reason.strip():
        raise ValueError("curriculum declined: " + reason)
    material = {"explanation": _text(parsed["explanation"], 4000, "explanation"),
                "questions": _questions(parsed["questions"], spans)}
    if len(json.dumps(material, ensure_ascii=False)) > 16000:
        raise ValueError("curriculum teaching material exceeds 16000 characters")
    return {"teaching_material": material, "cases": _cases(parsed["cases"], payload_contract)}
