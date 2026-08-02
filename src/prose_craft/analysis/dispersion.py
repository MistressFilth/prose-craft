"""Cross-draft lexical + structural dispersion measurement."""

from __future__ import annotations

import re
from collections import Counter
from typing import Hashable, TypeVar

from pydantic import BaseModel

_WORD_RE = re.compile(r"\b[a-z]+\b")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_T = TypeVar("_T", bound=Hashable)


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) > 2}


def _trigrams(text: str) -> set[str]:
    tokens = _WORD_RE.findall(text.lower())
    return {" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)}


def _jaccard(a: set[_T], b: set[_T]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _mass_share(a: Counter[str], b: Counter[str]) -> float:
    """Fraction of a's tokens that also appear in b."""
    a_total = sum(a.values())
    if a_total == 0:
        return 0.0
    shared = sum(count for token, count in a.items() if b.get(token, 0) > 0)
    return shared / a_total


class DispersionAltitude1(BaseModel):
    content_jaccard: float
    trigram_jaccard: float
    shared_mass: float
    dispersion_index: float


class DispersionAltitude2(BaseModel):
    distinct_opener_frames_fraction: float
    mean_opener_similarity: float
    distinct_structure_sigs_fraction: float
    mean_structural_similarity: float
    dispersion_index: float


class DispersionProfile(BaseModel):
    n: int
    altitude_1: DispersionAltitude1
    altitude_2: DispersionAltitude2


def _opener_frame(text: str) -> str:
    """A coarse opener signature: first 3 content words lowercase."""
    tokens = _WORD_RE.findall(text)
    return " ".join(tokens[:3]).lower()


def _structure_sig(text: str) -> tuple[int, ...]:
    """Sentence-length signature rounded to nearest 5."""
    sents = _SENT_SPLIT_RE.split(text.strip())
    return tuple((len(_WORD_RE.findall(s)) // 5) for s in sents if s.strip())


def measure_set(new_draft: str, siblings: list[str]) -> DispersionProfile:
    """Score the new draft against same-voice same-directory siblings.

    Returns a DispersionProfile. n=1 when there are no siblings.
    """
    all_drafts = [new_draft] + list(siblings)
    n = len(all_drafts)

    if n == 1:
        return DispersionProfile(
            n=1,
            altitude_1=DispersionAltitude1(
                content_jaccard=0.0,
                trigram_jaccard=0.0,
                shared_mass=0.0,
                dispersion_index=0.0,
            ),
            altitude_2=DispersionAltitude2(
                distinct_opener_frames_fraction=0.0,
                mean_opener_similarity=0.0,
                distinct_structure_sigs_fraction=0.0,
                mean_structural_similarity=0.0,
                dispersion_index=0.0,
            ),
        )

    new_tokens = _tokens(new_draft)
    new_trigrams = _trigrams(new_draft)
    new_counter: Counter[str] = Counter(_WORD_RE.findall(new_draft.lower()))

    jaccards: list[float] = []
    trigram_jaccards: list[float] = []
    shared_masses: list[float] = []
    for sib in siblings:
        sib_tokens = _tokens(sib)
        sib_trigrams = _trigrams(sib)
        sib_counter: Counter[str] = Counter(_WORD_RE.findall(sib.lower()))
        jaccards.append(_jaccard(new_tokens, sib_tokens))
        trigram_jaccards.append(_jaccard(new_trigrams, sib_trigrams))
        shared_masses.append(_mass_share(new_counter, sib_counter))

    mean_jaccard = sum(jaccards) / len(jaccards) if jaccards else 0.0
    mean_trigram = sum(trigram_jaccards) / len(trigram_jaccards) if trigram_jaccards else 0.0
    mean_mass = sum(shared_masses) / len(shared_masses) if shared_masses else 0.0
    altitude_1_dispersion = 1.0 - (mean_jaccard + mean_trigram + mean_mass) / 3.0

    openers = [_opener_frame(d) for d in all_drafts]
    sigs = [_structure_sig(d) for d in all_drafts]
    distinct_openers = len(set(openers)) / n
    opener_pairs = [
        _jaccard(set(o1.split()), set(o2.split())) for o1 in openers for o2 in openers if o1 != o2
    ]
    mean_opener_sim = sum(opener_pairs) / len(opener_pairs) if opener_pairs else 0.0
    distinct_sigs = len(set(sigs)) / n
    sig_pairs = [_jaccard(set(s1), set(s2)) for s1 in sigs for s2 in sigs if s1 != s2]
    mean_struct_sim = sum(sig_pairs) / len(sig_pairs) if sig_pairs else 0.0
    altitude_2_dispersion = (
        distinct_openers + (1.0 - mean_opener_sim) + distinct_sigs + (1.0 - mean_struct_sim)
    ) / 4.0

    return DispersionProfile(
        n=n,
        altitude_1=DispersionAltitude1(
            content_jaccard=round(mean_jaccard, 3),
            trigram_jaccard=round(mean_trigram, 3),
            shared_mass=round(mean_mass, 3),
            dispersion_index=round(altitude_1_dispersion, 3),
        ),
        altitude_2=DispersionAltitude2(
            distinct_opener_frames_fraction=round(distinct_openers, 3),
            mean_opener_similarity=round(mean_opener_sim, 3),
            distinct_structure_sigs_fraction=round(distinct_sigs, 3),
            mean_structural_similarity=round(mean_struct_sim, 3),
            dispersion_index=round(altitude_2_dispersion, 3),
        ),
    )
