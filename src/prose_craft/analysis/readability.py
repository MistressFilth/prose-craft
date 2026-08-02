"""Flesch Reading Ease score."""

from __future__ import annotations


def flesch_reading_ease(mean_sentence_length: float, avg_syllables_per_word: float) -> float:
    """Compute the Flesch Reading Ease score, clamped to [0, 100]."""
    score = 206.835 - (1.015 * mean_sentence_length) - (84.6 * avg_syllables_per_word)
    return round(max(0.0, min(100.0, score)), 1)


def flesch_grade_level(score: float) -> str:
    """Return the approximate grade-level band for a Flesch score."""
    if score >= 90:
        return "5th grade (Very Easy)"
    if score >= 80:
        return "6th grade (Easy)"
    if score >= 70:
        return "7th grade (Fairly Easy)"
    if score >= 60:
        return "8th-9th grade (Standard)"
    if score >= 50:
        return "High school (Fairly Difficult)"
    if score >= 30:
        return "College (Difficult)"
    return "Graduate (Very Difficult)"
