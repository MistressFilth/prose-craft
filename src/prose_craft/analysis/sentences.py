"""Sentence, word, syllable tokenization."""

from __future__ import annotations

import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\b[a-zA-Z]+\b")
_VOWELS = "aeiouy"


def tokenize_sentences(text: str) -> list[str]:
    """Split text into sentences on terminal punctuation.

    Collapses all whitespace between sentences to a single space.
    Empty results are dropped.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def tokenize_words(text: str) -> list[str]:
    """Extract lowercase alphabetic words from text."""
    return [w.lower() for w in _WORD_RE.findall(text)]


def count_syllables(word: str) -> int:
    """Rough syllable count based on vowel groups.

    Adjusts for silent trailing 'e'. Returns 1 for empty input.
    """
    word = word.lower()
    if not word:
        return 1
    count = 0
    prev_was_vowel = False
    for char in word:
        is_vowel = char in _VOWELS
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    # Silent trailing 'e' is a common English heuristic, but 'e' after 'l'
    # forms its own syllable (table -> ta-ble, bottle -> bot-tle).
    if word.endswith("e") and not word.endswith("le") and count > 1:
        count -= 1
    return max(1, count)
