"""Resolve model-selected evidence IDs to exact archived source substrings."""

from __future__ import annotations

import re
from typing import Any


def source_spans(text: str) -> list[dict[str, Any]]:
    """Character offsets preserve original spelling, Unicode and repeated text."""
    spans = []
    for sentence in re.finditer(r".+?(?:[.!?](?=\s|$)|\n|$)", text, flags=re.DOTALL):
        for start in range(sentence.start(), sentence.end(), 1200):
            end = min(start + 1200, sentence.end())
            content = text[start:end]
            if content.strip():
                spans.append({"id": f"s{len(spans):04d}", "start": start, "end": end, "text": content})
    if len(spans) > 128:
        # Highly fragmented transcripts must not multiply the prompt/schema without bound.
        spans = [{"id": f"s{index:04d}", "start": start, "end": min(start + 1200, len(text)),
                  "text": text[start:start + 1200]}
                 for index, start in enumerate(range(0, len(text), 1200))
                 if text[start:start + 1200].strip()]
    return spans


def proposal_schema(spans: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "name": {"type": "string", "maxLength": 120},
            "steps": {"type": "array", "maxItems": 12, "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "instruction": {"type": "string", "minLength": 1, "maxLength": 500},
                    "source_span_id": {"type": "string", "enum": [span["id"] for span in spans]},
                }, "required": ["instruction", "source_span_id"],
            }},
            "decline_reason": {"type": "string", "maxLength": 1000},
        }, "required": ["name", "steps", "decline_reason"],
    }


def resolve_proposal(parsed: Any, spans: list[dict[str, Any]]) -> dict[str, Any]:
    # The host's JSON Schema validator is optional; the domain always checks IDs/types.
    if not isinstance(parsed, dict) or set(parsed) != {"name", "steps", "decline_reason"}:
        raise ValueError("study response must contain name, steps and decline_reason")
    name, items, reason = parsed["name"], parsed["steps"], parsed["decline_reason"]
    if (not isinstance(name, str) or len(name) > 120 or "\n" in name or "\r" in name
            or not isinstance(reason, str) or len(reason) > 1000):
        raise ValueError("study name and decline_reason must be bounded text")
    if not isinstance(items, list) or len(items) > 12:
        raise ValueError("study steps must be a list of at most 12 cited instructions")
    if not items and not reason.strip():
        raise ValueError("declined study requires a reason")
    if items and (reason.strip() or not name.strip()):
        raise ValueError("study proposal requires a name and an empty decline_reason")
    evidence = {span["id"]: span["text"] for span in spans}
    steps, quotes = [], []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"instruction", "source_span_id"}:
            raise ValueError("each study step requires instruction and source_span_id")
        step, source_id = item["instruction"], item["source_span_id"]
        if (not isinstance(step, str) or not step.strip() or len(step) > 500
                or "\n" in step or "\r" in step):
            raise ValueError("study instruction must be one line of 1-500 characters")
        if not isinstance(source_id, str) or source_id not in evidence:
            raise ValueError("study source_span_id is not in the supplied evidence")
        steps.append(step)
        quotes.append(evidence[source_id])
    return {"name": name, "steps": steps, "quotes": quotes, "decline_reason": reason}
