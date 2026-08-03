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
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from prose_craft.analysis.sentences import tokenize_sentences, tokenize_words
from prose_craft.voices.audience import ResolvedAudience
from prose_craft.voices.model import NeverEntry, VoiceProfile


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
    audience: ResolvedAudience | None = None

    @property
    def violations(self) -> list[Violation]:
        """All mechanical and statistical violations, concatenated."""
        return [*self.mechanical, *self.statistical]


_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]*\b")
_SHOUT_RE = re.compile(r"\b[A-Z]{2,}(?:\s+[A-Z]{2,})*\b")

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


def _check_sentence_length(text: str, profile: VoiceProfile, band: float) -> list[Violation]:
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
    if mean < lo - band or mean > hi + band:
        out.append(
            Violation(
                rule="rhythm.target_mean_sentence",
                message=f"mean sentence length {mean:.1f} outside band",
                category="statistical",
                measured=round(mean, 1),
                target=target,
                band=f"±{band}",
            )
        )
    return out


def _check_audience_never(text: str, audience: ResolvedAudience) -> list[Violation]:
    """Enforce mechanical never-list entries carried by the resolved audience.

    Audience-scoped never rules with ``detection="mechanical"`` are checked
    alongside the voice's own mechanical checks. Today the only mechanical
    pattern is "shouting" (an all-caps word/phrase); richer patterns can
    extend this function without changing its signature.
    """
    out: list[Violation] = []
    for entry in audience.never:
        if entry.detection != "mechanical":
            continue
        if "shout" in entry.rule.lower():
            for m in _SHOUT_RE.finditer(text):
                line, col = _find_line_col(text, m.start())
                out.append(
                    Violation(
                        line=line,
                        col=col,
                        rule=f"audience.never.{entry.rule}",
                        message=f"shouting detected: {m.group()!r}",
                        category="mechanical",
                    )
                )
    return out


def _check_surface_filter(
    text: str, audience: ResolvedAudience, surface: str | None
) -> list[Violation]:
    """Flag the surface as a violation when it appears in audience.surface_filter.close.

    Surfaces are simple string identifiers (e.g. "tweet", "memo", "rfc").
    The caller resolves the surface — from the file's extension, the
    ``--surface`` flag, or front-matter — and passes it in. A non-empty
    ``audience.surface_filter.close`` is a hard veto: any matching surface
    fails.
    """
    if surface is None or audience.surface_filter is None:
        return []
    close = audience.surface_filter.close or []
    if not close or surface not in close:
        return []
    return [
        Violation(
            rule=f"audience.surface_filter.close.{surface}",
            message=f"surface {surface!r} is closed for audience {audience.name!r}",
            category="mechanical",
        )
    ]


def _effective_band(tolerance: str, audience: ResolvedAudience | None) -> float:
    """Return the tolerance band, tightened by the audience's severity ceiling.

    Lower ceilings → tighter bands → more statistical violations fire.
    The ceiling of 5 leaves the band unchanged; ceiling 0 collapses the
    band to zero (every measurement at the boundary counts as a violation).
    """
    base = _TOLERANCE_BANDS[tolerance]
    if audience is None:
        return base
    return base * (audience.severity_ceiling / 5)


def _coerce_never_list(values: list[NeverEntry | str]) -> list[NeverEntry]:
    """Coerce bare strings to ``NeverEntry`` (defaulting to ``agent-required``).

    Mirrors the ``BeforeValidator`` on ``VoiceProfile.never`` so that callers
    (and the type checker) can treat the result as a homogeneous list of
    ``NeverEntry`` objects.
    """
    out: list[NeverEntry] = []
    for v in values:
        if isinstance(v, str):
            out.append(NeverEntry(rule=v))
        else:
            out.append(v)
    return out


def check_voice(
    text: str,
    profile: VoiceProfile,
    *,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
    brief_path: Path | None = None,
    audience: ResolvedAudience | None = None,
    surface: str | None = None,
) -> VoiceVerdict:
    """Run every check the profile enables and return a VoiceVerdict.

    When ``audience`` is supplied, the resolved severity ceiling tightens
    the tolerance band on statistical rules, mechanical entries from
    ``audience.never`` are enforced alongside the voice's own mechanical
    checks, and the target ``surface`` (when in
    ``audience.surface_filter.close``) is flagged.
    """
    band = _effective_band(tolerance, audience)
    mechanical = (
        _check_banned(text, profile) + _check_taboo(text, profile) + _check_preferred(text, profile)
    )
    if audience is not None:
        mechanical += _check_audience_never(text, audience)
        mechanical += _check_surface_filter(text, audience, surface)
    statistical = _check_pet_phrases(text, profile, tolerance) + _check_sentence_length(
        text, profile, band
    )
    seen: set[str] = set()
    judgments: list[JudgmentNeeded] = []
    sources: list[list[NeverEntry]] = [_coerce_never_list(profile.never)]
    if audience is not None:
        sources.append(audience.never)
    for source in sources:
        for entry in source:
            if entry.detection != "agent-required":
                continue
            if entry.rule in seen:
                continue
            seen.add(entry.rule)
            judgments.append(
                JudgmentNeeded(
                    rule=entry.rule,
                    prompt=f"Judge whether the draft violates: {entry.rule}",
                )
            )
    return VoiceVerdict(
        mechanical=mechanical,
        statistical=statistical,
        judgments_needed=judgments,
        audience=audience,
    )
