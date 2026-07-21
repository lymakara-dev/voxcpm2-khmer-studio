from __future__ import annotations

from app.main import TTSRequest, _generate_kwargs
from app.tts_model import contains_khmer, safe_normalize_flag


def test_contains_khmer_detects_khmer_digits():
    assert contains_khmer("អាយុ២៥ឆ្នាំ")


def test_contains_khmer_false_for_latin_and_ascii_digits():
    assert not contains_khmer("hello 25 world")


def test_safe_normalize_flag_forces_off_for_khmer_when_requested():
    assert safe_normalize_flag("អាយុ២៥ឆ្នាំ", True) is False


def test_safe_normalize_flag_leaves_off_alone_for_khmer():
    assert safe_normalize_flag("អាយុ២៥ឆ្នាំ", False) is False


def test_safe_normalize_flag_untouched_for_non_khmer():
    assert safe_normalize_flag("hello 25 world", True) is True
    assert safe_normalize_flag("hello 25 world", False) is False


def test_generate_kwargs_disables_normalize_for_khmer_text():
    req = TTSRequest(text="អាយុ២៥ឆ្នាំ", normalize=True)
    assert _generate_kwargs(req)["normalize"] is False


def test_generate_kwargs_keeps_normalize_for_non_khmer_text():
    req = TTSRequest(text="hello world", normalize=True)
    assert _generate_kwargs(req)["normalize"] is True
