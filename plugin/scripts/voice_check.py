"""Check a draft against a voice profile.

Reads a draft and a parsed voice profile, runs every mechanical and
statistical rule from 08-voice-checker-rules.md, and emits the JSON
violation report defined there.

Categories:
- mechanical: regex / string match against the draft
- statistical: count vs target with tolerance
- agent-required: emit a `judgments_needed` placeholder; the
  voice-checker agent supplies the verdict

Usage::

    python3 voice_check.py <draft-path> [--voice <name>] [--json]

When `--voice` is omitted, the script reads the draft's front-matter
to find a `voice:` key. When `--json` is set, the script prints the
JSON report on stdout; otherwise it prints a short human summary.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

import _counting as C  # type: ignore[import-not-found]

import voice_io  # type: ignore[import-not-found]
from pydantic import BaseModel

# -----------------------------------------------------------------
# Bank-union helper (BID-00008 Provides contract)
# -----------------------------------------------------------------


class BankUnion(BaseModel):
    """Union of inline phrases and banked phrases for a single phrase field.

    Provides: voice-check-banks.feature -> BankUnion
    Shape: inline_phrases + banked_phrases -> union (dict pattern, as list[str])
    Pydantic BaseModel when voice_io is available; plain object otherwise.
    """

    inline_phrases: list[str]
    banked_phrases: list[str]
    union: list[str]


class RhythmTarget:
    """Named return type for parse_rhythm_target / parse_variation_target (ARCH-004).

    Plain __slots__ class -- these functions run in pyyaml-only environments too.
    """

    __slots__ = ("low", "high")

    def __init__(self, low: float, high: float) -> None:
        self.low = low
        self.high = high


class DraftParse:
    """Named return type for _parse_draft (ARCH-005).

    Plain __slots__ class -- _parse_draft runs in pyyaml-only environments too.
    """

    __slots__ = ("front_matter", "body")

    def __init__(self, front_matter: dict, body: str) -> None:
        self.front_matter = front_matter
        self.body = body


# -----------------------------------------------------------------
# Depth-kind classification (BID-0000B)
# Agent-territory kinds are skipped during check; bank kind is read.
# -----------------------------------------------------------------

_AGENT_TERRITORY_KINDS: frozenset[str] = frozenset(
    {"well", "dial", "surface-map"}  # BID-0000B: only these three are agent territory
)
_BANK_KIND = "bank"


# -----------------------------------------------------------------
# Bank-phrase loading helpers (BID-00008, BID-0000A, BID-0000B)
# -----------------------------------------------------------------


def _parse_bank_body_phrases(body: str) -> list[str]:
    """Extract phrases from a bank file body (ordered list items).

    Supports both "N. phrase text" numbered list and bare "- phrase" bullet list.
    Returns phrases in declaration order with leading/trailing whitespace stripped.
    Floor metadata in front-matter is intentionally ignored (compose-time only).
    """
    phrases: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        # Numbered list: "1. phrase text"
        m = re.match(r"^\d+\.\s+(.+)$", line)
        if m:
            phrases.append(m.group(1).strip())
            continue
        # Bullet list: "- phrase text" or "* phrase text"
        m2 = re.match(r"^[-*]\s+(.+)$", line)
        if m2:
            phrases.append(m2.group(1).strip())
    return phrases


def _build_bank_union(
    voice_dir: Path,
    inline_phrases: list[str],
    depth_entries: list[voice_io.DepthEntry] | None,
    field_path: str,
) -> BankUnion:
    """Union inline phrases with banked phrases for a given front-matter field path.

    Only depth entries with `kind == "bank"` whose front-matter `field`
    matches `field_path` are included. Floor is ignored (BID-0000A).

    Args:
        voice_dir: Absolute path to the voice directory.
        inline_phrases: Phrases declared inline in the voice front-matter.
        depth_entries: Depth manifest entries from the voice (may be None).
        field_path: The front-matter field path (e.g. `"lexicon.pet_phrases"`).

    Returns:
        BankUnion with inline_phrases, banked_phrases, and their union.
    """
    banked: list[str] = []
    if depth_entries:
        for entry in depth_entries:
            if entry.kind != _BANK_KIND:
                continue
            bank_path = voice_dir / entry.path
            if not bank_path.exists():
                continue
            try:
                depth_file = voice_io.read_depth_file(voice_dir, entry)
            except voice_io.VoiceIOError:
                continue
            # Check that this bank backs the requested field
            fm_field = depth_file.front_matter.get("field", "")
            if fm_field != field_path:
                continue
            banked.extend(_parse_bank_body_phrases(depth_file.body))
    return BankUnion(
        inline_phrases=list(inline_phrases),
        banked_phrases=banked,
        union=list(inline_phrases) + banked,
    )


def _collect_agent_territory_judgments(
    depth_entries: list[voice_io.DepthEntry] | None,
) -> list[dict]:
    """Emit agent_required placeholder judgments for agent-territory depth kinds.

    Covers: well, move-catalog, dial, surface-map, character, reference (BID-0000B).
    These are never read by voice_check; the agent handles them.
    """
    out: list[dict] = []
    if not depth_entries:
        return out
    for entry in depth_entries:
        if entry.kind not in _AGENT_TERRITORY_KINDS:
            continue
        kind = entry.kind
        path = entry.path
        out.append(
            {
                "rule": f"{kind}.{path}",
                "declared": {"kind": kind, "path": path},
                "region": "whole-document",
                "prompt": (
                    f"Agent-territory depth kind '{kind}' at '{path}' requires agent judgment. "
                    f"voice_check does not read this file."
                ),
            }
        )
    return out


# -----------------------------------------------------------------
# Lexicon resolution
# -----------------------------------------------------------------


def _lexicons_root() -> Path:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        return Path(root) / "voices" / "_lexicons"
    return Path(__file__).resolve().parent.parent / "voices" / "_lexicons"


def _load_lexicon(name: str) -> dict[str, Any]:
    path = _lexicons_root() / f"{name}.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def effective_diction(voice_fm: dict[str, Any]) -> dict[str, list]:
    diction = voice_fm.get("diction") or {}
    inherited = diction.get("inherit_lexicons") or []
    banned: list[str] = []
    preferred: list[dict] = []
    taboo_phrases_inherit: list[str] = []
    seen_pref_keys: set[str] = set()
    seen_banned: set[str] = set()
    for lex_name in inherited:
        lex = _load_lexicon(lex_name)
        for word in lex.get("banned") or []:
            key = word.lower()
            if key not in seen_banned:
                banned.append(word)
                seen_banned.add(key)
        for entry in lex.get("preferred") or []:
            key = (entry.get("instead_of") or "").lower()
            if key and key not in seen_pref_keys:
                preferred.append(entry)
                seen_pref_keys.add(key)
        for tab in lex.get("taboo_phrases") or []:
            taboo_phrases_inherit.append(tab)
    for word in diction.get("banned") or []:
        key = word.lower()
        if key not in seen_banned:
            banned.append(word)
            seen_banned.add(key)
    for entry in diction.get("preferred") or []:
        key = (entry.get("instead_of") or "").lower()
        if key:
            preferred = [
                e for e in preferred if (e.get("instead_of") or "").lower() != key
            ]
            preferred.append(entry)
            seen_pref_keys.add(key)
    # IFACE-006 note: the spec's EffectiveDictionPattern declares fields
    # (inline_lexicon, inherited_lexicon, union) as a conceptual shape; the
    # actual return keys here are (banned, preferred, taboo_phrases_inherit)
    # which reflect the voice-checker rule surface rather than the abstract
    # lexicon-union shape.
    return {
        "banned": banned,
        "preferred": preferred,
        "taboo_phrases_inherit": taboo_phrases_inherit,
    }


# -----------------------------------------------------------------
# Mechanical rules
# -----------------------------------------------------------------


def _word_pattern(word: str) -> str:
    return r"\b" + re.escape(word) + r"\b"


def check_banned(text: str, banned: list[str]) -> list[dict]:
    out: list[dict] = []
    for word in banned:
        for match in re.finditer(_word_pattern(word), text, flags=re.IGNORECASE):
            out.append(
                {
                    "rule": "diction.banned",
                    "category": "mechanical",
                    "string": word,
                    "line": C.line_of(text, match.start()),
                    "col": C.col_of(text, match.start()),
                    "message": f"banned word: '{word}'",
                }
            )
    return out


def check_preferred(text: str, preferred: list[dict]) -> list[dict]:
    out: list[dict] = []
    for entry in preferred:
        bad = entry.get("instead_of")
        good = entry.get("use") or ""
        if not bad:
            continue
        bad_re = _word_pattern(bad)
        good_re = _word_pattern(good) if good else None
        for match in re.finditer(bad_re, text, flags=re.IGNORECASE):
            sentence = C.sentence_containing(text, match.start())
            if good_re and re.search(good_re, sentence, flags=re.IGNORECASE):
                continue
            msg = f"prefer '{good}' over '{bad}'" if good else f"avoid '{bad}'"
            out.append(
                {
                    "rule": "diction.preferred",
                    "category": "mechanical",
                    "string": bad,
                    "suggestion": good,
                    "line": C.line_of(text, match.start()),
                    "col": C.col_of(text, match.start()),
                    "message": msg,
                }
            )
    return out


def check_characteristic(
    text: str, openers: list[str], closers: list[str]
) -> list[dict]:
    out: list[dict] = []
    sentences = C.split_sentences(text)
    if not sentences:
        return out
    if openers:
        hits = sum(
            1
            for s in sentences
            if any(s.lstrip().lower().startswith(o.lower()) for o in openers)
        )
        if hits == 0:
            out.append(
                {
                    "rule": "lexicon.characteristic_openers",
                    "category": "mechanical",
                    "kind": "absence",
                    "message": "no characteristic opener used in this draft",
                }
            )
    if closers:
        hits = sum(
            1
            for s in sentences
            if any(s.rstrip().lower().rstrip(".!").endswith(c.lower()) for c in closers)
        )
        if hits == 0:
            out.append(
                {
                    "rule": "lexicon.characteristic_closers",
                    "category": "mechanical",
                    "kind": "absence",
                    "message": "no characteristic closer used in this draft",
                }
            )
    return out


def check_taboo_phrases(
    text: str, taboos: list[str], rule_label: str = "lexicon.taboo_phrases"
) -> list[dict]:
    out: list[dict] = []
    for phrase in taboos:
        for match in re.finditer(re.escape(phrase), text, flags=re.IGNORECASE):
            out.append(
                {
                    "rule": rule_label,
                    "category": "mechanical",
                    "string": phrase,
                    "line": C.line_of(text, match.start()),
                    "col": C.col_of(text, match.start()),
                    "message": f"taboo phrase: '{phrase}'",
                }
            )
    return out


def check_never_mechanical(text: str, never: list[Any]) -> list[dict]:
    out: list[dict] = []
    for i, entry in enumerate(never):
        if not isinstance(entry, dict):
            continue
        if entry.get("detection") != "mechanical":
            continue
        rule_id = f"never.{entry.get('id', i)}"
        if "string" in entry:
            pattern = _word_pattern(entry["string"])
        elif "regex" in entry:
            pattern = entry["regex"]
        else:
            out.append(
                {
                    "rule": rule_id,
                    "category": "schema-error",
                    "message": "mechanical never-rule needs a 'string' or 'regex' field",
                }
            )
            continue
        try:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
                out.append(
                    {
                        "rule": rule_id,
                        "category": "mechanical",
                        "match": match.group(0),
                        "line": C.line_of(text, match.start()),
                        "col": C.col_of(text, match.start()),
                        "message": entry.get("rule")
                        or f"never-rule violated: {rule_id}",
                    }
                )
        except re.error as exc:
            out.append(
                {
                    "rule": rule_id,
                    "category": "schema-error",
                    "message": f"invalid regex in never-rule: {exc}",
                }
            )
    return out


def check_forbidden_patterns_regex(text: str, patterns: list[str]) -> list[dict]:
    out: list[dict] = []
    for pat in patterns:
        if not isinstance(pat, str) or not pat.startswith("re:"):
            continue
        regex = pat[3:].lstrip()
        try:
            for match in re.finditer(regex, text, flags=re.MULTILINE):
                out.append(
                    {
                        "rule": "rhythm.forbidden_patterns",
                        "category": "mechanical",
                        "match": match.group(0),
                        "line": C.line_of(text, match.start()),
                        "col": C.col_of(text, match.start()),
                        "message": f"forbidden pattern: {regex}",
                    }
                )
        except re.error as exc:
            out.append(
                {
                    "rule": "rhythm.forbidden_patterns",
                    "category": "schema-error",
                    "message": f"invalid regex: {exc}",
                }
            )
    return out


# -----------------------------------------------------------------
# Statistical rules
# -----------------------------------------------------------------

_TARGET_RANGE_RE = re.compile(
    r"\s*(?:around\s+)?(\d+(?:\.\d+)?)(?:\s*[-–]\s*(\d+(?:\.\d+)?))?\s*(?:words)?\s*",
    flags=re.IGNORECASE,
)
_VARIATION_NUMBER_RE = re.compile(
    r"std\s*dev\s*around\s+(\d+(?:\.\d+)?)", flags=re.IGNORECASE
)


def parse_rhythm_target(value: str | None) -> RhythmTarget | None:
    if not value or not isinstance(value, str):
        return None
    m = _TARGET_RANGE_RE.match(value)
    if not m:
        return None
    lo = float(m.group(1))
    hi = float(m.group(2)) if m.group(2) else lo
    return RhythmTarget(low=lo, high=hi)


def parse_variation_target(value: str | None) -> RhythmTarget | None:
    if not value or not isinstance(value, str):
        return None
    m = _VARIATION_NUMBER_RE.search(value)
    if m:
        n = float(m.group(1))
        return RhythmTarget(low=n * 0.7, high=n * 1.3)
    v = value.strip().lower()
    if v == "low":
        return RhythmTarget(low=0.0, high=4.0)
    if v == "medium":
        return RhythmTarget(low=4.0, high=10.0)
    if v == "high":
        return RhythmTarget(low=10.0, high=float("inf"))
    return None


def parse_paragraph_target(value: str | None) -> RhythmTarget | None:
    return parse_rhythm_target(value)


def _band(target: tuple[float, float], tolerance: float) -> tuple[float, float]:
    lo, hi = target
    return lo * (1.0 - tolerance), hi * (1.0 + tolerance)


def _scaled_band(
    target: tuple[float, float], tolerance: float, voice_tolerance: str
) -> tuple[float, float]:
    if voice_tolerance == "relaxed":
        tolerance *= 2.0
    elif voice_tolerance == "strict":
        tolerance = max(0.0, tolerance - 0.10)
    return _band(target, tolerance)


def check_rhythm(text: str, rhythm: dict, voice_tolerance: str) -> list[dict]:
    out: list[dict] = []
    sentences = C.split_sentences(text)
    if not sentences:
        return out
    wps = [len(C.word_tokens(s)) for s in sentences]
    mean_words = C.mean(wps)
    sd_words = C.stdev(wps)
    base_tolerance = 0.20

    target_mean = parse_rhythm_target(rhythm.get("target_mean_sentence"))
    if target_mean is not None:
        lo, hi = _scaled_band(
            (target_mean.low, target_mean.high), base_tolerance, voice_tolerance
        )
        if not (lo <= mean_words <= hi):
            out.append(
                {
                    "rule": "rhythm.target_mean_sentence",
                    "category": "statistical",
                    "measured": round(mean_words, 1),
                    "target": rhythm.get("target_mean_sentence"),
                    "band": (round(lo, 1), round(hi, 1)),
                    "message": f"mean sentence length {mean_words:.1f} words is outside the {rhythm.get('target_mean_sentence')} target",
                }
            )

    var_target = parse_variation_target(rhythm.get("target_variation"))
    if var_target is not None:
        lo, hi = var_target.low, var_target.high
        if not (lo <= sd_words <= hi):
            out.append(
                {
                    "rule": "rhythm.target_variation",
                    "category": "statistical",
                    "measured": round(sd_words, 1),
                    "target": rhythm.get("target_variation"),
                    "band": (lo, hi if hi != float("inf") else None),
                    "message": f"sentence-length variation (std dev {sd_words:.1f}) is outside the {rhythm.get('target_variation')} target",
                }
            )

    paragraphs = C.split_paragraphs(text)
    if paragraphs:
        sentences_per_para = [len(C.split_sentences(p)) for p in paragraphs]
        para_mean = C.mean(sentences_per_para)
        para_target = parse_paragraph_target(rhythm.get("paragraph_shape"))
        if para_target is not None:
            lo, hi = _scaled_band(
                (para_target.low, para_target.high), base_tolerance, voice_tolerance
            )
            if not (lo <= para_mean <= hi):
                out.append(
                    {
                        "rule": "rhythm.paragraph_shape",
                        "category": "statistical",
                        "measured": round(para_mean, 1),
                        "target": rhythm.get("paragraph_shape"),
                        "band": (round(lo, 1), round(hi, 1)),
                        "message": f"paragraph length (mean {para_mean:.1f} sentences) is outside the {rhythm.get('paragraph_shape')} target",
                    }
                )

    return out


def check_pet_phrases(text: str, phrases: list[str]) -> list[dict]:
    out: list[dict] = []
    if not phrases:
        return out
    words = C.word_count(text)
    over_threshold = 8.0
    for phrase in phrases:
        n = len(re.findall(_word_pattern(phrase), text, flags=re.IGNORECASE))
        per_1k = (1000.0 * n / words) if words else 0.0
        if n == 0 and words >= 200:
            out.append(
                {
                    "rule": "lexicon.pet_phrases",
                    "category": "statistical",
                    "phrase": phrase,
                    "measured": 0,
                    "target": "≥1 per 1k words",
                    "kind": "absence",
                    "message": f"pet phrase '{phrase}' not used (draft is {words} words)",
                }
            )
        elif per_1k > over_threshold:
            out.append(
                {
                    "rule": "lexicon.pet_phrases",
                    "category": "statistical",
                    "phrase": phrase,
                    "measured": round(per_1k, 1),
                    "target": f"≤{over_threshold:g} per 1k words",
                    "kind": "oversaturation",
                    "message": f"pet phrase '{phrase}' over-used at {per_1k:.1f}/1k words",
                }
            )
    return out


def _statistical_metric(text: str, metric: str) -> float:
    sentences = C.split_sentences(text)
    paragraphs = C.split_paragraphs(text)
    words = C.word_count(text)
    wps = [len(C.word_tokens(s)) for s in sentences] if sentences else [0]
    if metric == "mean_sentence_words":
        return C.mean(wps)
    if metric == "pct_sentences_over_30_words":
        if not sentences:
            return 0.0
        return 100.0 * sum(1 for n in wps if n > 30) / len(sentences)
    if metric == "pct_paragraphs_over_5_sentences":
        if not paragraphs:
            return 0.0
        spp = [len(C.split_sentences(p)) for p in paragraphs]
        return 100.0 * sum(1 for n in spp if n > 5) / len(paragraphs)
    if metric == "adjective_density_per_1k":
        n = len(
            re.findall(
                r"\b\w+(?:ous|ive|able|ible|ful|less|al|ic|ish|ly)\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        return (1000.0 * n / words) if words else 0.0
    if metric == "passive_density_per_1k":
        n = len(
            re.findall(
                r"\b(?:is|are|was|were|be|been|being)\s+\w+ed\b",
                text,
                flags=re.IGNORECASE,
            )
        )
        return (1000.0 * n / words) if words else 0.0
    if metric == "please_density_per_1k":
        n = len(re.findall(r"\bplease\b", text, flags=re.IGNORECASE))
        return (1000.0 * n / words) if words else 0.0
    raise ValueError(f"unknown metric: {metric}")


def check_never_statistical(text: str, never: list[Any]) -> list[dict]:
    out: list[dict] = []
    for i, entry in enumerate(never):
        if not isinstance(entry, dict):
            continue
        if entry.get("detection") != "statistical":
            continue
        rule_id = f"never.{entry.get('id', i)}"
        try:
            measured = _statistical_metric(text, entry["metric"])
        except (KeyError, ValueError) as exc:
            out.append(
                {
                    "rule": rule_id,
                    "category": "schema-error",
                    "message": f"invalid statistical never-rule: {exc}",
                }
            )
            continue
        threshold = float(entry.get("threshold", 0.0))
        op = entry.get("op", "gt")
        flagged = (
            (op == "gt" and measured > threshold)
            or (op == "lt" and measured < threshold)
            or (op == "eq" and abs(measured - threshold) < 1e-9)
        )
        if flagged:
            out.append(
                {
                    "rule": rule_id,
                    "category": "statistical",
                    "measured": round(measured, 2),
                    "threshold": threshold,
                    "op": op,
                    "message": entry.get("rule") or f"never-rule violated: {rule_id}",
                }
            )
    return out


# -----------------------------------------------------------------
# Agent-required placeholders
# -----------------------------------------------------------------


def _emit_placeholder(
    rule: str,
    declared: Any,
    prompt: str,
    region: str = "whole-document",
    measured: Any = None,
    policy: str | None = None,
) -> dict:
    out = {
        "rule": rule,
        "declared": declared,
        "region": region,
        "prompt": prompt,
    }

    if measured is not None:
        out["measured"] = measured
    if policy is not None:
        out["policy"] = policy
    return out


def collect_judgments_needed(text: str, voice_fm: dict) -> list[dict]:
    out: list[dict] = []

    if voice_fm.get("purpose"):
        out.append(
            _emit_placeholder(
                "purpose",
                voice_fm["purpose"],
                "Does this draft serve the declared purpose?",
            )
        )

    if voice_fm.get("audience"):
        out.append(
            _emit_placeholder(
                "audience",
                voice_fm["audience"],
                "Does this draft address the declared audience?",
            )
        )

    register = voice_fm.get("register") or {}
    for axis, value in register.items():
        if value is None:
            continue
        out.append(
            _emit_placeholder(
                f"register.{axis}",
                value,
                f"Does this draft hold to {axis}: {value}?",
            )
        )

    diction = voice_fm.get("diction") or {}
    for fld in ("default_balance", "germanic_for", "latinate_for"):
        if diction.get(fld):
            out.append(
                _emit_placeholder(
                    f"diction.{fld}",
                    diction[fld],
                    f"Does the draft's diction match the declared {fld}?",
                )
            )

    rhythm = voice_fm.get("rhythm") or {}
    if rhythm.get("one_sentence_paragraphs"):
        paragraphs = C.split_paragraphs(text)
        single = sum(1 for p in paragraphs if len(C.split_sentences(p)) == 1)
        out.append(
            _emit_placeholder(
                "rhythm.one_sentence_paragraphs",
                rhythm["one_sentence_paragraphs"],
                "Does the draft's use of one-sentence paragraphs honor the declared policy?",
                measured=f"{single}/{len(paragraphs)}",
                policy=rhythm["one_sentence_paragraphs"],
            )
        )
    for pat in rhythm.get("forbidden_patterns") or []:
        if isinstance(pat, str) and not pat.startswith("re:"):
            out.append(
                _emit_placeholder(
                    "rhythm.forbidden_patterns",
                    pat,
                    f"Does the draft contain the forbidden pattern: '{pat}'?",
                )
            )

    syntax = voice_fm.get("syntax") or {}
    counts = _syntax_counts(text)
    words = C.word_count(text)
    for key, policy in syntax.items():
        if not policy:
            continue
        n = counts.get(key, 0)
        per_1k = round(1000.0 * n / words, 2) if words else 0.0
        out.append(
            _emit_placeholder(
                f"syntax.{key}",
                policy,
                f"Does the draft's use of {key} (count {n}, {per_1k}/1k words) honor the policy: '{policy}'?",
                measured={"count": n, "per_1k": per_1k},
                policy=policy,
            )
        )

    if (voice_fm.get("lexicon") or {}).get("taboo_phrases"):
        out.append(
            _emit_placeholder(
                "lexicon.taboo_phrases.paraphrase",
                (voice_fm["lexicon"])["taboo_phrases"],
                "Does the draft contain paraphrases of any taboo phrase that the literal scan missed?",
            )
        )

    structure = voice_fm.get("structure") or {}
    for fld, policy in structure.items():
        if policy:
            out.append(
                _emit_placeholder(
                    f"structure.{fld}",
                    policy,
                    f"Does the draft's {fld} honor the policy: '{policy}'?",
                )
            )

    for i, entry in enumerate(voice_fm.get("never") or []):
        if isinstance(entry, str):
            out.append(
                _emit_placeholder(
                    f"never.{i}",
                    entry,
                    f"Does the draft violate the never-rule: '{entry}'?",
                )
            )
        elif (
            isinstance(entry, dict)
            and entry.get("detection", "agent-required") == "agent-required"
        ):
            out.append(
                _emit_placeholder(
                    f"never.{entry.get('id', i)}",
                    entry,
                    entry.get("rule") or "(no rule prose)",
                    f"Does the draft violate: '{entry.get('rule', '')}'?",
                )
            )

    return out


def _syntax_counts(text: str) -> dict[str, int]:
    cleaned = C._strip_code(text)
    return {
        "em_dashes": len(re.findall(r"—|--", cleaned)),
        "colons": len(re.findall(r":(?!\d)(?!//)", cleaned)),
        "semicolons": cleaned.count(";"),
        "parentheticals": len(re.findall(r"\([^)]+\)", cleaned)),
        "fragments": C.heuristic_fragment_count(text),
        "bullets": len(re.findall(r"^\s*[-*+]\s", cleaned, flags=re.MULTILINE)),
        "questions": len(re.findall(r"\?(?:\s|$)", cleaned)),
    }


# -----------------------------------------------------------------
# TEX-shape detector (BID-0005 -- BID-0006a)
# -----------------------------------------------------------------

_TEX1_RE = re.compile(r"—|--")
_TEX7_RE = re.compile(
    r"\b[\w'-]+,\s+[\w'-]+,?\s+and\s+[\w'-]+[.!?]?\s*$",
    re.IGNORECASE,
)

_TEX8_RE = re.compile(r"\bnot\b.{1,80}\bnot\b", re.IGNORECASE | re.DOTALL)
_BOLD_SPAN_RE = re.compile(r"\*\*[^\n]+\*\*")


def _sentence_is_tex_1(s: str) -> bool:
    return len(_TEX1_RE.findall(s)) >= 2


def _sentence_is_tex_7(s: str) -> bool:
    return _TEX7_RE.search(s.strip()) is not None


def _sentence_is_tex_8(s: str) -> bool:
    return _TEX8_RE.search(s) is not None


def _count_tex_candidates(text: str) -> dict[str, int]:
    """Count candidate occurrences of TEX-1, TEX-7, TEX-8, and TEX-9 shapes.

    TEX-1 -- em-dash interruptive aside (two em-dashes in the same sentence)
    TEX-7 -- three-part terminal triplet ("X, Y, and Z" at sentence end)
    TEX-8 -- anaphoric lyrical build ("Not X, not Y, not Z -- the thing itself")
    TEX-9 -- aphoristic close (very short sentence <8 words after a longer one)

    Returns a dict with keys tex_1, tex_7, tex_8, tex_9 mapping to int counts.
    """
    cleaned = C._strip_code(text)
    sentences: list[str] = C.split_sentences(cleaned)

    tex_1 = sum(1 for s in sentences if _sentence_is_tex_1(s))
    tex_7 = sum(1 for s in sentences if _sentence_is_tex_7(s))
    tex_8 = sum(1 for s in sentences if _sentence_is_tex_8(s))

    # TEX-9: aphoristic close -- short sentence (<8 words) following a longer
    # one (>=8 words). Count short-sentence occurrences that have a long
    # predecessor.
    tex_9 = 0
    words_per: list[int] = [len(C.word_tokens(s)) for s in sentences]
    for i in range(1, len(sentences)):
        if words_per[i] <= 6 and words_per[i - 1] >= 8:
            tex_9 += 1

    return {"tex_1": tex_1, "tex_7": tex_7, "tex_8": tex_8, "tex_9": tex_9}


def _count_bold_overlap(text: str) -> dict[str, int]:
    """Count TEX-1/7/8/9 candidate sentences that overlap with bold markup.

    A candidate sentence has bold-overlap when either:
    - The sentence itself contains a `**...**` span, OR
    - Its containing paragraph's first sentence is bold-fronted
      (begins with `**` after any leading markdown header markers).

    Bold-overlap signals that the texture move is attached to a paragraph's
    explicitly load-bearing content (per voice rule: bold marks the
    load-bearing claim, one per paragraph max). This is a near-zero-false-
    positive heuristic for the placement principle in moves.md "Placement"
    section: cosmic register attaches to small subjects, not the document's
    load-bearing claim.

    Returns a dict with keys tex_1, tex_7, tex_8, tex_9 mapping to int counts
    of bold-overlapping candidates.
    """
    C._strip_code(text)
    paragraphs = C.split_paragraphs(text)

    counts = {"tex_1": 0, "tex_7": 0, "tex_8": 0, "tex_9": 0}
    for para in paragraphs:
        sentences = C.split_sentences(para)
        if not sentences:
            continue
        first = sentences[0].lstrip()
        # Strip leading header markers (#, >, etc.) before checking bold-front
        first_stripped = re.sub(r"^#+\s*", "", first)
        para_bold_fronted = first_stripped.startswith("**")

        words_per = [len(C.word_tokens(s)) for s in sentences]
        for i, s in enumerate(sentences):
            sentence_has_bold = _BOLD_SPAN_RE.search(s) is not None
            if not (sentence_has_bold or para_bold_fronted):
                continue
            if _sentence_is_tex_1(s):
                counts["tex_1"] += 1
            if _sentence_is_tex_7(s):
                counts["tex_7"] += 1
            if _sentence_is_tex_8(s):
                counts["tex_8"] += 1
            if i >= 1 and words_per[i] <= 6 and words_per[i - 1] >= 8:
                counts["tex_9"] += 1

    return counts


# Stopword list for brief-vocab overlap. Function words and common
# discourse markers carry no signal; including them in the overlap
# would mask the signal we want (whether content vocabulary is shared
# vs invented). Kept small and local to avoid a new dependency.
_BRIEF_OVERLAP_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "for",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "i",
        "you",
        "he",
        "she",
        "they",
        "them",
        "us",
        "his",
        "her",
        "their",
        "our",
        "my",
        "your",
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
        "how",
        "not",
        "no",
        "so",
        "than",
        "into",
        "out",
        "up",
        "down",
        "over",
        "under",
        "about",
        "after",
        "before",
        "between",
        "through",
        "during",
        "above",
        "below",
        "more",
        "most",
        "less",
        "least",
        "very",
        "just",
        "only",
        "also",
        "even",
        "still",
        "yet",
        "all",
        "any",
        "some",
        "each",
        "every",
        "other",
        "another",
        "such",
        "same",
        "own",
        "one",
        "two",
        "first",
        "second",
        "last",
        "next",
        "now",
        "here",
        "there",
        "back",
        "forward",
        "way",
        "well",
        "much",
        "many",
        "few",
        "ever",
        "never",
        "always",
        "often",
        "sometimes",
    }
)


def _content_vocab(text: str) -> set[str]:
    """Return the set of content-word lemmas in `text`.

    Lowercases, strips code blocks, tokenizes on word boundaries,
    drops stopwords and tokens shorter than three characters
    (filtering out the noisiest function-word remainder). The result
    is the rough content-vocabulary of the text -- used by the
    brief-overlap detector to decide whether a TEX-decorated
    sentence's vocabulary is shared with the brief or invented by
    the writer.
    """
    cleaned = C._strip_code(text).lower()
    tokens = C.word_tokens(cleaned)
    return {t for t in tokens if len(t) >= 3 and t not in _BRIEF_OVERLAP_STOPWORDS}


# Threshold: a TEX-decorated sentence is classified as annotative
# when at least this share of its content vocabulary appears in the
# brief's vocabulary. Tuned against observed values:
#   - MAGE README's invented-subject sentences (Pope card,
#     bones-beneath-the-flesh) score ~0.0-0.2 against a brief that
#     describes the system functionally. Sentences with content
#     vocabulary the brief did not name.
#   - Annotative sentences in the four failed PR-description
#     exemplars score ~0.4-0.7 against the APP-40004 brief. The
#     content vocabulary is mostly the brief's vocabulary plus a
#     few decorative words (e.g., "by ancient custom of the
#     codebase" carries ancient + custom outside the brief).
# 0.6 is the threshold that separates the two distributions: the
# share of the sentence's content lives in the brief.
_BRIEF_OVERLAP_ANNOTATIVE_THRESHOLD = 0.6


def _count_brief_vocab_overlap(text: str, brief_text: str) -> dict[str, Any]:
    """Count TEX-1/7/8/9 candidate sentences whose content vocabulary
    is mostly contained in the brief's vocabulary (>=60%).

    A high overlap rate signals that the texture is annotative: the
    TEX-decorated sentence's vocabulary is mostly the brief's
    vocabulary, so the move is decorating an existing claim rather
    than inventing a new small subject the cosmic register could
    attach to. The failure mode the moves catalog warns against (the
    strip-test: remove the move and a literally-true claim remains).

    A low overlap rate signals that the texture is generative: the
    TEX-decorated sentence introduces vocabulary the brief did not
    contain. The MAGE README's "Pope card" and "bones beneath the
    flesh" both hit this signal -- invented small subjects that
    carry the cosmic register.

    Returns a dict with keys:
        per_move_overlap: {tex_1: int, tex_7: int, tex_8: int, tex_9: int}
            -- count of TEX-N candidate sentences with content-vocab
            whose overlap rate >= _BRIEF_OVERLAP_ANNOTATIVE_THRESHOLD
        total_annotative: int -- sum across all types
        total_candidates: int -- sum of all candidate counts
        annotative_rate: float -- total_annotative / total_candidates,
            0.0 when no candidates are present
        threshold: float -- the per-sentence annotative threshold
    """
    cleaned = C._strip_code(text)
    sentences = C.split_sentences(cleaned)
    brief_vocab = _content_vocab(brief_text)

    per_move = {"tex_1": 0, "tex_7": 0, "tex_8": 0, "tex_9": 0}
    total_candidates = 0
    words_per = [len(C.word_tokens(s)) for s in sentences]

    for i, s in enumerate(sentences):
        sentence_vocab = _content_vocab(s)
        # An empty sentence-vocab is vacuously contained -- skip to
        # avoid false-positive annotative classification on stub
        # sentences (e.g., bullets that read as section headers).
        if not sentence_vocab:
            continue
        overlap_share = len(sentence_vocab & brief_vocab) / len(sentence_vocab)
        is_annotative = overlap_share >= _BRIEF_OVERLAP_ANNOTATIVE_THRESHOLD

        if _sentence_is_tex_1(s):
            total_candidates += 1
            if is_annotative:
                per_move["tex_1"] += 1
        if _sentence_is_tex_7(s):
            total_candidates += 1
            if is_annotative:
                per_move["tex_7"] += 1
        if _sentence_is_tex_8(s):
            total_candidates += 1
            if is_annotative:
                per_move["tex_8"] += 1
        if i >= 1 and words_per[i] <= 6 and words_per[i - 1] >= 8:
            total_candidates += 1
            if is_annotative:
                per_move["tex_9"] += 1

    total_annotative = sum(per_move.values())
    annotative_rate = (
        round(total_annotative / total_candidates, 2) if total_candidates > 0 else 0.0
    )
    return {
        "per_move_overlap": per_move,
        "total_annotative": total_annotative,
        "total_candidates": total_candidates,
        "annotative_rate": annotative_rate,
        "threshold": _BRIEF_OVERLAP_ANNOTATIVE_THRESHOLD,
    }


def _load_move_catalog_floors(
    voice_obj: Any,
    voice_dir_path: "Path",
) -> dict[str, int]:
    """Return density floor fields from the first move-catalog depth entry.

    Reads the front-matter of the moves depth file and extracts
    density_floor, triplet_floor, lyrical_build_floor, aphoristic_close_floor,
    and load_bearing_floor. Missing fields default to 0. Preserved for
    back-compat callers that read floor-only thresholds; new callers
    should use _load_move_catalog_thresholds() which also reads the
    ceiling and strip-test pass-rate fields layered on top of floors.
    """
    if voice_obj is None:
        return {}
    depth_entries = voice_obj.depth or []
    for entry in depth_entries:
        if entry.kind != "move-catalog":
            continue
        try:
            depth_file = voice_io.read_depth_file(voice_dir_path, entry)
        except voice_io.VoiceIOError:
            continue
        fm = depth_file.front_matter or {}
        return {
            "density_floor": int(fm.get("density_floor", 0)),
            "triplet_floor": int(fm.get("triplet_floor", 0)),
            "lyrical_build_floor": int(fm.get("lyrical_build_floor", 0)),
            "aphoristic_close_floor": int(fm.get("aphoristic_close_floor", 0)),
            "load_bearing_floor": int(fm.get("load_bearing_floor", 0)),
        }
    return {}


def _load_move_catalog_thresholds(
    voice_obj: Any,
    voice_dir_path: "Path",
) -> dict[str, float]:
    """Return ceiling + strip-test pass-rate fields from the moves catalog.

    Reads density_ceiling (int) and strip_test_pass_rate (float) from
    the move-catalog depth file's front-matter. These are the
    selection-side thresholds that complement the floors: floors guard
    against flatness, ceilings + pass-rate guard against decorative
    over-deployment. Missing fields default to 0 (ceiling) and 0.0
    (pass-rate); a missing ceiling means "no ceiling enforced" and a
    missing pass-rate means "no quality gate enforced." Voices that
    declare neither field stay on the gate-only diagnostic.
    """
    if voice_obj is None:
        return {}
    depth_entries = voice_obj.depth or []
    for entry in depth_entries:
        if entry.kind != "move-catalog":
            continue
        try:
            depth_file = voice_io.read_depth_file(voice_dir_path, entry)
        except voice_io.VoiceIOError:
            continue
        fm = depth_file.front_matter or {}
        ceiling_raw = fm.get("density_ceiling")
        pass_rate_raw = fm.get("strip_test_pass_rate")
        return {
            "density_ceiling": int(ceiling_raw) if ceiling_raw is not None else 0,
            "strip_test_pass_rate": (
                float(pass_rate_raw) if pass_rate_raw is not None else 0.0
            ),
        }
    return {}


def tex_shape_detector(
    text: str,
    voice_obj: Any | None,
    voice_dir_path: "Path | None",
    brief_text: str | None = None,
) -> dict | None:
    """TEX-shape detector pass (BID-00005).

    Runs only when the voice declares a move-catalog depth entry.
    Returns a warning dict or None when the voice has no moves catalog.

    The returned dict conforms to the TexShapeWarning shape:
    pass, category, message, candidate_counts, floors, word_count,
    bold_overlap, brief_overlap, thresholds, approx_density_per_1k,
    strip_test_pass_rate, above_ceiling, below_pass_rate.

    Floors guard against flatness; ceilings + pass-rate guard against
    decorative over-deployment. Strip-test pass-rate has two halves:
    the structural half (bold-overlap signal -- moves attached to
    paragraph-load-bearing claims) and the content half (brief-overlap
    signal -- moves whose vocabulary is wholly contained in the brief's
    vocabulary, indicating annotation rather than invention. When
    `brief_text` is None, only the structural half contributes; when
    a brief is supplied, both halves count toward the pass-rate.
    """
    if voice_obj is None or voice_dir_path is None:
        return None
    # Only fire when the voice (or its parent in an override chain) has
    # a move-catalog depth entry. Composed voices like discordian-
    # composed inherit the move catalog from their base; without
    # walking the chain, the detector silently no-ops on every
    # composed-voice draft. Resolve the chain and check both levels.
    chain = (
        voice_io.resolve_override_chain(voice_obj)
        if hasattr(voice_io, "resolve_override_chain")
        else [voice_obj]
    )

    moves_owner: Any | None = None
    for v in chain:
        if any(e.kind == "move-catalog" for e in (v.depth or [])):
            moves_owner = v
            break
    if moves_owner is None:
        return None
    moves_dir_path = voice_io.voices_root() / moves_owner.name

    counts = _count_tex_candidates(text)
    bold_overlap = _count_bold_overlap(text)
    brief_overlap: dict[str, Any] | None = (
        _count_brief_vocab_overlap(text, brief_text) if brief_text is not None else None
    )
    floors = _load_move_catalog_floors(moves_owner, moves_dir_path)
    thresholds = _load_move_catalog_thresholds(moves_owner, moves_dir_path)
    word_count = C.word_count(text)

    # Build per-floor comparison message
    floor_map = {
        "tex_1": floors.get("density_floor", 0),
        "tex_7": floors.get("triplet_floor", 0),
        "tex_8": floors.get("lyrical_build_floor", 0),
        "tex_9": floors.get("aphoristic_close_floor", 0),
    }

    tex_label = {
        "tex_1": "TEX-1",
        "tex_7": "TEX-7",
        "tex_8": "TEX-8",
        "tex_9": "TEX-9",
    }
    below_floor: list[str] = []
    for key, floor_val in floor_map.items():
        detected = counts[key]
        if floor_val > 0 and detected < floor_val:
            below_floor.append(f"{tex_label[key]}: {detected} (floor {floor_val})")
    density_total = sum(counts.values())
    approx_density = (
        round(1000.0 * density_total / word_count, 1) if word_count else 0.0
    )

    if below_floor:
        msg = (
            f"TEX-shape density ({approx_density}/1k words "
            f"({word_count} words). Below floor: {', '.join(below_floor)}."
        )
    else:
        msg = (
            f"TEX-shape density ({approx_density}/1k words "
            f"({word_count} words). All floor targets met."
        )

    bold_overlap_total = sum(bold_overlap.values())
    if bold_overlap_total > 0:
        overlap_parts = [
            f"{tex_label[k]}={v}" for k, v in bold_overlap.items() if v > 0
        ]
        msg += (
            f" Bold-overlap detected ({', '.join(overlap_parts)}) -- "
            f'verify load-bearing per moves.md "Placement" '
            f"section (cosmic register attaches to small subjects, "
            f"not the document's load-bearing claim)."
        )

    # ------- Ceiling + strip-test pass-rate (Moves 3 + 4) -------
    # The ceiling caps total density per 1k words; the pass-rate is the
    # share of deployed moves that pass the strip-test approximation.
    # The strip-test has two halves:
    #   - structural (bold-overlap): the move attaches to a
    #     paragraph-load-bearing claim.
    #   - content (brief-overlap): the TEX-decorated sentence's
    #     vocabulary is wholly contained in the brief's vocabulary,
    #     so the move annotates a fact already in-scope rather than
    #     inventing a small subject for the cosmic register.
    # A sentence fails the strip-test when EITHER signal flags it.
    # Without a brief, only the structural half contributes; the
    # message names this so the agent knows the pass-rate is partial.
    density_ceiling = thresholds.get("density_ceiling", 0)
    pass_rate_threshold = thresholds.get("strip_test_pass_rate", 0.0)
    above_ceiling = density_ceiling > 0 and approx_density > density_ceiling

    brief_annotative_total = (
        brief_overlap["total_annotative"] if brief_overlap is not None else 0
    )

    if density_total > 0:
        # Conservative union estimate: the share of moves that fail at
        # least one signal is bounded above by the sum of the two
        # signal counts (capped at density_total). Treat that bound as
        # the failure count for the pass-rate.
        failed_estimate = min(
            density_total, bold_overlap_total + brief_annotative_total
        )
        deployed_strip_test_pass = density_total - failed_estimate
        strip_test_pass_rate = round(deployed_strip_test_pass / density_total, 2)
    else:
        strip_test_pass_rate = 1.0  # Vacuously passes when nothing is deployed
    below_pass_rate = (
        pass_rate_threshold > 0.0 and strip_test_pass_rate < pass_rate_threshold
    )

    if above_ceiling:
        msg += (
            f" Density above ceiling ({approx_density}/1k > {density_ceiling}/1k) -- "
            f"selection beats quantity; trim moves that fail the strip-test."
        )
    if brief_overlap is not None and brief_annotative_total > 0:
        annotative_rate = brief_overlap["annotative_rate"]
        msg += (
            f" Brief-vocab overlap detected ({brief_annotative_total}/"
            f"{brief_overlap['total_candidates']}) TEX-decorated "
            f"sentences (rate {annotative_rate}) carry only vocabulary "
            f"already in the brief -- these moves are annotating, not "
            f"inventing. Re-attach to small subjects the brief did "
            f"not name."
        )
    elif brief_overlap is None:
        msg += (
            " (Strip-test pass-rate is structural-only; pass --brief "
            "<path> to also score the content half against the brief's "
            "vocabulary.)"
        )

    if below_pass_rate:
        msg += (
            f" Strip-test pass-rate ({strip_test_pass_rate}) below "
            f"threshold ({pass_rate_threshold}) -- deployed moves are "
            f"reading as decoration. Re-attach to small invented "
            f'subjects per moves.md "Placement" section.'
        )

    return {
        "pass": "tex_shape_detector",
        "category": "warning",
        "message": msg,
        "candidate_counts": counts,
        "bold_overlap": bold_overlap,
        "brief_overlap": brief_overlap,
        "floors": floors,
        "thresholds": thresholds,
        "approx_density_per_1k": approx_density,
        "strip_test_pass_rate": strip_test_pass_rate,
        "above_ceiling": above_ceiling,
        "below_pass_rate": below_pass_rate,
        "word_count": word_count,
    }


# ================================================
# Orchestrator
# ================================================


def check(
    text: str,
    voice_fm: dict,
    voice_tolerance: str = "normal",
    voice_name: str | None = None,
    voice_obj: Any | None = None,
    brief_text: str | None = None,
) -> dict:
    """Run all voice-check rules against `text` using the voice front-matter.

    When `voice_obj` is supplied (recommended for deep voices), bank files are
    read and their phrases are unioned with inline `lexicon.pet_phrases`.
    The override chain (parent -> child) is walked when `voice_obj.base` is set,
    applying the bank union at the child level.

    When `voice_obj` is None (legacy / simple-voice path), behaviour is
    identical to pre-redesign: only inline front-matter is consulted.
    """
    diction_eff = effective_diction(voice_fm)
    violations: list[dict] = []

    violations += check_banned(text, diction_eff["banned"])
    violations += check_preferred(text, diction_eff["preferred"])

    lexicon = voice_fm.get("lexicon") or {}
    violations += check_characteristic(
        text,
        lexicon.get("characteristic_openers") or [],
        lexicon.get("characteristic_closers") or [],
    )

    taboo_combined: list[str] = []
    seen_taboo: set[str] = set()
    # When voice_obj is supplied, union banked taboo_phrases from depth-manifest
    # (BID-0008X end-to-end: after /deepen-voice, taboo_phrases live in a bank file)
    if voice_obj is not None:
        voice_dir = voice_io.voices_root() / voice_obj.name
        banked_taboo_union = _build_bank_union(
            voice_dir,
            list(lexicon.get("taboo_phrases") or []),
            voice_obj.depth,
            "lexicon.taboo_phrases",
        )
        inline_and_banked_taboo = banked_taboo_union.union
    else:
        inline_and_banked_taboo = list(lexicon.get("taboo_phrases") or [])
    for phrase in inline_and_banked_taboo + diction_eff["taboo_phrases_inherit"]:
        key = phrase.lower()
        if key not in seen_taboo:
            taboo_combined.append(phrase)
            seen_taboo.add(key)
    violations += check_taboo_phrases(text, taboo_combined)

    never = voice_fm.get("never") or []
    violations += check_never_mechanical(text, never)
    violations += check_never_statistical(text, never)

    rhythm = voice_fm.get("rhythm") or {}
    violations += check_forbidden_patterns_regex(
        text, rhythm.get("forbidden_patterns") or []
    )
    violations += check_rhythm(text, rhythm, voice_tolerance)

    # --- pet_phrases: union inline + banked (BID-0000X, BID-0000Y) -------
    # When voice_obj is provided, walk the override chain (parent, child) and
    # compute the effective pet_phrases union at the child level.
    # Bank union is computed at the child level after override resolution;
    # the child's depth manifest wins where present (total override by path).
    if voice_obj is not None:
        chain = voice_io.resolve_override_chain(voice_obj)
        # The child is the last element in the chain (or the sole element for
        # a simple voice). Effective pet_phrases: union across the resolved
        # chain -- parent provides banked phrases when the child has no override.
        # Implementation: collect pet_phrases from the chain's last (child)
        # union, walking parent banks only when child has no bank for that field.
        effective_phrases = _compute_chain_pet_phrases(chain)
    else:
        effective_phrases = list(lexicon.get("pet_phrases") or [])

    violations += check_pet_phrases(text, effective_phrases)

    if voice_tolerance == "relaxed":
        violations = [v for v in violations if v.get("kind") != "oversaturation"]

    judgments = collect_judgments_needed(text, voice_fm)

    # Append agent-territory depth-kind placeholders (BID-00008)
    if voice_obj is not None:
        judgments = judgments + _collect_agent_territory_judgments(voice_obj.depth)

    by_category = {"mechanical": 0, "statistical": 0}
    for v in violations:
        cat = v.get("category", "")
        if cat in by_category:
            by_category[cat] += 1

    # Prefer explicit voice_name (from CLI --voice or caller); fall back to
    # front-matter key if present (older voice profiles that named "voice:").
    resolved_voice = voice_name or voice_fm.get("voice")

    # --- TEX-shape detector pass (BID-00005) ---
    # Runs once per invocation; emits warnings (never violations).
    warnings: list[dict] = []
    if voice_obj is not None:
        vdir_path = voice_io.voices_root() / voice_obj.name
        tex_warning = tex_shape_detector(
            text, voice_obj, vdir_path, brief_text=brief_text
        )
        if tex_warning is not None:
            warnings.append(tex_warning)

    return {
        "voice": resolved_voice,
        "voice_tolerance": voice_tolerance,
        "checked": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "mechanical_violations": by_category["mechanical"],
            "statistical_violations": by_category["statistical"],
            "needs_judgment": len(judgments),
        },
        "violations": violations,
        "warnings": warnings,
        "judgments_needed": judgments,
    }


def _compute_chain_pet_phrases(chain: voice_io.OverrideChain) -> list[str]:
    """Compute effective pet_phrases across the override chain.

    Walk [parent, child] (or [child] for a simple voice). At each level,
    compute the bank union for `lexicon.pet_phrases`. The child's depth
    manifest takes total precedence when it contains a bank for this field;
    otherwise the parent's banked phrases contribute.

    Returns the union list (inline + banked) for the effective phrase set
    that voice_check should run density checks against.
    """
    if not chain:
        return []

    field_path = "lexicon.pet_phrases"

    # Collect [inline_phrases, depth_entries, voice_dir] per chain level
    # Walk from parent -> child; child overrides parent's bank for same field_path.
    # We use total-override-by-path semantics: if the child has a bank entry
    # for this field, use ONLY the child's bank (plus child's inline).
    # If the child has NO bank entry for this field, use parent's bank.

    child = chain[-1]
    child_dir = voice_io.voices_root() / child.name
    child_inline = list(
        (child.front_matter.get("lexicon") or {}).get("pet_phrases") or []
    )
    child_union = _build_bank_union(child_dir, child_inline, child.depth, field_path)
    child_has_bank = bool(child_union.banked_phrases)

    if child_has_bank or len(chain) == 1:
        # Child covers this field (or is a simple voice); use child only
        return child_union.union

    # Child has no bank for this field; collect from parent(s)
    # (single-level only -- chain has at most [parent, child])
    parent = chain[0]
    parent_dir = voice_io.voices_root() / parent.name
    parent_inline = list(
        (parent.front_matter.get("lexicon") or {}).get("pet_phrases") or []
    )
    parent_union = _build_bank_union(
        parent_dir, parent_inline, parent.depth, field_path
    )

    # Merge: child's inline phrases + parent's full union
    seen: set[str] = set()
    merged: list[str] = []
    for phrase in child_inline + parent_union.union:
        key = phrase.lower()
        if key not in seen:
            merged.append(phrase)
            seen.add(key)
    return merged


# -----------------------------------
# CLI
# -----------------------------------

_DRAFT_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _parse_draft(path: Path) -> DraftParse:
    raw = path.read_text(encoding="utf-8")
    m = _DRAFT_FRONT_MATTER_RE.match(raw)
    front = yaml.safe_load(m.group(1)) if m else {}
    body = raw[m.end() :] if m else raw
    return DraftParse(
        front_matter=(front if isinstance(front, dict) else {}), body=body
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="voice_check")
    parser.add_argument("draft", help="path to the draft .md file")
    parser.add_argument("--voice", help="voice name (default: from draft front-matter)")
    parser.add_argument(
        "--voice-tolerance",
        choices=["relaxed", "normal", "strict"],
        help="override voice tolerance level (relaxed, normal, or strict)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON to stdout")
    parser.add_argument(
        "--brief",
        help=(
            "path to the brief that produced this draft. When supplied, "
            "the TEX-shape detector scores the content half of the "
            "strip-test (vocabulary overlap between TEX-decorated "
            "sentences and the brief). Without --brief, only the "
            "structural half (bold-overlap) contributes to the "
            "strip-test pass-rate."
        ),
    )

    args = parser.parse_args(argv)

    draft_path = Path(args.draft)
    parsed = _parse_draft(draft_path)
    front, body = parsed.front_matter, parsed.body
    voice_name = args.voice or front.get("voice")
    # CLI flag overrides front-matter voice_tolerance; front-matter overrides default
    voice_tolerance = args.voice_tolerance or front.get("voice_tolerance", "normal")

    # Resolve brief: CLI flag --brief > draft front-matter 'brief:' key >
    # sibling <draft>.brief.md file > absent. Absent means the
    # structural-only strip-test pass-rate is reported.
    brief_text: str | None = None
    brief_path_raw = args.brief or front.get("brief")
    if brief_path_raw:
        bp = Path(brief_path_raw)
        if bp.is_file():
            brief_text = bp.read_text(encoding="utf-8")
        else:
            print(
                f"--brief path not found: {bp}; continuing without brief",
                file=sys.stderr,
            )
    else:
        sibling = draft_path.parent / f"{draft_path.stem}.brief.md"
        if sibling.is_file():
            brief_text = sibling.read_text(encoding="utf-8")

    if not voice_name:
        print(
            "no voice declared in front-matter and --voice not given", file=sys.stderr
        )
        return 2

    voice_obj = None
    voice_fm: dict
    try:
        voice_obj = voice_io.read(voice_name)
        voice_fm = voice_obj.front_matter
    except Exception as exc:
        print(f"voice profile not found: {exc}", file=sys.stderr)
        return 2

    report = check(
        body,
        voice_fm,
        voice_tolerance=voice_tolerance,
        voice_name=voice_name,
        voice_obj=voice_obj,
        brief_text=brief_text,
    )
    report["draft"] = str(draft_path)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        s = report["summary"]
        print(
            f"voice={report['voice']} mechanical={s['mechanical_violations']} "
            f"statistical={s['statistical_violations']} needs_judgment={s['needs_judgment']}"
        )
        for v in report["violations"]:
            cat = v.get("category", "?")
            line = v.get("line")
            loc = f"{draft_path}:{line}" if line else str(draft_path)
            print(f"  [{cat}] {loc} -- {v.get('rule')}: {v.get('message')}")
    return 0 if not report["violations"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
