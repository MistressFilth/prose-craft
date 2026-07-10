"""Counting primitives for voice_check.py.

Every rule in 08-voice-checker-rules.md depends on one of these
helpers. Kept separate from `voice_check` so the rule logic stays
readable.

Approximations are accepted where they keep the dependency surface
zero (no NLTK, no spaCy). The voice-checker reports approximate
counts; the agent's interpretive verdict is the authoritative read.
"""

import re
import statistics
from typing import Iterable


_FINITE_VERB_TOKENS = frozenset(
    {
        "is",
        "was",
        "were",
        "are",
        "am",
        "be",
        "been",
        "being",
        "has",
        "have",
        "had",
        "having",
        "do",
        "does",
        "did",
        "doing",
        "done",
        "can",
        "could",
        "shall",
        "should",
        "will",
        "would",
        "may",
        "might",
        "must",
        "ought",
        "need",
        "dare",
        "go",
        "goes",
        "went",
        "gone",
        "say",
        "says",
        "said",
        "see",
        "sees",
        "saw",
        "seen",
        "make",
        "makes",
        "made",
        "know",
        "knows",
        "knew",
        "known",
        "take",
        "takes",
        "took",
        "taken",
        "get",
        "gets",
        "got",
        "gotten",
        "give",
        "gives",
        "gave",
        "given",
        "find",
        "finds",
        "found",
        "think",
        "thinks",
        "thought",
        "come",
        "comes",
        "came",
        "want",
        "wants",
        "wanted",
        "use",
        "uses",
        "used",
        "tell",
        "tells",
        "told",
        "ask",
        "asks",
        "asked",
        "feel",
        "feels",
        "felt",
        "seem",
        "seems",
        "seemed",
        "leave",
        "leaves",
        "left",
        "call",
        "calls",
        "called",
        "become",
        "becomes",
        "became",
    }
)


_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`[^`]+`")
_TABLE_ROW_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*$", re.MULTILINE)
_ATX_HEADER_RE = re.compile(r"^[ \t]*#{1,6}[ \t]+.*$", re.MULTILINE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])(?=\s|$)")
_WORD_RE = re.compile(r"\b[\w'\-]+\b")
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n+")


def _strip_code(text: str) -> str:
    """Blank out non-prose spans before counting, offsets preserved.

    Strips fenced and inline code, then markdown table rows (pipe
    syntax has no terminal punctuation, so an un-stripped table would
    otherwise glom onto whichever real sentence follows it) and ATX
    headers (same problem: a header line has no terminal punctuation
    either). Replacement is same-length whitespace so callers that
    rely on offsets into the original text (e.g. `sentence_containing`)
    still line up.
    """
    text = _CODE_FENCE_RE.sub(lambda m: " " * len(m.group(0)), text)
    text = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), text)
    text = _TABLE_ROW_RE.sub(lambda m: " " * len(m.group(0)), text)
    text = _ATX_HEADER_RE.sub(lambda m: " " * len(m.group(0)), text)
    return text


def split_sentences(text: str) -> list[str]:
    """Split into sentences. Approximate.

    Strips fenced and inline code first; splits on terminal
    punctuation followed by whitespace or end-of-string. Decimal
    numbers (3.14) survive because the lookahead requires whitespace.
    """
    cleaned = _strip_code(text)
    parts = _SENTENCE_SPLIT_RE.split(cleaned)
    return [p.strip() for p in parts if p and p.strip()]


def word_tokens(s: str) -> list[str]:
    return _WORD_RE.findall(s)


def word_count(text: str) -> int:
    return len(_WORD_RE.findall(_strip_code(text)))


def split_paragraphs(text: str) -> list[str]:
    cleaned = _strip_code(text)
    parts = _PARAGRAPH_SPLIT_RE.split(cleaned)
    return [p.strip() for p in parts if p and p.strip()]


def heuristic_fragment_count(text: str) -> int:
    """Sentences with no finite verb. Approximate.

    Counts sentences that:
    - have <= 6 word tokens AND
    - contain none of the common finite-verb forms.
    """
    count = 0
    for s in split_sentences(text):
        toks = [t.lower() for t in word_tokens(s)]
        if len(toks) <= 6 and not any(t in _FINITE_VERB_TOKENS for t in toks):
            count += 1
    return count


def line_of(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


def col_of(text: str, offset: int) -> int:
    last_nl = text.rfind("\n", 0, offset)
    return offset - last_nl if last_nl >= 0 else offset + 1


def sentence_containing(text: str, offset: int) -> str:
    sentences = split_sentences(text)
    cursor = 0
    cleaned = _strip_code(text)
    for sentence in sentences:
        idx = cleaned.find(sentence, cursor)
        if idx < 0:
            continue
        end = idx + len(sentence)
        if idx <= offset <= end:
            return sentence
        cursor = end
    return ""


def stdev(values: Iterable[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)
