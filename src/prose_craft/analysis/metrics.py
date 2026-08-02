"""Top-level analyze_prose entry point."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from prose_craft.analysis.cohesion import (
    connectives_per_100,
    count_connectives,
)
from prose_craft.analysis.diction import classify_word_origin
from prose_craft.analysis.monotony import monotony_zones
from prose_craft.analysis.readability import flesch_reading_ease
from prose_craft.analysis.sentences import (
    count_syllables,
    tokenize_sentences,
    tokenize_words,
)


class ProseMetrics(BaseModel):
    sentence_count: int
    word_count: int
    mean_sentence_length: float
    sentence_length_std: float
    short_sentences_pct: float
    long_sentences_pct: float
    germanic_pct: float
    latinate_pct: float
    avg_syllables_per_word: float
    polysyllabic_pct: float
    flesch_reading_ease: float
    connectives_per_100_words: float
    causal_markers: int
    temporal_markers: int
    monotony_zones: int


def analyze_prose(text: str) -> ProseMetrics | None:
    """Compute the full ProseMetrics bundle for the given text.

    Returns None for empty text or text with no detectable sentences.
    """
    sentences = tokenize_sentences(text)
    words = tokenize_words(text)
    if not sentences or not words:
        return None

    sent_lengths = [len(tokenize_words(s)) for s in sentences]
    mean_len = sum(sent_lengths) / len(sent_lengths)
    variance = sum((n - mean_len) ** 2 for n in sent_lengths) / len(sent_lengths)
    std = variance**0.5

    short = sum(1 for n in sent_lengths if n < 10) / len(sent_lengths) * 100
    long_ = sum(1 for n in sent_lengths if n > 25) / len(sent_lengths) * 100

    origins = [classify_word_origin(w) for w in words if len(w) > 2]
    counts = Counter(origins)
    classified = counts["germanic"] + counts["latinate"]
    germanic = (counts["germanic"] / classified * 100) if classified else 50.0
    latinate = (counts["latinate"] / classified * 100) if classified else 50.0

    syllables = [count_syllables(w) for w in words]
    avg_syl = sum(syllables) / len(syllables) if syllables else 2.0
    poly = (
        sum(1 for s in syllables if s >= 3) / len(syllables) * 100 if syllables else 0.0
    )

    flesch = flesch_reading_ease(mean_len, avg_syl)
    connective_counts = count_connectives(text, words)
    conn_density = connectives_per_100(connective_counts, len(words))
    mono = len(monotony_zones(sent_lengths))

    return ProseMetrics(
        sentence_count=len(sentences),
        word_count=len(words),
        mean_sentence_length=round(mean_len, 1),
        sentence_length_std=round(std, 1),
        short_sentences_pct=round(short, 1),
        long_sentences_pct=round(long_, 1),
        germanic_pct=round(germanic, 1),
        latinate_pct=round(latinate, 1),
        avg_syllables_per_word=round(avg_syl, 2),
        polysyllabic_pct=round(poly, 1),
        flesch_reading_ease=flesch,
        connectives_per_100_words=conn_density,
        causal_markers=connective_counts.causal,
        temporal_markers=connective_counts.temporal,
        monotony_zones=mono,
    )
