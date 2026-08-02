"""Tests for the top-level analyze_prose entry point."""

from prose_craft.analysis.metrics import ProseMetrics, analyze_prose


def test_empty_text_returns_none():
    assert analyze_prose("") is None


def test_short_clean_text():
    text = "The cat sat on the mat. The dog ran in the park."
    m = analyze_prose(text)
    assert isinstance(m, ProseMetrics)
    assert m.sentence_count == 2
    assert m.word_count > 0
    assert 0.0 <= m.germanic_pct <= 100.0


def test_metrics_rounds_decimals():
    text = "She walked home. He stayed inside. They laughed at the joke."
    m = analyze_prose(text)
    assert m.mean_sentence_length == round(m.mean_sentence_length, 1)
    assert m.sentence_length_std == round(m.sentence_length_std, 1)


def test_detects_monotony():
    # Six sentences all near 10 words
    text = " ".join(["The cat sat on the mat by the door today."] * 6)
    m = analyze_prose(text)
    assert m.monotony_zones >= 1
