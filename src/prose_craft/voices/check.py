"""Voice-rule violation detection.

Three categories, matching the existing plugin taxonomy:

- **mechanical** — string/regex match (banned words, taboo phrases,
  preferred substitutions, mechanical never-list entries)
- **statistical** — count and compare to a numeric target
- **agent-required** — model-judged; surfaced as ``judgments_needed``
  placeholders for the voice-checker agent to resolve
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from prose_craft.analysis.sentences import tokenize_sentences, tokenize_words
from prose_craft.voices.model import VoiceProfile


class Violation(BaseModel):
    line: int | None = None
    col: int | None = None
    rule: str
    message: str
    category: Literal["mechanical", "statistical"]
    measured: float | str | None = None
    target: str | None = None
    band: str | None = None


class JudgmentNeeded(BaseModel):
    rule: str
    prompt: str


class VoiceVerdict(BaseModel):
    mechanical: list[Violation] = []
    statistical: list[Violation] = []
    judgments_needed: list[JudgmentNeeded] = []


_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")

_TOLERANCE_BANDS: dict[str, float] = {
    "strict": 0.5,
    "normal": 1.0,
    "relaxed": 2.0,
}


def _find_line_col(text: str, offset: int) -> tuple[int, int]:
    head = text[:offset]
    line = head.count("\n") + 1
    last_nl = head.rfind("\n")
    col = offset - last_nl if last_nl >= 0 else offset + 1
    return line, col


def _check_banned(text: str, profile: VoiceProfile) -> list[Violation]:
    out: list[Violation] = []
    for word in profile.diction.banned:
        for m in re.finditer(rf"\b{re.escape(word)}\b", text, re.IGNORECASE):
            line, col = _find_line_col(text, m.start())
            out.append(
                Violation(
                    line=line,
                    col=col,
                    rule="diction.banned",
                    message=f"banned word: {word!r}",
                    category="mechanical",
                )
            )
    return out


def _check_taboo(text: str, profile: VoiceProfile) -> list[Violation]:
    out: list[Violation] = []
    for phrase in profile.lexicon.taboo_phrases:
        for m in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            line, col = _find_line_col(text, m.start())
            out.append(
                Violation(
                    line=line,
                    col=col,
                    rule="lexicon.taboo_phrases",
                    message=f"taboo phrase: {phrase!r}",
                    category="mechanical",
                )
            )
    return out


def _check_preferred(text: str, profile: VoiceProfile) -> list[Violation]:
    out: list[Violation] = []
    for rule in profile.diction.preferred:
        for m in re.finditer(rf"\b{re.escape(rule.instead_of)}\b", text, re.IGNORECASE):
            line, col = _find_line_col(text, m.start())
            out.append(
                Violation(
                    line=line,
                    col=col,
                    rule="diction.preferred",
                    message=f"prefer {rule.use!r} over {rule.instead_of!r}: {rule.note}",
                    category="mechanical",
                )
            )
    return out


def _check_pet_phrases(text: str, profile: VoiceProfile, tolerance: str) -> list[Violation]:
    """Pet phrases recur by design. Flag over-saturation only.

    Band: more than 3x per 1000 words is over-saturated, scaled by
    tolerance (strict = 2x, normal = 3x, relaxed = 5x).
    """
    out: list[Violation] = []
    words = tokenize_words(text)
    if not words or not profile.lexicon.pet_phrases:
        return out
    text_lower = text.lower()
    band = {"strict": 2, "normal": 3, "relaxed": 5}[tolerance]
    for phrase in profile.lexicon.pet_phrases:
        count = text_lower.count(phrase.lower())
        density = count / len(words) * 1000
        if density > band:
            out.append(
                Violation(
                    rule="lexicon.pet_phrases",
                    message=f"pet phrase {phrase!r} appears {count} times ({density:.1f}/1k)",
                    category="statistical",
                    measured=round(density, 1),
                    target=f"<= {band}/1k",
                    band=tolerance,
                )
            )
    return out


def _check_sentence_length(text: str, profile: VoiceProfile, tolerance: str) -> list[Violation]:
    out: list[Violation] = []
    target = profile.rhythm.target_mean_sentence
    if not target:
        return out
    match = re.search(r"(\d+)\s*-\s*(\d+)", target)
    if not match:
        return out
    lo, hi = int(match.group(1)), int(match.group(2))
    sents = tokenize_sentences(text)
    if not sents:
        return out
    lengths = [len(tokenize_words(s)) for s in sents]
    mean = sum(lengths) / len(lengths)
    band = _TOLERANCE_BANDS[tolerance]
    if mean < lo - band or mean > hi + band:
        out.append(
            Violation(
                rule="rhythm.target_mean_sentence",
                message=f"mean sentence length {mean:.1f} outside band",
                category="statistical",
                measured=round(mean, 1),
                target=target,
                band=tolerance,
            )
        )
    return out


def check_voice(
    text: str,
    profile: VoiceProfile,
    *,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
) -> VoiceVerdict:
    """Run every check the profile enables and return a VoiceVerdict."""
    mechanical = (
        _check_banned(text, profile) + _check_taboo(text, profile) + _check_preferred(text, profile)
    )
    statistical = _check_pet_phrases(text, profile, tolerance) + _check_sentence_length(
        text, profile, tolerance
    )
    judgments = [
        JudgmentNeeded(
            rule=entry.rule,
            prompt=f"Judge whether the draft violates: {entry.rule}",
        )
        for entry in profile.never
        if entry.detection == "agent-required"
    ]
    return VoiceVerdict(
        mechanical=mechanical,
        statistical=statistical,
        judgments_needed=judgments,
    )
