"""Tests for prose_craft.analysis.sentences."""

from prose_craft.analysis.sentences import count_syllables, tokenize_sentences, tokenize_words


def test_tokenize_sentences_splits_on_terminal_punctuation():
    text = "She walked home. He stayed. They laughed!"
    assert tokenize_sentences(text) == ["She walked home.", "He stayed.", "They laughed!"]


def test_tokenize_sentences_collapses_whitespace():
    text = "First sentence.\n\n  Second   sentence."
    assert tokenize_sentences(text) == ["First sentence.", "Second sentence."]


def test_tokenize_words_lowercases_and_strips_punctuation():
    assert tokenize_words("The quick, brown Fox.") == ["the", "quick", "brown", "fox"]


def test_count_syllables_basic():
    assert count_syllables("cat") == 1
    assert count_syllables("table") == 2
    assert count_syllables("beautiful") == 3


def test_count_syllables_silent_e():
    assert count_syllables("make") == 1
    assert count_syllables("code") == 1


def test_count_syllables_empty_returns_one():
    assert count_syllables("") == 1
