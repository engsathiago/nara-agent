"""Nara only advertises the configured product phrase."""

from tools.wake_word import wake_phrase


def test_product_phrase_does_not_depend_on_model_filename():
    for model in ("", "nara", "hey_nara"):
        cfg = {
            "provider": "openwakeword",
            "phrase": "Ei, Nara",
            "openwakeword": {"model": model},
        }
        assert wake_phrase(cfg) == "Ei, Nara"


def test_custom_detector_uses_its_configured_product_phrase(tmp_path):
    cfg = {
        "provider": "openwakeword",
        "phrase": "Ei, Nara",
        "openwakeword": {"model": str(tmp_path / "nara.tflite")},
    }
    assert wake_phrase(cfg) == "Ei, Nara"
