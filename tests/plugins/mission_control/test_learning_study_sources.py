"""Source citations retain exact Unicode offsets instead of model-copied text."""

import pytest

from plugins.mission_control.learning_study_sources import resolve_proposal, source_spans


def test_long_unicode_source_keeps_all_content_and_exact_citations():
    text = "\nOlá, ação!\n" + ("ação🚀 " * 700) + "\nSame. Same.\n"
    spans = source_spans(text)
    assert len({item["id"] for item in spans}) == len(spans)
    assert "".join("".join(span["text"].split()) for span in spans) == "".join(text.split())
    for span in spans:
        assert text[span["start"]:span["end"]] == span["text"]
        assert 0 < len(span["text"]) <= 1200
    chosen = spans[-1]
    procedure = resolve_proposal({
        "name": "Repeat", "steps": [{"instruction": "Repeat the instruction", "source_span_id": chosen["id"]}],
        "decline_reason": "",
    }, spans)
    assert procedure["quotes"] == [text[chosen["start"]:chosen["end"]]]


def test_fragmented_transcript_does_not_explode_evidence_catalog():
    text = "A.\n" * 16000
    spans = source_spans(text)
    assert len(spans) <= 128
    assert "".join(span["text"] for span in spans) == text


@pytest.mark.parametrize("step", [
    {"instruction": "do it", "source_span_id": "s9999"},
    {"instruction": "do it", "source_span_id": []},
    {"instruction": "do it", "source_span_id": "s0000", "quote": "fabricated"},
    {"instruction": "first\nsecond", "source_span_id": "s0000"},
])
def test_unknown_evidence_and_model_supplied_quotes_are_rejected(step):
    with pytest.raises(ValueError):
        resolve_proposal({"name": "Test", "steps": [step], "decline_reason": ""}, source_spans("Real evidence."))
