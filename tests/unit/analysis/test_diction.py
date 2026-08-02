"""Tests for prose_craft.analysis.diction."""

from prose_craft.analysis.diction import (
    LATINATE_SUFFIXES,
    SubstitutionRule,
    classify_word_origin,
)


def test_classify_explicit_germanic():
    assert classify_word_origin("blood") == "germanic"
    assert classify_word_origin("hand") == "germanic"


def test_classify_explicit_latinate():
    assert classify_word_origin("utilize") == "latinate"
    assert classify_word_origin("facilitate") == "latinate"


def test_classify_by_suffix():
    assert classify_word_origin("communication") == "latinate"
    assert classify_word_origin("movement") == "latinate"


def test_classify_short_word_is_germanic():
    assert classify_word_origin("run") == "germanic"
    assert classify_word_origin("cat") == "germanic"


def test_classify_polysyllabic_unknown_is_latinate():
    assert classify_word_origin("perspicacious") == "latinate"


def test_classify_unknown():
    assert classify_word_origin("onomatopoeia") in ("latinate", "unknown")


def test_latinate_suffixes_constant():
    assert "tion" in LATINATE_SUFFIXES
    assert "ment" in LATINATE_SUFFIXES
    assert "ity" in LATINATE_SUFFIXES


def test_substitution_rule_model():
    rule = SubstitutionRule(instead_of="utilize", use="use", note="prefer Germanic")
    assert rule.instead_of == "utilize"
    assert rule.use == "use"