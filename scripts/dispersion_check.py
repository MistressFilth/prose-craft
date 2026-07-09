#!/usr/bin/env python3
"""dispersion_check.py -- cross-draft dispersion checker (v1).

Ported from workbench/reinhart/instrument/dispersion.py (validated research
algorithm; see workbench/reinhart/FINDINGS.md F6/F8 and
docs/superpowers/specs/2026-07-09-dispersion-checker-design.md for the
evidence and design this ships against).

Measures whether a set of same-brief/same-voice drafts have collapsed onto a
predictable region of style-space -- a token-blind, self-relative signal, not
a word list. No hardcoded semantic/taste/AI-tell vocabulary; the only
stopword set below is grammatical (articles, prepositions, pronouns,
auxiliaries, conjunctions), used purely to isolate content-word choices from
shared function words. This must never be extended into (or confused with)
the plugin's separate diction.banned corpo-speak lexicon -- that is a taste
stance; this is a structural convergence measurement.

Usage::

    python3 dispersion_check.py <draft1> <draft2> [<draft3> ...] [--json]

Order does not affect the computed signals -- measure_set treats the whole
list as one group, self-relative to its own other members. At least 2 paths
are required; dispersion is meaningless for a single draft.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import _counting as C  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Front-matter stripping (ported from workbench/reinhart/instrument/
# measure_bodies.py -- same leading '---\n...\n---\n' shape voice_check.py's
# _parse_draft already assumes elsewhere in this codebase).
# ---------------------------------------------------------------------------

_FRONT_MATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.DOTALL)


def strip_front_matter(text: str) -> str:
    """Strip a single leading '---\\n...\\n---\\n' YAML block, if present."""
    if not text.startswith("---"):
        return text
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return text
    return text[match.end() :]


# ---------------------------------------------------------------------------
# jaccard / word_trigrams (ported from workbench/reinhart/instrument/
# variation.py -- small enough to inline rather than add a shipped
# dependency on a research-only module outside main/'s git worktree).
# ---------------------------------------------------------------------------


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def word_trigrams(tokens: list[str]) -> set[tuple[str, str, str]]:
    return {tuple(tokens[i : i + 3]) for i in range(len(tokens) - 2)}


# ---------------------------------------------------------------------------
# GRAMMATICAL_STOPWORDS -- function words only. Normalization, not a
# semantic/taste filter: exists so content-word overlap signals measure
# *content* choices, not shared "the"/"and"/"you". See Global Constraints in
# docs/superpowers/plans/2026-07-09-dispersion-checker.md: never extend this
# into an AI-tell/taste blocklist.
# ---------------------------------------------------------------------------
GRAMMATICAL_STOPWORDS = frozenset(
    """
    a an the this that these those
    of in on at by for with about against between into through during
    before after above below to from up down over under again further
    then once here there all any both each few more most other some such
    no nor not only own same so than too very
    and but or yet nor
    i me my mine myself we us our ours ourselves you your yours yourself
    yourselves he him his himself she her hers herself it its itself
    they them their theirs themselves who whom whose which what
    as if because until while
    is am are was were be been being
    has have had having
    do does did doing done
    can could shall should will would may might must ought
    """.split()
)

_SECOND_PERSON_RE = re.compile(
    r"\b(you|your|yours|yourself|yourselves)\b", re.IGNORECASE
)

_SHORT_FRAGMENT_MAX_WORDS = 3
_OPENER_DELIMS = [",", ";", ":", "--", "—", ".", "!", "?"]

_BULLET_RE = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+\S", re.MULTILINE)
_HEADER_RE = re.compile(r"^[ \t]*#{1,6}[ \t]+\S", re.MULTILINE)
_BOLD_RE = re.compile(r"(\*\*[^*\n]+\*\*|__[^_\n]+__)")


def _content_words(text: str) -> list[str]:
    """Lowercased word tokens with GRAMMATICAL_STOPWORDS removed."""
    cleaned = C._strip_code(text)
    return [
        t.lower()
        for t in C.word_tokens(cleaned)
        if t.lower() not in GRAMMATICAL_STOPWORDS
    ]


def _mean_pairwise_jaccard(sets: list[set]) -> float:
    pairs = list(itertools.combinations(range(len(sets)), 2))
    if not pairs:
        return 0.0
    return C.mean([jaccard(sets[i], sets[j]) for i, j in pairs])


def _bucket_word_count(n: float, edges: tuple[int, int]) -> str:
    """Fixed, generic short/medium/long bucket -- NOT tuned to any corpus.
    Self-relative z-scoring degenerates at small N (a handful of drafts can
    produce spuriously "distinct" buckets even when a human reader would
    call them all short); see workbench/reinhart/instrument/dispersion.py's
    _bucket_word_count docstring for the full rationale. The dispersion
    CONCLUSION (the indices, the distinct-fraction/pairwise-Jaccard signals)
    stays fully self-relative -- only these bucket edges are fixed."""
    short_max, medium_max = edges
    if n <= short_max:
        return "short"
    if n <= medium_max:
        return "medium"
    return "long"


def _bucket_paragraph_count(n: int) -> str:
    if n <= 1:
        return "single"
    if n <= 4:
        return "few"
    return "many"


def _bucket_sentence_count(n: int) -> str:
    if n <= 10:
        return "few"
    if n <= 20:
        return "some"
    return "many"


def _content_jaccard(texts: list[str]) -> float:
    """Mean pairwise Jaccard of each draft's content-word *type* set."""
    type_sets = [set(_content_words(t)) for t in texts]
    return _mean_pairwise_jaccard(type_sets)


def _trigram_jaccard(texts: list[str]) -> float:
    """Mean pairwise Jaccard of each draft's word-trigram set."""
    token_lists = [C.word_tokens(C._strip_code(t)) for t in texts]
    lowered = [[tok.lower() for tok in toks] for toks in token_lists]
    trigram_sets = [word_trigrams(toks) for toks in lowered]
    return _mean_pairwise_jaccard(trigram_sets)


def _shared_mass(texts: list[str]) -> float:
    """Fraction of total content-word *tokens* whose *type* appears in at
    least ceil(N/2) drafts' type sets -- the "collapse onto a core
    vocabulary" signal."""
    n = len(texts)
    if n == 0:
        return 0.0
    per_draft_tokens = [_content_words(t) for t in texts]
    per_draft_types = [set(toks) for toks in per_draft_tokens]
    threshold = math.ceil(n / 2)

    type_draft_counts: dict[str, int] = {}
    for types in per_draft_types:
        for ty in types:
            type_draft_counts[ty] = type_draft_counts.get(ty, 0) + 1

    total_tokens = sum(len(toks) for toks in per_draft_tokens)
    if total_tokens == 0:
        return 0.0
    shared_tokens = sum(
        1
        for toks in per_draft_tokens
        for tok in toks
        if type_draft_counts.get(tok, 0) >= threshold
    )
    return shared_tokens / total_tokens


def _first_fragment(text: str) -> tuple[str, str]:
    """Scan for the first occurrence of any delimiter in _OPENER_DELIMS
    (textual order), returning (fragment_before_delimiter, delimiter)."""
    best_idx = None
    best_delim = ""
    for delim in _OPENER_DELIMS:
        idx = text.find(delim)
        if idx == -1:
            continue
        if best_idx is None or idx < best_idx:
            best_idx = idx
            best_delim = delim
    if best_idx is None:
        return text.strip(), ""
    return text[:best_idx], best_delim


def _opener_signals(text: str) -> dict[str, Any]:
    """Structural facts about a draft's opening, computed purely from
    punctuation/clause shape and word counts -- never from matching
    greeting/label words."""
    stripped = text.strip()
    sentences = C.split_sentences(stripped)
    first_sentence = sentences[0] if sentences else ""
    first_sentence_words = len(C.word_tokens(first_sentence))

    first_line = stripped.split("\n", 1)[0].rstrip()
    ends_with_colon = first_line.endswith(":")

    has_2nd_person_pron = bool(_SECOND_PERSON_RE.search(first_sentence))

    fragment, delim = _first_fragment(stripped)
    fragment_word_count = len(C.word_tokens(fragment))
    is_short_fragment = 0 < fragment_word_count <= _SHORT_FRAGMENT_MAX_WORDS

    is_label_colon_opener = is_short_fragment and delim == ":"
    is_greeting_shape = is_short_fragment and delim in (",", "--", "—")

    return {
        "first_sentence_words": first_sentence_words,
        "ends_with_colon": ends_with_colon,
        "has_2nd_person_pron": has_2nd_person_pron,
        "is_label_colon_opener": is_label_colon_opener,
        "is_greeting_shape": is_greeting_shape,
    }


_OPENER_LENGTH_EDGES = (10, 22)  # words: short <=10, medium 11-22, long >22


def _opener_frames(texts: list[str]) -> list[tuple]:
    raw = [_opener_signals(t) for t in texts]
    frames = []
    for r in raw:
        frames.append(
            (
                _bucket_word_count(r["first_sentence_words"], _OPENER_LENGTH_EDGES),
                r["ends_with_colon"],
                r["has_2nd_person_pron"],
                r["is_label_colon_opener"],
                r["is_greeting_shape"],
            )
        )
    return frames


def _structure_signals(text: str) -> dict[str, Any]:
    stripped = text.strip()
    paragraphs = C.split_paragraphs(stripped)
    sentences = C.split_sentences(stripped)
    sent_lens = [len(C.word_tokens(s)) for s in sentences]
    return {
        "paragraph_count": len(paragraphs),
        "has_headers": bool(_HEADER_RE.search(stripped)),
        "has_bullets": bool(_BULLET_RE.search(stripped)),
        "has_bold": bool(_BOLD_RE.search(stripped)),
        "sentence_count": len(sentences),
        "mean_sentence_len": C.mean(sent_lens) if sent_lens else 0.0,
    }


_STRUCTURE_LENGTH_EDGES = (12, 22)  # words/sentence: short <=12, medium 13-22, long >22


def _structure_sigs(texts: list[str]) -> list[tuple]:
    raw = [_structure_signals(t) for t in texts]
    sigs = []
    for r in raw:
        pb = _bucket_paragraph_count(r["paragraph_count"])
        sb = _bucket_sentence_count(r["sentence_count"])
        lb = _bucket_word_count(r["mean_sentence_len"], _STRUCTURE_LENGTH_EDGES)
        sigs.append(
            (
                pb,
                r["has_headers"],
                r["has_bullets"],
                r["has_bold"],
                sb,
                lb,
            )
        )
    return sigs


def _pairwise_field_similarity(sigs: list[tuple]) -> float:
    """Mean pairwise fraction of matching fields between same-shaped tuples
    (graded similarity, not just exact-tuple equality)."""
    pairs = list(itertools.combinations(range(len(sigs)), 2))
    if not pairs:
        return 0.0
    sims = []
    for i, j in pairs:
        a, b = sigs[i], sigs[j]
        matches = sum(1 for x, y in zip(a, b) if x == y)
        sims.append(matches / len(a))
    return C.mean(sims)


def measure_set(list_of_texts: list[str]) -> dict[str, Any]:
    """Measure a set of N same-brief/same-voice drafts (already
    front-matter-stripped prose bodies). Raises ValueError when fewer than
    2 drafts are given -- dispersion is meaningless for a single draft."""
    n = len(list_of_texts)
    if n < 2:
        raise ValueError("measure_set needs at least 2 drafts to be self-relative")

    content_jaccard = _content_jaccard(list_of_texts)
    trigram_jaccard = _trigram_jaccard(list_of_texts)
    shared_mass = _shared_mass(list_of_texts)

    opener_frames = _opener_frames(list_of_texts)
    distinct_opener_frames_fraction = len(set(opener_frames)) / n
    mean_opener_similarity = _pairwise_field_similarity(opener_frames)

    structure_sigs = _structure_sigs(list_of_texts)
    distinct_structure_sigs_fraction = len(set(structure_sigs)) / n
    mean_structural_similarity = _pairwise_field_similarity(structure_sigs)

    a1_overlap_signals = [content_jaccard, trigram_jaccard, shared_mass]
    a1_index = 1.0 - C.mean(a1_overlap_signals)

    a2_distinct_signals = [
        distinct_opener_frames_fraction,
        distinct_structure_sigs_fraction,
    ]
    a2_index = C.mean(a2_distinct_signals)

    return {
        "n": n,
        "altitude_1": {
            "content_jaccard": content_jaccard,
            "trigram_jaccard": trigram_jaccard,
            "shared_mass": shared_mass,
            "dispersion_index": a1_index,
        },
        "altitude_2": {
            "distinct_opener_frames_fraction": distinct_opener_frames_fraction,
            "mean_opener_similarity": mean_opener_similarity,
            "distinct_structure_sigs_fraction": distinct_structure_sigs_fraction,
            "mean_structural_similarity": mean_structural_similarity,
            "dispersion_index": a2_index,
        },
        "_raw": {
            "opener_frames": [list(f) for f in opener_frames],
            "structure_sigs": [list(s) for s in structure_sigs],
        },
    }


def load_texts_from_paths(paths: list[Path]) -> list[str]:
    """Read each path, strip a leading YAML front-matter block if present."""
    return [strip_front_matter(p.read_text(encoding="utf-8")) for p in paths]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="dispersion_check")
    parser.add_argument("drafts", nargs="+", help="paths to compare (>=2 required)")
    parser.add_argument("--json", action="store_true", help="emit JSON to stdout")
    args = parser.parse_args(argv)

    paths = [Path(p) for p in args.drafts]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        print(
            f"error: file(s) not found: {', '.join(str(p) for p in missing)}",
            file=sys.stderr,
        )
        return 2
    if len(paths) < 2:
        print("error: at least 2 drafts are required", file=sys.stderr)
        return 2

    texts = load_texts_from_paths(paths)
    try:
        profile = measure_set(texts)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    profile["files"] = [str(p) for p in paths]

    if args.json:
        print(json.dumps(profile, indent=2))
    else:
        a1 = profile["altitude_1"]
        a2 = profile["altitude_2"]
        print(f"n={profile['n']}")
        print(
            f"  content_jaccard={a1['content_jaccard']:.3f} "
            f"trigram_jaccard={a1['trigram_jaccard']:.3f} "
            f"shared_mass={a1['shared_mass']:.3f} "
            f"A1_index={a1['dispersion_index']:.3f}"
        )
        print(
            f"  distinct_opener_frames={a2['distinct_opener_frames_fraction']:.3f} "
            f"mean_opener_similarity={a2['mean_opener_similarity']:.3f}"
        )
        print(
            f"  distinct_structure_sigs={a2['distinct_structure_sigs_fraction']:.3f} "
            f"mean_structural_similarity={a2['mean_structural_similarity']:.3f} "
            f"A2_index={a2['dispersion_index']:.3f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
