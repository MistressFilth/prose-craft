"""Germanic vs. Latinate word origin classification + substitution table."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

GERMANIC_MARKERS: set[str] = {
    "blood", "bone", "skin", "heart", "gut", "hand", "foot", "eye", "ear",
    "head", "arm", "leg", "finger", "mouth", "tooth", "hair", "back", "neck",
    "kill", "strike", "break", "hold", "bring", "take", "give", "run", "fall",
    "walk", "go", "come", "get", "put", "make", "see", "know", "think", "feel",
    "say", "tell", "ask", "hear", "find", "show", "let", "leave", "keep",
    "begin", "end", "stand", "sit", "lie", "sleep", "wake", "eat", "drink",
    "die", "live", "love", "hate", "fear", "dread", "hope", "wrath", "shame",
    "glad", "sad", "earth", "water", "fire", "wind", "sun", "moon", "storm",
    "rain", "snow", "sky", "sea", "land", "wood", "stone", "hill", "field",
    "man", "woman", "child", "house", "home", "door", "window", "bed", "food",
    "day", "night", "year", "time", "life", "death", "word", "thing", "way",
    "good", "bad", "great", "small", "old", "new", "long", "short", "high",
    "low", "true", "dark", "light", "cold", "warm", "hard", "soft", "fast",
    "slow",
}

LATINATE_MARKERS: set[str] = {
    "utilize", "facilitate", "implement", "demonstrate", "indicate",
    "sufficient", "require", "obtain", "provide", "attempt", "commence",
    "conclude", "inquire", "respond", "observe", "reside", "purchase",
    "additional", "approximately", "subsequently", "concerning", "regarding",
    "assist", "construct", "manufacture", "transportation", "deceased",
    "perspiration", "consume", "endeavor", "numerous", "terminate", "initiate",
    "constitute", "establish", "determine", "significant", "appropriate",
    "necessary", "available", "possible",
}

LATINATE_SUFFIXES: list[str] = [
    "tion", "sion", "ment", "ity", "ance", "ence",
    "ous", "ious", "ive", "ative", "itive",
    "al", "ial", "ical", "able", "ible",
    "fy", "ify", "ize", "ate",
]


class SubstitutionRule(BaseModel):
    """A single Latinate -> Germanic substitution suggestion."""

    instead_of: str
    use: str
    note: str = ""


def classify_word_origin(word: str) -> Literal["germanic", "latinate", "unknown"]:
    """Classify a word as likely Germanic, Latinate, or unknown."""
    word = word.lower()
    if word in GERMANIC_MARKERS:
        return "germanic"
    if word in LATINATE_MARKERS:
        return "latinate"
    for suffix in LATINATE_SUFFIXES:
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return "latinate"
    if len(word) <= 4:
        return "germanic"
    from prose_craft.analysis.sentences import count_syllables
    if count_syllables(word) >= 4:
        return "latinate"
    return "unknown"