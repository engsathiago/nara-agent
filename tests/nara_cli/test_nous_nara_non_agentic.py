"""Tests for the Nous-Nara-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"nara"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``nara-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "nara" tag namespace.

``is_nous_nara_non_agentic`` should only match the actual Nous Research
Nara-3 / Nara-4 chat family.
"""

from __future__ import annotations

import pytest

from nara_cli.model_switch import (
    _NARA_MODEL_WARNING,
    _check_nara_model_warning,
    is_nous_nara_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/Nara-3-Llama-3.1-70B",
        "NousResearch/Nara-3-Llama-3.1-405B",
        "nara-3",
        "Nara-3",
        "nara-4",
        "nara-4-405b",
        "nara_4_70b",
        "openrouter/nara3:70b",
        "openrouter/nousresearch/nara-4-405b",
        "NousResearch/Nara3",
        "nara-3.1",
    ],
)
def test_matches_real_nous_nara_chat_models(model_name: str) -> None:
    assert is_nous_nara_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Nara 3/4"
    )
    assert _check_nara_model_warning(model_name) == _NARA_MODEL_WARNING
