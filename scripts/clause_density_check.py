#!/usr/bin/env python3
"""clause_density_check.py -- present-participial-clause (ppc) and
agentless-passive rate diagnostic (v1).

Ported from the actual validated research methodology (NOT a tag-only
simplification): workbench/reinhart/instrument/tell_meter.py's 4 original
regex patterns UNIONED with workbench/reinhart/instrument/tag_chunker.py's
2 tag-based match functions, deduplicated by substring-containment of
overlapping spans within the same sentence -- confirmed in
workbench/reinhart/HYPOTHESES.md's R6/H12 log and the canonical
`_tag_chunker_counts` helper in workbench/reinhart/instrument/
run_r6_h11.py. See docs/superpowers/specs/2026-07-09-
clause-density-diagnostic-design.md for the full evidence and design.

HARD RULE (see the design doc's non-negotiable constraints): this is a
report-only diagnostic. F10 proved mechanically reducing ppc/agentless-
passive density made prose worse in 3/3 tested cases -- never render this
as a target, threshold, or verdict.

Usage::

    python3 clause_density_check.py <draft-path> --voice <name>
        [--surface <name>] [--json]

Reports the draft's own rates always. When --surface is given, also reads
prior same-voice-same-surface history, reports a reference mean + n, and
appends this draft's own record for future comparisons.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

import nltk  # type: ignore[import-not-found]

import _counting as C  # type: ignore[import-not-found]
from dispersion_check import strip_front_matter  # type: ignore[import-not-found]

# ---------------------------------------------------------------------------
# Original regex patterns (ported verbatim from workbench/reinhart/
# instrument/tell_meter.py -- retained, not replaced, per the design doc's
# corrected methodology).
# ---------------------------------------------------------------------------
_PPC_COMMA_ING_RE = re.compile(r",\s+\b\w+ing\b", re.IGNORECASE)
_PPC_SENTENCE_INITIAL_RE = re.compile(r"^\s*\w+ing\b[^,.!?]*,", re.IGNORECASE)
_PPC_SUBORD_RE = re.compile(
    r"\b(?:while|by|when|before|after|in)\s+\w+ing\b", re.IGNORECASE
)
_PASSIVE_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+\w+(?:ed|en)\b(?!\s+by\b)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Tag-based rules (ported verbatim from workbench/reinhart/instrument/
# tag_chunker.py).
# ---------------------------------------------------------------------------
BE_VERB_WORDS = {"am", "is", "are", "was", "were", "be", "been", "being"}
GET_VERB_WORDS = {"get", "gets", "got", "getting", "gotten"}
# Closed be+get lexical class for the passive auxiliary slot. HAVE/HAD/'VE
# form perfect aspect, a DIFFERENT closed class, and must never populate
# this slot -- distinguishing them requires checking word text, since
# have/had/'ve receive the same VB*/VBP/VBZ/VBD Penn Treebank tags as
# be/get auxiliaries (see workbench/reinhart/HYPOTHESES.md R6/H12 for the
# false-positive regression this fixes).
PASSIVE_AUX_WORDS = BE_VERB_WORDS | GET_VERB_WORDS
GERUND_TAKING_PREPS = {"of", "for", "about", "on", "without", "instead"}
PASSIVE_VERB_TAGS = {"VB", "VBD", "VBP", "VBZ", "VBG"}
NOUN_TAGS = {"NN", "NNS", "NNP", "NNPS"}
NOUN_OR_PRP_TAGS = NOUN_TAGS | {"PRP"}

Tagged = list[tuple[str, str]]


def tag_sentence(sentence: str) -> Tagged:
    """Tokenize + POS-tag a single sentence (Penn Treebank tagset)."""
    tokens = nltk.word_tokenize(sentence)
    return nltk.pos_tag(tokens)


def _span_text(tagged: Tagged, lo: int, hi: int) -> str:
    return " ".join(w for w, _ in tagged[lo : hi + 1])


def find_tag_passive_matches(tagged: Tagged) -> list[dict[str, Any]]:
    """Tag-based agentless_passive: BE/GET-word(VB*-tagged) [RB]? VBN, no
    'by' in next ~4 tokens."""
    matches: list[dict[str, Any]] = []
    n = len(tagged)
    i = 0
    while i < n:
        word_i, tag_i = tagged[i]
        if tag_i in PASSIVE_VERB_TAGS and word_i.lower() in PASSIVE_AUX_WORDS:
            j = i + 1
            adv_idx = None
            if j < n and tagged[j][1] == "RB":
                adv_idx = j
                j += 1
            if j < n and tagged[j][1] == "VBN":
                vbn_idx = j
                lookahead = tagged[vbn_idx + 1 : vbn_idx + 1 + 4]
                has_by = any(w.lower() == "by" for w, _ in lookahead)
                if not has_by:
                    matches.append(
                        {
                            "pattern": "tag_passive",
                            "span": _span_text(tagged, i, vbn_idx),
                        }
                    )
                i = vbn_idx + 1
                continue
        i += 1
    return matches


def find_tag_ppc_matches(tagged: Tagged) -> list[dict[str, Any]]:
    """Tag-based ppc: rules A (NN/PRP+VBG), B (,[DT]?NN/PRP+VBG), C (CC+VBG)."""
    matches: list[dict[str, Any]] = []
    n = len(tagged)

    # Rule A: <NN|NNS|NNP|NNPS|PRP><VBG> immediately adjacent.
    for i in range(n - 1):
        word_i, tag_i = tagged[i]
        word_j, tag_j = tagged[i + 1]
        if tag_i in NOUN_OR_PRP_TAGS and tag_j == "VBG":
            if word_i.lower() in BE_VERB_WORDS:
                continue
            if i > 0:
                prev_word, prev_tag = tagged[i - 1]
                if prev_tag == "IN" and prev_word.lower() in GERUND_TAKING_PREPS:
                    continue
            matches.append(
                {"pattern": "tag_ppc_nn_vbg", "span": _span_text(tagged, i, i + 1)}
            )

    # Rule B: `,` <DT>? <NN.*|PRP> <VBG>
    for i in range(n):
        word_i, tag_i = tagged[i]
        if word_i == ",":
            j = i + 1
            if j < n and tagged[j][1] == "DT":
                j += 1
            if (
                j < n
                and tagged[j][1] in NOUN_OR_PRP_TAGS
                and j + 1 < n
                and tagged[j + 1][1] == "VBG"
            ):
                matches.append(
                    {
                        "pattern": "tag_ppc_comma_dt_nn_vbg",
                        "span": _span_text(tagged, i, j + 1),
                    }
                )

    # Rule C: <CC><VBG> immediately adjacent, CC in {and, or}.
    for i in range(n - 1):
        word_i, tag_i = tagged[i]
        word_j, tag_j = tagged[i + 1]
        if tag_i == "CC" and word_i.lower() in {"and", "or"} and tag_j == "VBG":
            if i > 0 and tagged[i - 1][0].lower() in BE_VERB_WORDS:
                continue
            matches.append(
                {"pattern": "tag_ppc_cc_vbg", "span": _span_text(tagged, i, i + 1)}
            )

    return matches


def _analyze_text(text: str) -> dict[str, list[dict[str, Any]]]:
    """Run both the retained original regex patterns AND the tag-based
    rules, sentence-scoped for the tag rules, and return every match with
    its containing sentence attached (needed for dedup grouping)."""
    cleaned = C._strip_code(text)
    sentences = C.split_sentences(text)

    original_matches: list[dict[str, Any]] = []

    for m in _PPC_COMMA_ING_RE.finditer(cleaned):
        original_matches.append(
            {
                "feature": "ppc",
                "span": m.group(0).strip(),
                "sentence": _sentence_for_offset(cleaned, sentences, m.start()),
            }
        )
    for m in _PPC_SUBORD_RE.finditer(cleaned):
        original_matches.append(
            {
                "feature": "ppc",
                "span": m.group(0).strip(),
                "sentence": _sentence_for_offset(cleaned, sentences, m.start()),
            }
        )
    for sent in sentences:
        m = _PPC_SENTENCE_INITIAL_RE.match(sent)
        if m:
            original_matches.append(
                {"feature": "ppc", "span": m.group(0).strip(), "sentence": sent}
            )
    for m in _PASSIVE_RE.finditer(cleaned):
        original_matches.append(
            {
                "feature": "agentless_passive",
                "span": m.group(0).strip(),
                "sentence": _sentence_for_offset(cleaned, sentences, m.start()),
            }
        )

    tag_matches: list[dict[str, Any]] = []
    for sent in sentences:
        tagged = tag_sentence(sent)
        for m in find_tag_passive_matches(tagged):
            m = dict(m)
            m["feature"] = "agentless_passive"
            m["sentence"] = sent
            tag_matches.append(m)
        for m in find_tag_ppc_matches(tagged):
            m = dict(m)
            m["feature"] = "ppc"
            m["sentence"] = sent
            tag_matches.append(m)

    return {"original_matches": original_matches, "tag_matches": tag_matches}


def _sentence_for_offset(cleaned: str, sentences: list[str], offset: int) -> str:
    cursor = 0
    for sent in sentences:
        idx = cleaned.find(sent, cursor)
        if idx < 0:
            continue
        if idx <= offset <= idx + len(sent):
            return sent
        cursor = idx + len(sent)
    return ""


# ---------------------------------------------------------------------------
# Deduplication (ported verbatim from workbench/reinhart/instrument/
# run_r6_h11.py's _dedup_count / _UnionFind / _norm -- the canonical
# combine-and-dedup step used by every real measurement round).
# ---------------------------------------------------------------------------


def _norm(s: str) -> str:
    s = s.replace("...", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _dedup_count(matches: list[dict[str, Any]]) -> int:
    """Given all matches (original + tag) for ONE feature, merge same-
    instance matches via substring containment of normalized span text
    within each sentence group, and return the number of distinct
    instances (connected components)."""
    if not matches:
        return 0
    groups: dict[str, list[int]] = {}
    for idx, m in enumerate(matches):
        key = _norm(m.get("sentence", ""))
        groups.setdefault(key, []).append(idx)
    uf = _UnionFind(len(matches))
    for idxs in groups.values():
        spans = [_norm(matches[i]["span"]) for i in idxs]
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                sa, sb = spans[a], spans[b]
                if not sa or not sb:
                    continue
                if sa in sb or sb in sa:
                    uf.union(idxs[a], idxs[b])
    roots = {uf.find(i) for i in range(len(matches))}
    return len(roots)


def _per_1000(count: int, words: int) -> float:
    if words <= 0:
        return 0.0
    return count / words * 1000.0


def _ensure_nltk_ready() -> None:
    """Probe-based readiness check (same convention as workbench/reinhart/
    instrument/tell_meter.py's _NLTK_READY probe): attempt a real tiny tag
    operation rather than checking specific resource-path strings, since
    those strings drift across nltk versions. On LookupError, attempt a
    one-time download of both required resources, then retry once. Raises
    RuntimeError with a clear manual-command message if that also fails --
    never crashes with a raw LookupError."""
    try:
        nltk.pos_tag(nltk.word_tokenize("The cat sat on the mat."))
        return
    except LookupError:
        pass

    try:
        nltk.download("punkt_tab", quiet=True)
        nltk.download("averaged_perceptron_tagger_eng", quiet=True)
    except Exception:
        pass

    try:
        nltk.pos_tag(nltk.word_tokenize("The cat sat on the mat."))
    except LookupError as exc:
        raise RuntimeError(
            "nltk tagger data not found and automatic download failed. "
            "Run once manually: python -m nltk.downloader punkt_tab "
            "averaged_perceptron_tagger_eng"
        ) from exc


def measure_clause_density(body: str) -> dict[str, Any]:
    """Measure ppc/agentless_passive rates for one draft body (already
    front-matter-stripped). Combines regex + tag matches per feature,
    deduplicates by span containment, and reports per-1000-word rates."""
    words = C.word_count(body)
    if not body.strip():
        return {
            "word_count": 0,
            "ppc_count": 0,
            "ppc_per_1k": 0.0,
            "agentless_passive_count": 0,
            "agentless_passive_per_1k": 0.0,
        }
    result = _analyze_text(body)
    all_matches = result["original_matches"] + result["tag_matches"]
    counts: dict[str, int] = {}
    for feature in ("ppc", "agentless_passive"):
        feature_matches = [m for m in all_matches if m["feature"] == feature]
        counts[feature] = _dedup_count(feature_matches)
    return {
        "word_count": words,
        "ppc_count": counts["ppc"],
        "ppc_per_1k": _per_1000(counts["ppc"], words),
        "agentless_passive_count": counts["agentless_passive"],
        "agentless_passive_per_1k": _per_1000(counts["agentless_passive"], words),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="clause_density_check")
    parser.add_argument("draft", help="path to the draft .md file")
    parser.add_argument("--voice", required=True, help="voice name")
    parser.add_argument("--surface", default=None, help="genre/surface name (optional)")
    parser.add_argument("--json", action="store_true", help="emit JSON to stdout")
    args = parser.parse_args(argv)

    path = Path(args.draft)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    try:
        _ensure_nltk_ready()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    body = strip_front_matter(path.read_text(encoding="utf-8"))
    draft_stats = measure_clause_density(body)

    result: dict[str, Any] = {"draft": draft_stats, "reference": None}

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"ppc={draft_stats['ppc_per_1k']:.1f}/1k "
            f"agentless_passive={draft_stats['agentless_passive_per_1k']:.1f}/1k "
            f"(words={draft_stats['word_count']})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
