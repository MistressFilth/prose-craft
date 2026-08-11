"""Cohesion marker counting and density."""

from __future__ import annotations

import re

from pydantic import BaseModel

CAUSAL_WORDS: set[str] = {
    "because",
    "since",
    "therefore",
    "thus",
    "hence",
    "so",
    "consequently",
    "accordingly",
    "as a result",
    "for this reason",
    "due to",
}
TEMPORAL_WORDS: set[str] = {
    "then",
    "next",
    "after",
    "before",
    "during",
    "while",
    "meanwhile",
    "subsequently",
    "previously",
    "finally",
    "eventually",
    "first",
    "second",
    "last",
    "when",
    "until",
}
ADDITIVE_WORDS: set[str] = {
    "and",
    "also",
    "moreover",
    "furthermore",
    "in addition",
    "additionally",
}
ADVERSATIVE_WORDS: set[str] = {
    "but",
    "however",
    "yet",
    "although",
    "though",
    "nevertheless",
    "nonetheless",
    "instead",
    "otherwise",
    "conversely",
    "on the other hand",
}


class ConnectiveCounts(BaseModel):
    causal: int = 0
    temporal: int = 0
    additive: int = 0
    adversative: int = 0


def count_connectives(text: str) -> ConnectiveCounts:
    """Count occurrences of each connective class in text.

    Uses word-boundary regex on the lowercase text. Returns zeros for
    empty text.
    """
    if not text:
        return ConnectiveCounts()
    lowered = text.lower()
    return ConnectiveCounts(
        causal=_count_set(lowered, CAUSAL_WORDS),
        temporal=_count_set(lowered, TEMPORAL_WORDS),
        additive=_count_set(lowered, ADDITIVE_WORDS),
        adversative=_count_set(lowered, ADVERSATIVE_WORDS),
    )


def _count_set(text: str, words: set[str]) -> int:
    total = 0
    for word in words:
        if " " in word:
            total += text.count(word)
        else:
            total += len(re.findall(rf"\b{re.escape(word)}\b", text))
    return total


def connectives_per_100(counts: ConnectiveCounts, word_count: int) -> float:
    """Total connectives per 100 words. Zero if word_count is zero."""
    if word_count == 0:
        return 0.0
    total = counts.causal + counts.temporal + counts.additive + counts.adversative
    return round(total / word_count * 100, 2)
