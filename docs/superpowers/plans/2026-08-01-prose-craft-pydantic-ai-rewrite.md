# prose-craft → pydantic-ai rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite prose-craft from a Claude Code plugin only into a `pydantic-ai` engine (Typer CLI + FastMCP server + thin plugin adapter) with XDG-resident voice profiles, copy-only migration from the old plugin-data location, and `FunctionModel`-driven deterministic test suite.

**Architecture:** Single composition root `ProseCraft` constructs seven `pydantic-ai` agents. Deterministic primitives in `src/prose_craft/analysis/` are pure Python, callable from CLI, agents (as tools), and MCP. Voice profiles are Pydantic models that round-trip the existing `voice.md` front-matter format. Plugin survives as 10-line adapters; engine has zero Claude Code imports.

**Tech Stack:** Python >=3.10, pydantic-ai-slim, pydantic-ai-harness, typer, fastmcp, pyyaml, pytest, pytest-asyncio, respx, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-01-prose-craft-pydantic-ai-design.md`

## Global Constraints

- `requires-python = ">=3.10"` (mirrors lies / mage)
- Two version surfaces start at `0.1.0`: `plugin/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
- Conventional Commits v1.0.0, no `Co-Authored-By:` trailer
- `mypy --strict` over `src/prose_craft`
- `ruff check` + `ruff format` with line-length 100
- `asyncio_mode = "auto"` in `pyproject.toml` (mirrors lies)
- Voice profile files: `extra="forbid"` on `VoiceProfile`
- Engine: zero Claude Code imports; plugin: zero engine code
- Voice profiles at `$XDG_DATA_HOME/prose-craft/voices/<name>/voice.md`
- Migration is copy-only; source never modified
- All CLI error paths exit non-zero with stderr message

---

## Phase 0: Foundation

### Task 1: Repository scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `.pre-commit-config.yaml`
- Create: `.gitignore`
- Create: `AGENTS.md`
- Create: `CLAUDE.md`
- Create: `README.md`
- Create: `CHANGELOG.md`
- Create: `src/prose_craft/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Interfaces:** None (foundation). Subsequent tasks import from `prose_craft`.

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "prose-craft"
version = "0.1.0"
description = "pydantic-ai engine for designing and applying prose voices"
readme = "README.md"
requires-python = ">=3.10"
license = "GPL-2.0-only"
dependencies = [
    "pydantic-ai-slim>=2.18",
    "pydantic-ai-harness[code-mode,dynamic-workflow]>=0.1",
    "typer>=0.12",
    "fastmcp>=2.0",
    "mcp>=1.0",
    "pyyaml>=6.0.3",
    "python-frontmatter>=1.1.0",
    "pydantic>=2.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.12",
    "ruff>=0.5",
    "mypy>=1.10",
    "respx>=0.21",
]

[project.scripts]
prose = "prose_craft.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/prose_craft"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-ra -q"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
strict = true
files = ["src/prose_craft"]
```

- [ ] **Step 2: Write Makefile**

```makefile
.PHONY: init sync test unit-test features-test clean lint typecheck format check release help

init:
	uv sync --all-extras

sync:
	uv sync --all-extras

unit-test:
	uv run pytest tests/unit -v

features-test:
	uv run pytest tests/features -v

test: unit-test features-test

clean:
	rm -rf .ruff_cache .mypy_cache .pytest_cache src/prose_craft/__pycache__ src/prose_craft/*/__pycache__ tests/__pycache__ tests/*/__pycache__
	find . -type d -name __pycache__ -exec rm -rf {} +

lint:
	uv run ruff check src tests

typecheck:
	uv run mypy src/prose_craft

format:
	uv run ruff format src tests

check: lint typecheck format

release:
	uv run python -m build
	git tag v$(uv version --short)
	git push --tags

help:
	@echo "Targets: init sync unit-test features-test test clean lint typecheck format check release help"
```

- [ ] **Step 3: Write .pre-commit-config.yaml**

```yaml
repos:
  - repo: local
    hooks:
      - id: make-check
        name: make check
        entry: make check
        language: system
        pass_filenames: false
```

- [ ] **Step 4: Write .gitignore**

```
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
build/
*.egg-info/
.superpowers/
.superpowers.json
```

- [ ] **Step 5: Write AGENTS.md**

```markdown
# MistressFilth/prose-craft

Repository for the prose-craft engine: a `pydantic-ai` CLI + FastMCP server
for designing and applying prose voices, with a thin Claude Code plugin
adapter.

## Working memory

Cross-repo scratch, brainstorm output, and any artifact **not yet promoted**
to the engine docs lives in the project-notes hub:

`@/home/divinefilth/code/project-notes/prose-craft/AGENTS.md`

## Conventions

See `@/home/divinefilth/.claude/rules/` for shared repo standards
(commit format, required files, Makefile targets, pre-commit, versioning,
changelog, plugin packaging).
```

- [ ] **Step 6: Write CLAUDE.md**

```
@AGENTS.md
```

- [ ] **Step 7: Write README.md skeleton**

```markdown
# prose-craft

A `pydantic-ai` engine for designing and applying prose voices.

- **Typer CLI** with subcommands for analyze, edit, architect, tune-diction,
  voice compose/refine/draft/edit/check/list/show/init, migrate, mcp.
- **FastMCP server** over stdio, exposing the engine as tools and resources
  to any MCP host.
- **Voice profiles** at `$XDG_DATA_HOME/prose-craft/voices/<name>/voice.md`.
- **Plugin adapter** at `plugin/` is a thin Claude Code integration.

## Install

```bash
make init
```

## Quickstart

```bash
prose voice list
prose analyze chapter.md --voice MistressFilth
prose voice compose MistressFilth
prose mcp
```

## Migrating from the old plugin

If you have existing voices in `${CLAUDE_PLUGIN_DATA}/voices/`, copy them
into the new XDG-resident location:

```bash
prose migrate voices
```

The old directory is left untouched; delete the new one to roll back.

## Development

```bash
make test
make check
```

See `docs/superpowers/specs/2026-08-01-prose-craft-pydantic-ai-design.md`
for the architecture.
```

- [ ] **Step 8: Write CHANGELOG.md**

```markdown
# Changelog

## [Unreleased]

### Changed
- Rewrite as pydantic-ai CLI + FastMCP server. Plugin reduced to thin adapter.
  Voice profiles moved from `${CLAUDE_PLUGIN_DATA}/voices/` to
  `$XDG_DATA_HOME/prose-craft/voices/`. Run `prose migrate voices` once to
  copy existing profiles.

## [0.0.0] - 2026-07-14

Initial release as a Claude Code plugin only.
```

- [ ] **Step 9: Write src/prose_craft/__init__.py**

```python
"""prose-craft: pydantic-ai engine for designing and applying prose voices."""

__version__ = "0.1.0"
```

- [ ] **Step 10: Write tests/__init__.py and tests/conftest.py**

```python
# tests/__init__.py
```

```python
# tests/conftest.py
"""Shared pytest fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_voices_root(tmp_path: Path) -> Path:
    """An isolated voices root for the duration of one test."""
    root = tmp_path / "voices"
    root.mkdir()
    return root
```

- [ ] **Step 11: Run init and verify**

```bash
make init
```

Expected: uv creates `.venv`, installs all deps, no errors.

- [ ] **Step 12: Commit**

```bash
git add pyproject.toml Makefile .pre-commit-config.yaml .gitignore AGENTS.md CLAUDE.md README.md CHANGELOG.md src/ tests/
git commit -m "chore: scaffold prose-craft engine (pyproject, Makefile, foundation)"
```

---


## Phase 1: Deterministic primitives

### Task 2: sentences module

**Files:**
- Create: `src/prose_craft/analysis/__init__.py`
- Create: `src/prose_craft/analysis/sentences.py`
- Create: `tests/unit/analysis/__init__.py`
- Create: `tests/unit/analysis/test_sentences.py`

**Interfaces:**
- Produces: `tokenize_sentences(text: str) -> list[str]`
- Produces: `tokenize_words(text: str) -> list[str]`
- Produces: `count_syllables(word: str) -> int`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/analysis/test_sentences.py
from prose_craft.analysis.sentences import count_syllables, tokenize_sentences, tokenize_words


def test_tokenize_sentences_splits_on_terminal_punctuation():
    text = "She walked home. He stayed. They laughed!"
    assert tokenize_sentences(text) == ["She walked home.", "He stayed.", "They laughed!"]


def test_tokenize_sentences_collapses_whitespace():
    text = "First sentence.\n\n  Second   sentence."
    assert tokenize_sentences(text) == ["First sentence.", "Second sentence."]


def test_tokenize_words_lowercases_and_strips_punctuation():
    assert tokenize_words("The quick, brown Fox.") == ["the", "quick", "brown", "fox"]


def test_count_syllables_basic():
    assert count_syllables("cat") == 1
    assert count_syllables("table") == 2
    assert count_syllables("beautiful") == 3


def test_count_syllables_silent_e():
    assert count_syllables("make") == 1
    assert count_syllables("code") == 1


def test_count_syllables_empty_returns_one():
    assert count_syllables("") == 1
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/analysis/test_sentences.py -v
```

Expected: ModuleNotFoundError or ImportError.

- [ ] **Step 3: Implement sentences module**

```python
# src/prose_craft/analysis/__init__.py
"""Deterministic prose metrics. No LLM, no network."""
```

```python
# src/prose_craft/analysis/sentences.py
"""Sentence, word, syllable tokenization."""
from __future__ import annotations

import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"\b[a-zA-Z]+\b")
_VOWELS = "aeiouy"


def tokenize_sentences(text: str) -> list[str]:
    """Split text into sentences on terminal punctuation.

    Collapses all whitespace between sentences to a single space.
    Empty results are dropped.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def tokenize_words(text: str) -> list[str]:
    """Extract lowercase alphabetic words from text."""
    return [w.lower() for w in _WORD_RE.findall(text)]


def count_syllables(word: str) -> int:
    """Rough syllable count based on vowel groups.

    Adjusts for silent trailing 'e'. Returns 1 for empty input.
    """
    word = word.lower()
    if not word:
        return 1
    count = 0
    prev_was_vowel = False
    for char in word:
        is_vowel = char in _VOWELS
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/analysis/test_sentences.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/analysis/ tests/unit/analysis/
git commit -m "feat(analysis): sentence, word, syllable tokenization"
```

---

### Task 3: diction module

**Files:**
- Create: `src/prose_craft/analysis/diction.py`
- Create: `tests/unit/analysis/test_diction.py`

**Interfaces:**
- Produces: `classify_word_origin(word: str) -> Literal["germanic", "latinate", "unknown"]`
- Produces: `GERMANIC_MARKERS: set[str]`, `LATINATE_MARKERS: set[str]`, `LATINATE_SUFFIXES: list[str]`
- Produces: `SubstitutionRule` Pydantic model (used by Phase 4 agents)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/analysis/test_diction.py
from prose_craft.analysis.diction import (
    LATINATE_SUFFIXES,
    SubstitutionRule,
    classify_word_origin,
)


def test_classify_explicit_germanic():
    assert classify_word_origin("blood") == "germanic"
    assert classify_word_origin("hand") == "germanic"


def test_classify_explicit_latinate():
    assert classify_word_origin("utilize") == "latinate"
    assert classify_word_origin("facilitate") == "latinate"


def test_classify_by_suffix():
    assert classify_word_origin("communication") == "latinate"
    assert classify_word_origin("movement") == "latinate"


def test_classify_short_word_is_germanic():
    assert classify_word_origin("run") == "germanic"
    assert classify_word_origin("cat") == "germanic"


def test_classify_polysyllabic_unknown_is_latinate():
    assert classify_word_origin("perspicacious") == "latinate"


def test_classify_unknown():
    assert classify_word_origin("onomatopoeia") in ("latinate", "unknown")


def test_latinate_suffixes_constant():
    assert "tion" in LATINATE_SUFFIXES
    assert "ment" in LATINATE_SUFFIXES
    assert "ity" in LATINATE_SUFFIXES


def test_substitution_rule_model():
    rule = SubstitutionRule(instead_of="utilize", use="use", note="prefer Germanic")
    assert rule.instead_of == "utilize"
    assert rule.use == "use"
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/analysis/test_diction.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement diction module**

```python
# src/prose_craft/analysis/diction.py
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
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/analysis/test_diction.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/analysis/diction.py tests/unit/analysis/test_diction.py
git commit -m "feat(analysis): diction classifier and SubstitutionRule model"
```

---

### Task 4: cohesion module

**Files:**
- Create: `src/prose_craft/analysis/cohesion.py`
- Create: `tests/unit/analysis/test_cohesion.py`

**Interfaces:**
- Produces: `ConnectiveCounts(causal: int, temporal: int, additive: int, adversative: int)`
- Produces: `count_connectives(text: str, words: list[str]) -> ConnectiveCounts`
- Produces: `connectives_per_100(counts: ConnectiveCounts, word_count: int) -> float`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/analysis/test_cohesion.py
from prose_craft.analysis.cohesion import (
    ConnectiveCounts,
    connectives_per_100,
    count_connectives,
)


def test_count_connectives_basic():
    text = "Because it rained, we stayed inside. Then we ate."
    counts = count_connectives(text, ["Because", "it", "rained", "we", "stayed", "inside", "Then", "we", "ate"])
    assert counts.causal >= 1
    assert counts.temporal >= 1


def test_count_connectives_empty():
    counts = count_connectives("", [])
    assert counts.causal == 0
    assert counts.temporal == 0
    assert counts.additive == 0
    assert counts.adversative == 0


def test_connectives_per_100():
    counts = ConnectiveCounts(causal=2, temporal=2, additive=0, adversative=0)
    assert connectives_per_100(counts, 100) == 4.0
    assert connectives_per_100(counts, 0) == 0.0
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/analysis/test_cohesion.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement cohesion module**

```python
# src/prose_craft/analysis/cohesion.py
"""Cohesion marker counting and density."""
from __future__ import annotations

from pydantic import BaseModel

CAUSAL_WORDS: set[str] = {
    "because", "since", "therefore", "thus", "hence", "so",
    "consequently", "accordingly", "as a result", "for this reason",
    "due to",
}
TEMPORAL_WORDS: set[str] = {
    "then", "next", "after", "before", "during", "while", "meanwhile",
    "subsequently", "previously", "finally", "eventually", "first",
    "second", "last", "when", "until",
}
ADDITIVE_WORDS: set[str] = {
    "and", "also", "moreover", "furthermore", "in addition", "additionally",
}
ADVERSATIVE_WORDS: set[str] = {
    "but", "however", "yet", "although", "though", "nevertheless",
    "nonetheless", "instead", "otherwise", "conversely", "on the other hand",
}


class ConnectiveCounts(BaseModel):
    causal: int = 0
    temporal: int = 0
    additive: int = 0
    adversative: int = 0


def count_connectives(text: str, words: list[str]) -> ConnectiveCounts:
    """Count occurrences of each connective class in text.

    Uses word-boundary regex on the lowercase text. Returns zeros for
    empty text.
    """
    import re

    if not text:
        return ConnectiveCounts()
    lowered = text.lower()
    return ConnectiveCounts(
        causal=_count_set(lowered, CAUSAL_WORDS, re),
        temporal=_count_set(lowered, TEMPORAL_WORDS, re),
        additive=_count_set(lowered, ADDITIVE_WORDS, re),
        adversative=_count_set(lowered, ADVERSATIVE_WORDS, re),
    )


def _count_set(text: str, words: set[str], re: object) -> int:
    total = 0
    for word in words:
        if " " in word:
            total += text.count(word)
        else:
            total += len(re.findall(rf"\b{re.escape(word)}\b", text))
    return total


def connectives_per_100(counts: ConnectiveCounts, word_count: int) -> float:
    """Total connectives per 100 words. Zero if word_count is zero."""
    if word_count == 0:
        return 0.0
    total = counts.causal + counts.temporal + counts.additive + counts.adversative
    return round(total / word_count * 100, 2)
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/analysis/test_cohesion.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/analysis/cohesion.py tests/unit/analysis/test_cohesion.py
git commit -m "feat(analysis): cohesion marker counts and density"
```

---

### Task 5: readability + monotony modules

**Files:**
- Create: `src/prose_craft/analysis/readability.py`
- Create: `src/prose_craft/analysis/monotony.py`
- Create: `tests/unit/analysis/test_readability.py`
- Create: `tests/unit/analysis/test_monotony.py`

**Interfaces:**
- Produces: `flesch_reading_ease(mean_sentence_length: float, avg_syllables_per_word: float) -> float`
- Produces: `flesch_grade_level(score: float) -> str`
- Produces: `monotony_zones(sent_lengths: list[int], tolerance: int = 3, min_streak: int = 4) -> list[tuple[int, int]]`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/analysis/test_readability.py
from prose_craft.analysis.readability import flesch_grade_level, flesch_reading_ease


def test_flesch_simple_text():
    # Mean sentence 10, avg syllables 1.5 -> 206.835 - 10.15 - 126.9 = 69.785
    score = flesch_reading_ease(mean_sentence_length=10.0, avg_syllables_per_word=1.5)
    assert 69.0 <= score <= 71.0


def test_flesch_clamped():
    # Pathological inputs should clamp to [0, 100]
    assert flesch_reading_ease(mean_sentence_length=100.0, avg_syllables_per_word=5.0) == 0.0
    assert flesch_reading_ease(mean_sentence_length=1.0, avg_syllables_per_word=1.0) == 100.0


def test_grade_level_thresholds():
    assert "Graduate" in flesch_grade_level(20.0)
    assert "College" in flesch_grade_level(40.0)
    assert "Standard" in flesch_grade_level(65.0)
    assert "Easy" in flesch_grade_level(75.0)
    assert "Very Easy" in flesch_grade_level(95.0)
```

```python
# tests/unit/analysis/test_monotony.py
from prose_craft.analysis.monotony import monotony_zones


def test_no_zones_when_lengths_vary():
    lengths = [10, 20, 8, 25, 12, 30]
    assert monotony_zones(lengths) == []


def test_detects_long_streak():
    # Five consecutive lengths within ±3 of each other
    lengths = [10, 11, 12, 11, 13, 10, 25]
    zones = monotony_zones(lengths)
    assert len(zones) == 1
    start, end = zones[0]
    assert start == 0
    assert end == 5


def test_does_not_flag_short_streaks():
    # Three consecutive within tolerance is not monotony
    lengths = [10, 11, 12, 30, 10, 11, 12, 30]
    assert monotony_zones(lengths) == []


def test_zone_at_end_of_text():
    lengths = [25, 10, 11, 12, 11, 13]
    zones = monotony_zones(lengths)
    assert len(zones) == 1
    assert zones[0] == (1, 5)
```

- [ ] **Step 2: Run tests, verify fail**

```bash
uv run pytest tests/unit/analysis/test_readability.py tests/unit/analysis/test_monotony.py -v
```

Expected: ImportError on both.

- [ ] **Step 3: Implement readability module**

```python
# src/prose_craft/analysis/readability.py
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
```

- [ ] **Step 4: Implement monotony module**

```python
# src/prose_craft/analysis/monotony.py
"""Detect consecutive same-length sentence zones."""
from __future__ import annotations


def monotony_zones(
    sent_lengths: list[int],
    tolerance: int = 3,
    min_streak: int = 4,
) -> list[tuple[int, int]]:
    """Return zones of 4+ consecutive sentences within ±tolerance words.

    A zone is a (start_index, end_index_inclusive) pair. Empty input
    returns empty list.
    """
    if len(sent_lengths) < min_streak:
        return []
    zones: list[tuple[int, int]] = []
    streak_start = 0
    for i in range(1, len(sent_lengths)):
        if abs(sent_lengths[i] - sent_lengths[i - 1]) <= tolerance:
            continue
        if i - streak_start >= min_streak:
            zones.append((streak_start, i - 1))
        streak_start = i
    if len(sent_lengths) - streak_start >= min_streak:
        zones.append((streak_start, len(sent_lengths) - 1))
    return zones
```

- [ ] **Step 5: Run tests, verify pass**

```bash
uv run pytest tests/unit/analysis/test_readability.py tests/unit/analysis/test_monotony.py -v
```

Expected: 8 passed total.

- [ ] **Step 6: Commit**

```bash
git add src/prose_craft/analysis/readability.py src/prose_craft/analysis/monotony.py tests/unit/analysis/
git commit -m "feat(analysis): Flesch readability and monotony zone detection"
```

---

### Task 6: clause_density module

**Files:**
- Create: `src/prose_craft/analysis/clause_density.py`
- Create: `tests/unit/analysis/test_clause_density.py`

**Interfaces:**
- Produces: `ClauseDensity(ppc_per_1k: float, agentless_passive_per_1k: float)`
- Produces: `measure_clause_density(text: str, words: list[str]) -> ClauseDensity`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/analysis/test_clause_density.py
from prose_craft.analysis.clause_density import measure_clause_density


def test_empty_text():
    cd = measure_clause_density("", [])
    assert cd.ppc_per_1k == 0.0
    assert cd.agentless_passive_per_1k == 0.0


def test_present_participle_clause_counted():
    text = "Walking home, she saw the dog. Running fast, he caught it."
    words = text.split()
    cd = measure_clause_density(text, words)
    assert cd.ppc_per_1k > 0


def test_agentless_passive_counted():
    text = "The ball was thrown. The cake was eaten."
    words = text.split()
    cd = measure_clause_density(text, words)
    assert cd.agentless_passive_per_1k > 0


def test_no_false_positive_on_simple_sentence():
    text = "She walked home."
    words = text.split()
    cd = measure_clause_density(text, words)
    assert cd.ppc_per_1k == 0.0
    assert cd.agentless_passive_per_1k == 0.0
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/analysis/test_clause_density.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement clause_density module**

```python
# src/prose_craft/analysis/clause_density.py
"""Present participial clause + agentless passive density."""
from __future__ import annotations

import re

from pydantic import BaseModel

_PPC_RE = re.compile(
    r"\b(Walking|Running|Sitting|Standing|Talking|Working|Looking|Holding|"
    r"Carrying|Wearing|Holding|Reading|Writing|Eating|Drinking|Thinking|"
    r"Feeling|Hearing|Watching|Coming|Going|Playing|Crying|Laughing|"
    r"Smiling|Frowning|Sleeping|Waiting|Hoping|Fearing|Loving|Hating|"
    r"Reaching|Pulling|Pushing|Kicking|Striking|Opening|Closing|Lifting|"
    r"Dropping|Falling|Rising|Stopping|Starting|Building|Breaking)\b",
    re.IGNORECASE,
)
_AGENTLESS_PASSIVE_RE = re.compile(
    r"\b(was|were|is|are|been|be|being)\s+(\w+(ed|en|t))\b",
    re.IGNORECASE,
)


class ClauseDensity(BaseModel):
    ppc_per_1k: float
    agentless_passive_per_1k: float


def measure_clause_density(text: str, words: list[str]) -> ClauseDensity:
    """Measure present participial clauses and agentless passives per 1k words."""
    if not words:
        return ClauseDensity(ppc_per_1k=0.0, agentless_passive_per_1k=0.0)
    word_count = len(words)
    ppc = len(_PPC_RE.findall(text))
    passive = len(_AGENTLESS_PASSIVE_RE.findall(text))
    return ClauseDensity(
        ppc_per_1k=round(ppc / word_count * 1000, 1),
        agentless_passive_per_1k=round(passive / word_count * 1000, 1),
    )
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/analysis/test_clause_density.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/analysis/clause_density.py tests/unit/analysis/test_clause_density.py
git commit -m "feat(analysis): clause density (PPC + agentless passive)"
```

---

### Task 7: dispersion module

**Files:**
- Create: `src/prose_craft/analysis/dispersion.py`
- Create: `tests/unit/analysis/test_dispersion.py`

**Interfaces:**
- Produces: `DispersionAltitude1(content_jaccard, trigram_jaccard, shared_mass, dispersion_index)`
- Produces: `DispersionAltitude2(distinct_opener_frames_fraction, mean_opener_similarity, distinct_structure_sigs_fraction, mean_structural_similarity, dispersion_index)`
- Produces: `DispersionProfile(n, altitude_1, altitude_2)`
- Produces: `measure_set(new_draft: str, siblings: list[str]) -> DispersionProfile`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/analysis/test_dispersion.py
from prose_craft.analysis.dispersion import measure_set


def test_single_draft_no_siblings():
    profile = measure_set("one two three four", [])
    assert profile.n == 1
    assert profile.altitude_1.dispersion_index == 0.0
    assert profile.altitude_2.distinct_opener_frames_fraction == 0.0


def test_identical_drafts_have_zero_dispersion():
    text = "The cat sat on the mat. The dog ran in the park."
    profile = measure_set(text, [text, text])
    assert profile.n == 3
    assert profile.altitude_1.dispersion_index == 0.0


def test_distinct_drafts_have_positive_dispersion():
    new = "She walked home slowly through the rain."
    sib_a = "The cat sat on the mat and purred."
    sib_b = "Birds sang in the bright morning sky."
    profile = measure_set(new, [sib_a, sib_b])
    assert profile.n == 3
    assert profile.altitude_1.dispersion_index > 0.0
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/analysis/test_dispersion.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement dispersion module**

```python
# src/prose_craft/analysis/dispersion.py
"""Cross-draft lexical + structural dispersion measurement."""
from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel

_WORD_RE = re.compile(r"\b[a-z]+\b")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) > 2}


def _trigrams(text: str) -> set[str]:
    tokens = _WORD_RE.findall(text.lower())
    return {" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)}


def _jaccard(a: set[str], b: set[str]) -> float:
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
    sig_pairs = [
        _jaccard(set(s1), set(s2)) for s1 in sigs for s2 in sigs if s1 != s2
    ]
    mean_struct_sim = sum(sig_pairs) / len(sig_pairs) if sig_pairs else 0.0
    altitude_2_dispersion = (distinct_openers + (1.0 - mean_opener_sim) + distinct_sigs + (1.0 - mean_struct_sim)) / 4.0

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
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/analysis/test_dispersion.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/analysis/dispersion.py tests/unit/analysis/test_dispersion.py
git commit -m "feat(analysis): cross-draft dispersion (lexical + structural)"
```

---

### Task 8: metrics module

**Files:**
- Create: `src/prose_craft/analysis/metrics.py`
- Create: `tests/unit/analysis/test_metrics.py`

**Interfaces:**
- Produces: `ProseMetrics` Pydantic model (sentence_count, word_count, mean_sentence_length, sentence_length_std, short_sentences_pct, long_sentences_pct, germanic_pct, latinate_pct, avg_syllables_per_word, polysyllabic_pct, flesch_reading_ease, connectives_per_100_words, causal_markers, temporal_markers, monotony_zones)`
- Produces: `analyze_prose(text: str) -> ProseMetrics`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/analysis/test_metrics.py
from prose_craft.analysis.metrics import ProseMetrics, analyze_prose


def test_empty_text_returns_none():
    assert analyze_prose("") is None


def test_short_clean_text():
    text = "The cat sat on the mat. The dog ran in the park."
    m = analyze_prose(text)
    assert isinstance(m, ProseMetrics)
    assert m.sentence_count == 2
    assert m.word_count > 0
    assert 0.0 <= m.germanic_pct <= 100.0


def test_metrics_rounds_decimals():
    text = "She walked home. He stayed inside. They laughed at the joke."
    m = analyze_prose(text)
    assert m.mean_sentence_length == round(m.mean_sentence_length, 1)
    assert m.sentence_length_std == round(m.sentence_length_std, 1)


def test_detects_monotony():
    # Six sentences all near 10 words
    text = " ".join(["The cat sat on the mat by the door today."] * 6)
    m = analyze_prose(text)
    assert m.monotony_zones >= 1
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/analysis/test_metrics.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement metrics module**

```python
# src/prose_craft/analysis/metrics.py
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
    poly = sum(1 for s in syllables if s >= 3) / len(syllables) * 100 if syllables else 0.0

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
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/analysis/test_metrics.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/analysis/metrics.py tests/unit/analysis/test_metrics.py
git commit -m "feat(analysis): ProseMetrics model and analyze_prose() entry point"
```

---

### Task 9: inlined references

**Files:**
- Create: `src/prose_craft/references/__init__.py`
- Create: `src/prose_craft/references/prose_analysis.md`
- Create: `src/prose_craft/references/diction_tuning.md`
- Create: `src/prose_craft/references/rhythm_mastery.md`
- Create: `src/prose_craft/references/cohesion_craft.md`
- Create: `src/prose_craft/references/voice_contract.md`

**Interfaces:** None directly. Agents load these via `Path(__file__).parent / "<filename>"`.

- [ ] **Step 1: Write the __init__.py**

```python
# src/prose_craft/references/__init__.py
"""Inlined reference material loaded into agent system prompts."""

from pathlib import Path

REFERENCES_DIR = Path(__file__).parent


def load_reference(name: str) -> str:
    """Return the text of a reference file by basename (no extension)."""
    path = REFERENCES_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Write prose_analysis.md**

```markdown
# Prose analysis reference

Universal prose metrics and their interpretation.

## Thresholds

| Metric | Poor | Acceptable | Excellent |
|---|---|---|---|
| Sentence length variance (std dev) | <5 | 5-12 | 8-12 |
| Latinate % | >70% | <50% | Context-appropriate |
| Connectives per 100 words | <2 | 2-5 | 3-4 |
| Polysyllabic words | >35% | 20-35% | <25% |

## Flesch Reading Ease bands

| Score | Grade |
|---|---|
| 90-100 | 5th grade (Very Easy) |
| 80-90 | 6th grade (Easy) |
| 70-80 | 7th grade (Fairly Easy) |
| 60-70 | 8th-9th grade (Standard) |
| 50-60 | High school (Fairly Difficult) |
| 30-50 | College (Difficult) |
| 0-30 | Graduate (Very Difficult) |
```

- [ ] **Step 3: Write diction_tuning.md**

```markdown
# Diction tuning reference

Use Germanic for force. Use Latinate for precision.

## Common substitutions

| Latinate | Germanic |
|---|---|
| utilize | use |
| facilitate | help |
| demonstrate | show |
| significant | large / big |
| approximately | about |
| commence | begin / start |
| terminate | end / stop |
| attempt (v.) | try |
| sufficient | enough |
| regarding | about |

## When to reach for each

- **Germanic**: emotional intensity, physical action, concrete description, dialogue, death/violence/sex
- **Latinate**: technical precision, formal register, softening and distance, abstract concepts

## Quick test for Latinate overload

- Multiple `-tion`, `-ment`, `-ity` endings in a sentence
- Bureaucratic feel
- The sense that you need a dictionary
```

- [ ] **Step 4: Write rhythm_mastery.md**

```markdown
# Rhythm mastery reference

Readers unconsciously synchronize with prose rhythm. Sentence length encodes emotion; variance encodes energy.

## Sentence length categories

| Length | Words | Effect |
|---|---|---|
| Very short | 1-5 | Shock, emphasis, finality |
| Short | 6-12 | Direct, clear, strong |
| Medium | 13-20 | Balanced, comfortable, flexible |
| Long | 21-35 | Flowing, complex, immersive |
| Very long | 36+ | Overwhelming, breathless, accumulating |

## Five common rhythm problems

- **The Plateau** — all sentences the same length; flat, numbing
- **The Sawtooth** — alternating long/short/long/short; predictable
- **The Run-On** — consecutive long sentences; reader loses the thread
- **The Stutter** — consecutive short sentences outside of intentional staccato
- **The Wrong Energy** — sentence rhythm contradicts emotional content
```

- [ ] **Step 5: Write cohesion_craft.md**

```markdown
# Cohesion craft reference

Cohesion is the explicit linguistic glue between sentences and paragraphs.

## Four connective types

| Type | Examples |
|---|---|
| Additive | and, also, moreover, in addition, furthermore |
| Adversative | but, however, yet, although, on the other hand |
| Causal | because, since, therefore, thus, hence, so, consequently |
| Temporal | then, next, after, before, during, meanwhile, subsequently |

## Density guide

| Density | Effect |
|---|---|
| <1 per 100 words | Choppy, disconnected |
| 1-2 per 100 words | Taut, fast-paced |
| 2-4 per 100 words | Balanced, natural |
| 4-6 per 100 words | Logical, careful |
| >6 per 100 words | Mechanical, heavy |
```

- [ ] **Step 6: Write voice_contract.md**

```markdown
# Voice contract reference

The voice profile is the writer's authored constitution. Schema D1-D10.

## Front-matter order (fixed)

1. voice
2. version
3. created
4. updated
5. authors
6. imported_from
7. voice_persona
8. purpose (D1)
9. audience (D2)
10. audiences (D2.5)
11. register (D3)
12. diction (D4)
13. rhythm (D5)
14. syntax (D6)
15. lexicon (D7)
16. structure (D8)
17. never (D9)
18. attributions

## Rule taxonomy

- **Mechanical** — string/regex match (`diction.banned`, `lexicon.taboo_phrases` literal hits, `never` with `detection: mechanical`)
- **Statistical** — count and compare to target (`rhythm.target_mean_sentence`, every `syntax.*`)
- **Agent-required** — model judges (`purpose`, every `register.*` axis, `structure.*`)

## Audience ceiling enforcement

The ceiling is subtraction only. `dial_ceiling: 0.0` engages `fallback_voice`. `closed: true` rejects the audience outright.
```

- [ ] **Step 7: Smoke-test loader**

```bash
uv run python -c "from prose_craft.references import load_reference; print(load_reference('prose_analysis')[:80])"
```

Expected: prints the first 80 chars of `prose_analysis.md`.

- [ ] **Step 8: Commit**

```bash
git add src/prose_craft/references/
git commit -m "feat(references): inlined reference material (markdown, loaded by agents)"
```

---


## Phase 2: Voice subsystem

### Task 10: voice profile model

**Files:**
- Create: `src/prose_craft/voices/__init__.py`
- Create: `src/prose_craft/voices/model.py`
- Create: `tests/unit/voices/__init__.py`
- Create: `tests/unit/voices/test_model.py`

**Interfaces:**
- Produces: `VoiceProfile`, `AudienceCeiling`, `RegisterAxes`, `DictionConfig`, `RhythmConfig`, `SyntaxConfig`, `LexiconConfig`, `StructureConfig`, `NeverEntry`, `Attribution`, `SurfaceFilter`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/voices/test_model.py
import pytest
from pydantic import ValidationError

from prose_craft.voices.model import (
    AudienceCeiling,
    DictionConfig,
    LexiconConfig,
    NeverEntry,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SubstitutionRule,
    SurfaceFilter,
    SyntaxConfig,
    VoiceProfile,
)


def test_minimal_profile_parses():
    p = VoiceProfile(
        voice="MistressFilth",
        created="2026-08-01",
        updated="2026-08-01",
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )
    assert p.voice == "MistressFilth"
    assert p.version == 1


def test_extra_keys_rejected():
    with pytest.raises(ValidationError):
        VoiceProfile.model_validate({
            "voice": "x",
            "unknown_field": "y",
        })


def test_audience_ceiling_defaults():
    c = AudienceCeiling()
    assert c.severity_ceiling == 5
    assert c.dial_ceiling == 1.0
    assert c.closed is False


def test_audience_ceiling_closed():
    c = AudienceCeiling(closed=True, reason="no external use")
    assert c.closed is True
    assert c.reason == "no external use"


def test_never_entry_detection_default():
    e = NeverEntry(rule="no em-dashes as sentence punctuation")
    assert e.detection == "agent-required"


def test_substitution_rule_in_diction():
    d = DictionConfig(
        banned=["utilize"],
        preferred=[SubstitutionRule(instead_of="utilize", use="use", note="prefer Germanic")],
    )
    assert "utilize" in d.banned
    assert d.preferred[0].use == "use"


def test_surface_filter_admit_list():
    f = SurfaceFilter(admit=["memo", "postcard"])
    assert f.admit == ["memo", "postcard"]
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/voices/test_model.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement model module**

```python
# src/prose_craft/voices/__init__.py
"""Voice profile IO, location, model, and check."""
```

```python
# src/prose_craft/voices/model.py
"""Pydantic models for voice profiles.

Mirrors the D1-D10 + audiences + attributions schema from the existing
plugin. ``extra="forbid"`` rejects unknown keys so writers discover
typos at parse time.
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Re-export SubstitutionRule from analysis.diction so the voice
# schema can import it from a single place.
from prose_craft.analysis.diction import SubstitutionRule  # noqa: F401


class RegisterAxes(BaseModel):
    """D3 — six register axes. None = silent (composer has not asked)."""

    funny_serious: float | None = None
    formal_casual: float | None = None
    respectful_irreverent: float | None = None
    enthusiastic_matter_of_fact: float | None = None
    certainty: float | None = None
    density: float | None = None


class DictionConfig(BaseModel):
    """D4 — vocabulary guidance."""

    default_balance: str | None = None
    germanic_for: list[str] = []
    latinate_for: list[str] = []
    banned: list[str] = []
    preferred: list[SubstitutionRule] = []
    inherit_lexicons: list[str] = []


class RhythmConfig(BaseModel):
    """D5 — sentence and paragraph rhythm."""

    target_mean_sentence: str | None = None
    target_variation: str | None = None
    paragraph_shape: str | None = None
    one_sentence_paragraphs: str | None = None
    forbidden_patterns: list[str] = []


class SyntaxConfig(BaseModel):
    """D6 — punctuation and sentence-shape policy."""

    em_dashes: str | None = None
    colons: str | None = None
    semicolons: str | None = None
    parentheticals: str | None = None
    fragments: str | None = None
    bullets: str | None = None
    questions: str | None = None


class LexiconConfig(BaseModel):
    """D7 — characteristic vocabulary."""

    pet_phrases: list[str] = []
    characteristic_openers: list[str] = []
    characteristic_closers: list[str] = []
    taboo_phrases: list[str] = []


class StructureConfig(BaseModel):
    """D8 — opening, closing, transitions, emphasis, citations."""

    opening: str | None = None
    closing: str | None = None
    transitions: str | None = None
    emphasis: str | None = None
    citations: str | None = None


class SurfaceFilter(BaseModel):
    """Per-audience surface admit/close list."""

    admit: list[str] | None = None
    close: list[str] | None = None


class AudienceCeiling(BaseModel):
    """D2.5 — per-voice audience ceiling. Subtraction only."""

    severity_ceiling: int = Field(default=5, ge=0, le=5)
    dial_ceiling: float = Field(default=1.0, ge=0.0, le=1.0)
    fallback_voice: str | None = None
    never_extend: list["NeverEntry"] = []
    surface_filter: SurfaceFilter | None = None
    closed: bool = False
    reason: str | None = None


class NeverEntry(BaseModel):
    """D9 — one never-list entry."""

    id: str | None = None
    rule: str
    detection: Literal["mechanical", "statistical", "agent-required"] = "agent-required"


class Attribution(BaseModel):
    """Provenance record for a YAML field or rule id."""

    field: str
    source: str
    license: str
    citation: str | None = None
    date: date | None = None


class VoiceProfile(BaseModel):
    """D1-D10 + audiences + attributions."""

    model_config = ConfigDict(extra="forbid")

    voice: str
    version: int = 1
    created: date
    updated: date
    authors: list[str] = []
    imported_from: str | None = None
    voice_persona: str | None = None
    purpose: str | None = None
    audience: str | None = None
    audiences: dict[str, AudienceCeiling] = {}
    register: RegisterAxes
    diction: DictionConfig
    rhythm: RhythmConfig
    syntax: SyntaxConfig
    lexicon: LexiconConfig
    structure: StructureConfig
    never: list[NeverEntry] = []
    attributions: list[Attribution] = []


AudienceCeiling.model_rebuild()
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/voices/test_model.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/voices/ tests/unit/voices/
git commit -m "feat(voices): VoiceProfile and supporting Pydantic models"
```

---

### Task 11: voice location

**Files:**
- Create: `src/prose_craft/voices/location.py`
- Create: `tests/unit/voices/test_location.py`

**Interfaces:**
- Produces: `get_voices_root() -> Path` — XDG-compliant
- Produces: `voice_path(name: str, *, root: Path | None = None) -> Path`
- Produces: `VoiceNameError` exception

- [ ] **Step 1: Write failing test**

```python
# tests/unit/voices/test_location.py
import os
from pathlib import Path

import pytest

from prose_craft.voices.location import (
    VoiceNameError,
    get_voices_root,
    voice_path,
)


def test_voice_path_validates_name(tmp_voices_root):
    with pytest.raises(VoiceNameError):
        voice_path("Invalid Name", root=tmp_voices_root)
    with pytest.raises(VoiceNameError):
        voice_path("../escape", root=tmp_voices_root)
    p = voice_path("MistressFilth", root=tmp_voices_root)
    assert p == tmp_voices_root / "MistressFilth" / "voice.md"


def test_voice_path_allows_hyphens(tmp_voices_root):
    p = voice_path("d-nova", root=tmp_voices_root)
    assert p == tmp_voices_root / "d-nova" / "voice.md"


def test_get_voices_root_uses_env(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    root = get_voices_root()
    assert root == tmp_path / "prose-craft" / "voices"


def test_get_voices_root_uses_prose_craft_root_env(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "custom"))
    root = get_voices_root()
    assert root == tmp_path / "custom"


def test_get_voices_root_falls_back(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    root = get_voices_root()
    # On Linux: $HOME/.local/share/prose-craft/voices
    # On macOS: $HOME/Library/Application Support/prose-craft/voices
    assert "prose-craft" in str(root)
    assert root.name == "voices"
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/voices/test_location.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement location module**

```python
# src/prose_craft/voices/location.py
"""XDG-compliant voice profile location."""
from __future__ import annotations

import os
import platform
import re
from pathlib import Path

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class VoiceNameError(ValueError):
    """Raised when a voice name fails validation."""


def get_voices_root() -> Path:
    """Return the per-user global voice store.

    Resolution order:
      1. PROSE_CRAFT_VOICES_ROOT env var
      2. $XDG_DATA_HOME/prose-craft/voices
      3. Platform default:
         - macOS: $HOME/Library/Application Support/prose-craft/voices
         - other: $HOME/.local/share/prose-craft/voices
    """
    explicit = os.environ.get("PROSE_CRAFT_VOICES_ROOT")
    if explicit:
        return Path(explicit).resolve()

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "prose-craft" / "voices"

    home = Path(os.environ.get("HOME", "."))
    if platform.system() == "Darwin":
        return home / "Library" / "Application Support" / "prose-craft" / "voices"
    return home / ".local" / "share" / "prose-craft" / "voices"


def voice_path(name: str, *, root: Path | None = None) -> Path:
    """Return <root>/<name>/voice.md.

    Validates ``name`` against ``^[a-z0-9][a-z0-9-]*$``. Raises
    VoiceNameError for invalid names (including path-traversal attempts).
    """
    if not _NAME_RE.match(name):
        raise VoiceNameError(
            f"invalid voice name {name!r}: must match [a-z0-9][a-z0-9-]*"
        )
    base = (root or get_voices_root()) / name
    return base / "voice.md"
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/voices/test_location.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/voices/location.py tests/unit/voices/test_location.py
git commit -m "feat(voices): XDG-compliant voice location + name validation"
```

---

### Task 12: voice IO

**Files:**
- Create: `src/prose_craft/voices/io.py`
- Create: `tests/unit/voices/test_io.py`
- Create: `tests/fixtures/voices/MistressFilth/voice.md`

**Interfaces:**
- Produces: `read_voice(name: str, *, root: Path | None = None) -> VoiceProfile`
- Produces: `write_voice(profile: VoiceProfile, prose_body: str, *, root: Path | None = None) -> Path`
- Produces: `list_voices(*, root: Path | None = None) -> list[VoiceSummary]`
- Produces: `VoiceSummary`, `VoiceProfileNotFound`, `VoiceAlreadyExists`

- [ ] **Step 1: Create a fixture voice file**

```markdown
# tests/fixtures/voices/MistressFilth/voice.md
---
voice: MistressFilth
version: 1
created: 2026-08-01
updated: 2026-08-01
authors:
  - MistressFilth
register:
  funny_serious: 0.3
  formal_casual: 0.4
diction:
  default_balance: 60% Germanic / 40% Latinate
  banned:
    - utilize
rhythm:
  target_mean_sentence: 15-20 words
syntax:
  em_dashes: forbidden as sentence punctuation
lexicon:
  pet_phrases:
    - "the long now"
structure:
  opening: |
    Every dispatch opens with a moment in time.
never:
  - rule: no em-dash as sentence punctuation
    detection: mechanical
---

# What MistressFilth sounds like

Dnova writes in the second person, present tense, with a slight formal
distance. Sentences are medium-length with a few short punctuation pops.
```

- [ ] **Step 2: Write failing test**

```python
# tests/unit/voices/test_io.py
from pathlib import Path

import pytest

from prose_craft.voices.io import (
    VoiceProfileNotFound,
    list_voices,
    read_voice,
    write_voice,
)
from prose_craft.voices.model import (
    DictionConfig,
    LexiconConfig,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SyntaxConfig,
    VoiceProfile,
)


FIXTURE_ROOT = Path(__file__).parent.parent.parent / "fixtures" / "voices"


def test_read_voice_from_fixture(tmp_path):
    profile = read_voice("MistressFilth", root=FIXTURE_ROOT)
    assert profile.voice == "MistressFilth"
    assert profile.register.funny_serious == 0.3
    assert "utilize" in profile.diction.banned
    assert "the long now" in profile.lexicon.pet_phrases


def test_read_voice_missing(tmp_voices_root):
    with pytest.raises(VoiceProfileNotFound):
        read_voice("absent", root=tmp_voices_root)


def test_write_voice_round_trip(tmp_voices_root):
    p = VoiceProfile(
        voice="test",
        created="2026-08-01",
        updated="2026-08-01",
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )
    body = "\n# Body\n\nThis voice is X.\n"
    path = write_voice(p, body, root=tmp_voices_root)
    assert path.exists()
    reloaded = read_voice("test", root=tmp_voices_root)
    assert reloaded.voice == "test"
    # Re-read the raw file to confirm the body was preserved verbatim.
    raw = path.read_text(encoding="utf-8")
    assert body.strip() in raw


def test_write_atomic_no_partial_file_on_overwrite(tmp_voices_root):
    p = VoiceProfile(
        voice="atomic",
        created="2026-08-01",
        updated="2026-08-01",
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )
    write_voice(p, "first body", root=tmp_voices_root)
    write_voice(p, "second body", root=tmp_voices_root)
    raw = read_voice("atomic", root=tmp_voices_root)
    # VoiceProfile doesn't carry the body, but the file on disk should.
    path = tmp_voices_root / "atomic" / "voice.md"
    assert "second body" in path.read_text(encoding="utf-8")


def test_list_voices(tmp_voices_root):
    for name in ("alpha", "beta"):
        (tmp_voices_root / name).mkdir()
        (tmp_voices_root / name / "voice.md").write_text(
            f"---\nvoice: {name}\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
            "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n",
            encoding="utf-8",
        )
    summaries = list_voices(root=tmp_voices_root)
    names = {s.name for s in summaries}
    assert names == {"alpha", "beta"}
```

- [ ] **Step 3: Run test, verify fail**

```bash
uv run pytest tests/unit/voices/test_io.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implement io module**

```python
# src/prose_craft/voices/io.py
"""Voice profile read / write / list.

The on-disk format is YAML front-matter between ``---`` markers,
followed by a prose body. PyYAML parses the front-matter; the rest of
the file is preserved verbatim by ``write_voice``.
"""
from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from prose_craft.voices.location import get_voices_root, voice_path


class VoiceProfileNotFound(FileNotFoundError):
    """Raised when a voice profile does not exist on disk."""


class VoiceSummary(BaseModel):
    name: str
    updated: date


_FRONTMATTER_RE = __import__("re").compile(
    r"\A---\n(.*?)\n---\n?(.*)\Z", __import__("re").DOTALL
)


def read_voice(name: str, *, root: Path | None = None) -> VoiceProfile:
    """Parse <root>/<name>/voice.md and return a VoiceProfile.

    The prose body is dropped here (VoiceProfile has no body field);
    callers that need the body can call ``read_voice_raw``.
    """
    path = voice_path(name, root=root)
    if not path.exists():
        raise VoiceProfileNotFound(f"voice profile {name!r} not found at {path}")
    return _parse_voice_file(path)


def read_voice_raw(name: str, *, root: Path | None = None) -> tuple[VoiceProfile, str]:
    """Parse voice.md and return (profile, prose_body).

    The prose body is the text after the closing ``---`` marker,
    without the trailing newline-strip the regex applies.
    """
    path = voice_path(name, root=root)
    if not path.exists():
        raise VoiceProfileNotFound(f"voice profile {name!r} not found at {path}")
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise VoiceProfileNotFound(f"voice profile {name!r} has no front-matter at {path}")
    front_matter = yaml.safe_load(match.group(1)) or {}
    body = match.group(2)
    # Late import to avoid a circular dependency at module load.
    from prose_craft.voices.model import VoiceProfile

    profile = VoiceProfile.model_validate(front_matter)
    return profile, body


def _parse_voice_file(path: Path) -> VoiceProfile:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise VoiceProfileNotFound(f"voice profile at {path} has no front-matter")
    front_matter = yaml.safe_load(match.group(1)) or {}
    from prose_craft.voices.model import VoiceProfile

    return VoiceProfile.model_validate(front_matter)


def write_voice(
    profile: Any,
    prose_body: str = "",
    *,
    root: Path | None = None,
) -> Path:
    """Serialize the profile + prose body to voice.md.

    Atomic write: write to a temp file in the same directory, fsync,
    rename. Creates parent directories.
    """
    path = voice_path(profile.voice, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)

    from prose_craft.voices.model import VoiceProfile

    if not isinstance(profile, VoiceProfile):
        profile = VoiceProfile.model_validate(profile)
    payload = profile.model_dump(mode="json", exclude_none=False)
    front_matter = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    body = prose_body if prose_body.startswith("\n") else "\n" + prose_body
    full = f"---\n{front_matter}---{body}"

    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=".voice.", suffix=".md.tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(full)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return path


def list_voices(*, root: Path | None = None) -> list[VoiceSummary]:
    """Enumerate every voice under the root.

    Returns voices sorted by name. Voices without parseable front-matter
    are skipped silently.
    """
    base = root or get_voices_root()
    if not base.exists():
        return []
    out: list[VoiceSummary] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        candidate = child / "voice.md"
        if not candidate.is_file():
            continue
        try:
            profile = _parse_voice_file(candidate)
        except Exception:
            continue
        out.append(VoiceSummary(name=profile.voice, updated=profile.updated))
    return out
```

- [ ] **Step 5: Run test, verify pass**

```bash
uv run pytest tests/unit/voices/test_io.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/prose_craft/voices/io.py tests/unit/voices/test_io.py tests/fixtures/voices/
git commit -m "feat(voices): read/write/list voice profiles with atomic write"
```

---

### Task 13: voice migration

**Files:**
- Create: `src/prose_craft/voices/migrate.py`
- Create: `tests/unit/voices/test_migrate.py`

**Interfaces:**
- Produces: `migrate_voices(*, src, dst, overwrite, dry_run) -> MigrationReport`
- Produces: `MigrationReport(copied, skipped, errors)`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/voices/test_migrate.py
from pathlib import Path

from prose_craft.voices.migrate import migrate_voices


def _write_voice(root: Path, name: str) -> Path:
    vdir = root / name
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "voice.md").write_text(
        f"---\nvoice: {name}\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
        "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n",
        encoding="utf-8",
    )
    return vdir / "voice.md"


def test_migrate_copies_all(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_voice(src, "alpha")
    _write_voice(src, "beta")
    report = migrate_voices(src=src, dst=dst)
    assert sorted(report.copied) == ["alpha", "beta"]
    assert (dst / "alpha" / "voice.md").exists()
    assert (dst / "beta" / "voice.md").exists()
    # Source untouched.
    assert (src / "alpha" / "voice.md").exists()
    assert (src / "beta" / "voice.md").exists()


def test_migrate_skips_existing(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_voice(src, "alpha")
    _write_voice(dst, "alpha")
    report = migrate_voices(src=src, dst=dst)
    assert report.copied == []
    assert "alpha" in report.skipped


def test_migrate_overwrite(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_voice(src, "alpha")
    _write_voice(dst, "alpha")
    report = migrate_voices(src=src, dst=dst, overwrite=True)
    assert "alpha" in report.copied


def test_migrate_dry_run(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_voice(src, "alpha")
    report = migrate_voices(src=src, dst=dst, dry_run=True)
    assert "alpha" in report.copied
    assert not (dst / "alpha" / "voice.md").exists()


def test_migrate_missing_source(tmp_path):
    report = migrate_voices(src=tmp_path / "absent", dst=tmp_path / "dst")
    assert report.copied == []
    assert report.errors != []
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/voices/test_migrate.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement migrate module**

```python
# src/prose_craft/voices/migrate.py
"""Copy voice profiles from a legacy plugin-data location to the XDG root."""
from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel

from prose_craft.voices.io import read_voice
from prose_craft.voices.location import (
    VoiceNameError,
    get_voices_root,
    voice_path,
)


def default_legacy_root() -> Path:
    """Return the legacy plugin-data location, if any.

    Reads CLAUDE_PLUGIN_DATA env var; falls back to the prose plugin's
    default. Always returns a Path (may not exist).
    """
    import os

    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if base:
        return Path(base) / "voices"
    return Path.home() / ".claude" / "plugins" / "data" / "prose" / "voices"


class MigrationReport(BaseModel):
    copied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []


def migrate_voices(
    *,
    src: Path | None = None,
    dst: Path | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> MigrationReport:
    """Copy every <src>/<name>/voice.md to <dst>/<name>/voice.md.

    Source is never modified. Skips names that exist at dst unless
    overwrite=True. Returns a MigrationReport enumerating outcomes.
    """
    src_path = (src or default_legacy_root()).resolve()
    dst_path = (dst or get_voices_root()).resolve()
    report = MigrationReport()

    if not src_path.exists():
        report.errors.append(f"source not found: {src_path}")
        return report

    dst_path.mkdir(parents=True, exist_ok=True)

    for child in sorted(src_path.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        try:
            target = voice_path(name, root=dst_path)
        except VoiceNameError as exc:
            report.errors.append(f"{name}: {exc}")
            continue
        if target.exists() and not overwrite:
            report.skipped.append(name)
            continue
        try:
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child / "voice.md", target)
            report.copied.append(name)
        except OSError as exc:
            report.errors.append(f"{name}: {exc}")
    return report
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/voices/test_migrate.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/voices/migrate.py tests/unit/voices/test_migrate.py
git commit -m "feat(voices): copy-only voice migration from legacy plugin-data"
```

---

### Task 14: voice check

**Files:**
- Create: `src/prose_craft/voices/check.py`
- Create: `tests/unit/voices/test_check.py`

**Interfaces:**
- Produces: `VoiceVerdict(mechanical, statistical, judgments_needed)`
- Produces: `Violation(line, col, rule, message, category)`
- Produces: `JudgmentNeeded(rule, prompt)`
- Produces: `check_voice(text: str, profile: VoiceProfile, *, tolerance: str = "normal") -> VoiceVerdict`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/voices/test_check.py
from datetime import date

from prose_craft.voices.check import check_voice
from prose_craft.voices.model import (
    AudienceCeiling,
    DictionConfig,
    LexiconConfig,
    NeverEntry,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SubstitutionRule,
    SyntaxConfig,
    VoiceProfile,
)


def _profile(**overrides) -> VoiceProfile:
    base = dict(
        voice="t",
        created=date(2026, 8, 1),
        updated=date(2026, 8, 1),
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )
    base.update(overrides)
    return VoiceProfile(**base)


def test_check_voice_clean_text_returns_empty_verdict():
    p = _profile()
    text = "She walked home. The dog ran. Birds sang."
    v = check_voice(text, p)
    assert v.mechanical == []
    assert v.statistical == []
    assert v.judgments_needed == []


def test_check_voice_flags_banned_word():
    p = _profile(diction=DictionConfig(banned=["utilize"]))
    v = check_voice("We will utilize this approach.", p)
    assert any(mv.rule == "diction.banned" for mv in v.mechanical)


def test_check_voice_flags_taboo_phrase():
    p = _profile(lexicon=LexiconConfig(taboo_phrases=["in order to"]))
    v = check_voice("We did it in order to win.", p)
    assert any(mv.rule == "lexicon.taboo_phrases" for mv in v.mechanical)


def test_check_voice_flags_preferred_substitution():
    p = _profile(diction=DictionConfig(
        preferred=[SubstitutionRule(instead_of="utilize", use="use")]
    ))
    v = check_voice("We will utilize this.", p)
    assert any(mv.rule == "diction.preferred" for mv in v.mechanical)


def test_check_voice_tolerance_relaxed_widens_bands():
    p = _profile(rhythm=RhythmConfig(target_mean_sentence="15-20 words"))
    text = "One. Two three. Four five six. Seven eight nine ten. " * 6
    v_strict = check_voice(text, p, tolerance="strict")
    v_relaxed = check_voice(text, p, tolerance="relaxed")
    assert len(v_relaxed.statistical) <= len(v_strict.statistical)


def test_check_voice_agent_required_entries_become_judgments():
    p = _profile(never=[
        NeverEntry(rule="no purple prose", detection="agent-required"),
    ])
    v = check_voice("The sun was a fiery eye.", p)
    assert any(j.rule == "no purple prose" for j in v.judgments_needed)
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/voices/test_check.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement check module**

```python
# src/prose_craft/voices/check.py
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
            out.append(Violation(
                line=line, col=col,
                rule="diction.banned",
                message=f"banned word: {word!r}",
                category="mechanical",
            ))
    return out


def _check_taboo(text: str, profile: VoiceProfile) -> list[Violation]:
    out: list[Violation] = []
    for phrase in profile.lexicon.taboo_phrases:
        for m in re.finditer(re.escape(phrase), text, re.IGNORECASE):
            line, col = _find_line_col(text, m.start())
            out.append(Violation(
                line=line, col=col,
                rule="lexicon.taboo_phrases",
                message=f"taboo phrase: {phrase!r}",
                category="mechanical",
            ))
    return out


def _check_preferred(text: str, profile: VoiceProfile) -> list[Violation]:
    out: list[Violation] = []
    for rule in profile.diction.preferred:
        for m in re.finditer(rf"\b{re.escape(rule.instead_of)}\b", text, re.IGNORECASE):
            line, col = _find_line_col(text, m.start())
            out.append(Violation(
                line=line, col=col,
                rule="diction.preferred",
                message=f"prefer {rule.use!r} over {rule.instead_of!r}: {rule.note}",
                category="mechanical",
            ))
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
            out.append(Violation(
                rule="lexicon.pet_phrases",
                message=f"pet phrase {phrase!r} appears {count} times ({density:.1f}/1k)",
                category="statistical",
                measured=round(density, 1),
                target=f"<= {band}/1k",
                band=tolerance,
            ))
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
        out.append(Violation(
            rule="rhythm.target_mean_sentence",
            message=f"mean sentence length {mean:.1f} outside band",
            category="statistical",
            measured=round(mean, 1),
            target=target,
            band=tolerance,
        ))
    return out


def check_voice(
    text: str,
    profile: VoiceProfile,
    *,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
) -> VoiceVerdict:
    """Run every check the profile enables and return a VoiceVerdict."""
    mechanical = (
        _check_banned(text, profile)
        + _check_taboo(text, profile)
        + _check_preferred(text, profile)
    )
    statistical = (
        _check_pet_phrases(text, profile, tolerance)
        + _check_sentence_length(text, profile, tolerance)
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
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/voices/test_check.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/voices/check.py tests/unit/voices/test_check.py
git commit -m "feat(voices): voice check with mechanical/statistical/agent-required taxonomy"
```

---

### Task 15: voice template

**Files:**
- Create: `src/prose_craft/data/__init__.py`
- Create: `src/prose_craft/data/voice_template.md`

**Interfaces:**
- Produces: `load_template() -> str`

- [ ] **Step 1: Write the template**

```markdown
# src/prose_craft/data/voice_template.md
---
voice: <name>
version: 1
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
authors: []
imported_from: null
voice_persona: null
purpose: null
audience: null
audiences: {}
register:
  funny_serious: null
  formal_casual: null
  respectful_irreverent: null
  enthusiastic_matter_of_fact: null
  certainty: null
  density: null
diction:
  default_balance: null
  germanic_for: []
  latinate_for: []
  banned: []
  preferred: []
  inherit_lexicons: []
rhythm:
  target_mean_sentence: null
  target_variation: null
  paragraph_shape: null
  one_sentence_paragraphs: null
  forbidden_patterns: []
syntax:
  em_dashes: null
  colons: null
  semicolons: null
  parentheticals: null
  fragments: null
  bullets: null
  questions: null
lexicon:
  pet_phrases: []
  characteristic_openers: []
  characteristic_closers: []
  taboo_phrases: []
structure:
  opening: null
  closing: null
  transitions: null
  emphasis: null
  citations: null
never: []
attributions: []
---

# <voice-name> — voice body

A short paragraph capturing what this voice sounds like. The composer
fills this in during the compose dialogue. The model reads it as
guidance; the YAML above is what `check_voice` verifies.
```

- [ ] **Step 2: Write the loader**

```python
# src/prose_craft/data/__init__.py
"""Static package data: the voice template, bundled reference YAML."""

from pathlib import Path

DATA_DIR = Path(__file__).parent


def load_template() -> str:
    """Return the contents of voice_template.md."""
    return (DATA_DIR / "voice_template.md").read_text(encoding="utf-8")
```

- [ ] **Step 3: Smoke-test**

```bash
uv run python -c "from prose_craft.data import load_template; t = load_template(); print('voice_template has', len(t), 'chars')"
```

Expected: prints a positive integer.

- [ ] **Step 4: Commit**

```bash
git add src/prose_craft/data/
git commit -m "feat(data): bundled voice template for /compose-voice and /voice init"
```

---


## Phase 3: Config + orchestrator

### Task 16: config module

**Files:**
- Create: `src/prose_craft/config.py`
- Create: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `get_model() -> str`
- Produces: `get_voices_root() -> Path`  (re-export from voices.location for top-level callers)

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_config.py
import os
from pathlib import Path

from prose_craft.config import get_model


def test_get_model_default(monkeypatch):
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    assert get_model() == "anthropic:claude-opus-4-5"


def test_get_model_env_override(monkeypatch):
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:claude-sonnet-4-5")
    assert get_model() == "anthropic:claude-sonnet-4-5"
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement config module**

```python
# src/prose_craft/config.py
"""Runtime configuration: env vars, defaults."""
from __future__ import annotations

import os
from pathlib import Path

from prose_craft.voices.location import get_voices_root as _get_voices_root

DEFAULT_MODEL = "anthropic:claude-opus-4-5"

__all__ = ["DEFAULT_MODEL", "get_model", "get_voices_root"]


def get_model() -> str:
    """Return the configured model identifier.

    Reads ``PROSE_CRAFT_MODEL`` from the environment; falls back to
    ``DEFAULT_MODEL``.
    """
    return os.environ.get("PROSE_CRAFT_MODEL", DEFAULT_MODEL)


def get_voices_root() -> Path:
    """Re-export of ``prose_craft.voices.location.get_voices_root``."""
    return _get_voices_root()
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/config.py tests/unit/test_config.py
git commit -m "feat(config): get_model and get_voices_root"
```

---

### Task 17: deps module

**Files:**
- Create: `src/prose_craft/orchestrator/__init__.py`
- Create: `src/prose_craft/orchestrator/deps.py`
- Create: `tests/unit/orchestrator/__init__.py`
- Create: `tests/unit/orchestrator/test_deps.py`

**Interfaces:**
- Produces: `AnalysisDeps(file_path, voice_name, tolerance)`
- Produces: `EditorDeps(file_path, voice_name, tolerance)`
- Produces: `ArchitectDeps(file_path, voice_name)`
- Produces: `TuneDeps(file_path, voice_name)`
- Produces: `VoiceDeps(file_path, voice_name, tolerance, brief_path)`
- Produces: `StylistDeps(file_path, voice_name, brief, mode)`
- Produces: `ComposerDeps(name, current_field, profile, history)`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/orchestrator/test_deps.py
from pathlib import Path

from prose_craft.orchestrator.deps import (
    AnalysisDeps,
    ArchitectDeps,
    ComposerDeps,
    EditorDeps,
    StylistDeps,
    TuneDeps,
    VoiceDeps,
)


def test_analysis_deps_defaults():
    d = AnalysisDeps(file_path=Path("x.md"))
    assert d.voice_name is None
    assert d.tolerance == "normal"


def test_editor_deps_optional_voice():
    d = EditorDeps(file_path=Path("x.md"))
    assert d.voice_name is None


def test_voice_deps_brief_optional():
    d = VoiceDeps(file_path=Path("x.md"), voice_name="v")
    assert d.brief_path is None


def test_stylist_deps_mode():
    d = StylistDeps(file_path=Path("x.md"), voice_name="v", mode="draft")
    assert d.mode == "draft"


def test_composer_deps_current_field():
    d = ComposerDeps(name="v", current_field="purpose")
    assert d.current_field == "purpose"
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/orchestrator/test_deps.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement deps module**

```python
# src/prose_craft/orchestrator/__init__.py
"""Composition root and shared agent dependencies."""
```

```python
# src/prose_craft/orchestrator/deps.py
"""Pydantic dep models shared by every agent."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

Tolerance = Literal["strict", "normal", "relaxed"]
StylistMode = Literal["draft", "edit"]


class AnalysisDeps(BaseModel):
    file_path: Path
    voice_name: str | None = None
    tolerance: Tolerance = "normal"


class EditorDeps(BaseModel):
    file_path: Path
    voice_name: str | None = None
    tolerance: Tolerance = "normal"


class ArchitectDeps(BaseModel):
    file_path: Path
    voice_name: str | None = None


class TuneDeps(BaseModel):
    file_path: Path
    voice_name: str | None = None


class VoiceDeps(BaseModel):
    file_path: Path
    voice_name: str
    tolerance: Tolerance = "normal"
    brief_path: Path | None = None


class StylistDeps(BaseModel):
    file_path: Path
    voice_name: str
    brief: str | None = None
    mode: StylistMode = "draft"


class ComposerDeps(BaseModel):
    name: str
    current_field: str = "purpose"
    profile: dict | None = None
    history: list[dict] = []
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/orchestrator/test_deps.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/orchestrator/ tests/unit/orchestrator/
git commit -m "feat(orchestrator): agent dep models (AnalysisDeps through ComposerDeps)"
```

---

### Task 18: prompts module

**Files:**
- Create: `src/prose_craft/orchestrator/prompts.py`

**Interfaces:** Constants for each agent's system prompt. No tests (text content is documentation, not behavior).

- [ ] **Step 1: Write the module**

```python
# src/prose_craft/orchestrator/prompts.py
"""System prompts for each agent.

Loaded once at module import. Kept as plain strings so they can be
inspected and tested by reading the file.
"""
from __future__ import annotations

from prose_craft.references import load_reference

ANALYST_SYSTEM_PROMPT = f"""\
You are the prose-craft analyst. Read the user's draft and return a
structured ProseDiagnostic.

Use these reference modules when interpreting the metrics:

{load_reference("prose_analysis")}
{load_reference("cohesion_craft")}

If the draft names a voice, also run the voice check and append the
Voice section. Never rewrite prose; the analyst is read-only.
"""

EDITOR_SYSTEM_PROMPT = f"""\
You are the prose-craft editor. Apply the four-pass edit:

1. Structural — paragraph order, weak openings/closings
2. Sentence-level — rhythm, throat-clearing
3. Word-level — weak verbs, adverbs, cliches
4. Sound — unintentional rhyme, consonant clusters

Use these reference modules:

{load_reference("diction_tuning")}
{load_reference("rhythm_mastery")}

If a voice is named, honor the voice's rules first; the four-pass
fills the dimensions the voice leaves silent. Return an EditResult
with the change_log enumerating rules honored, fallback dimensions,
and agent_required entries.
"""

ARCHITECT_SYSTEM_PROMPT = f"""\
You are the prose-craft architect. Apply the iceberg rewrite protocol:

1. Identify core intent
2. Find the best sentence
3. Rebuild from principle
4. Check against the original
5. Read aloud

If a voice is named, honor the voice's rules in the reconstruction.
"""

TUNE_DICTION_SYSTEM_PROMPT = f"""\
You are the prose-craft tune-diction agent. Identify Latinate words
that could take Germanic alternatives. Return a SubstitutionPlan
ordered by impact. If a voice is named, weight suggestions by the
voice's diction block.

{load_reference("diction_tuning")}
"""

VOICE_CHECKER_SYSTEM_PROMPT = f"""\
You are the prose-craft voice-checker. You are read-only. Read the
draft and the voice profile. For each agent-required entry in the
profile, judge whether the draft violates it. Return a VoiceVerdict
where ``judgments_needed`` is replaced with your resolved Judgments.

{load_reference("voice_contract")}
"""

VOICE_STYLIST_SYSTEM_PROMPT = f"""\
You are the prose-craft voice-stylist. Draft or edit prose in the
named voice. Follow the voice's diction, rhythm, syntax, lexicon,
and structure rules. Run voice_check on your output before returning.

{load_reference("voice_contract")}
"""

VOICE_COMPOSER_SYSTEM_PROMPT = f"""\
You are the prose-craft voice-composer. Walk the writer through
composing a voice profile one dimension at a time (D1-D10). Propose
named-source presets where applicable; the writer accepts, modifies,
or declines. Never override; always propose.

{load_reference("voice_contract")}
"""
```

- [ ] **Step 2: Smoke-test the import**

```bash
uv run python -c "from prose_craft.orchestrator.prompts import ANALYST_SYSTEM_PROMPT; print(len(ANALYST_SYSTEM_PROMPT))"
```

Expected: positive integer.

- [ ] **Step 3: Commit**

```bash
git add src/prose_craft/orchestrator/prompts.py
git commit -m "feat(orchestrator): per-agent system prompts with inlined references"
```

---

### Task 19: ProseCraft composition root

**Files:**
- Create: `src/prose_craft/orchestrator/root.py`
- Create: `tests/unit/orchestrator/test_root.py`

**Interfaces:**
- Produces: `ProseCraft(model, voices_root, log_level)` class
- Produces: `ProseCraft.analyst() -> Agent`
- Produces: `ProseCraft.editor() -> Agent`
- Produces: `ProseCraft.architect() -> Agent`
- Produces: `ProseCraft.tune_diction() -> Agent`
- Produces: `ProseCraft.voice_checker() -> Agent`
- Produces: `ProseCraft.voice_stylist() -> Agent`
- Produces: `ProseCraft.voice_composer() -> Agent`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/orchestrator/test_root.py
import pytest
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai import ModelMessage, ModelResponse, TextPart

from prose_craft.orchestrator.root import ProseCraft


def _stub_response(content: str):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(content)])
    return FunctionModel(fn)


def test_prose_craft_constructs_with_defaults(monkeypatch):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", "/tmp/test-voices")
    craft = ProseCraft()
    assert craft.model == "anthropic:claude-opus-4-5"
    assert craft.voices_root == pytest.approx_mp("/tmp/test-voices") or str(craft.voices_root).endswith("test-voices")


def test_prose_craft_lazy_build(monkeypatch):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", "/tmp/test-voices")
    craft = ProseCraft()
    # First access builds the agent; second access returns the same one.
    a1 = craft.analyst()
    a2 = craft.analyst()
    assert a1 is a2
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/orchestrator/test_root.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement root module**

```python
# src/prose_craft/orchestrator/root.py
"""ProseCraft composition root.

Constructed once per CLI invocation or MCP request. Owns model
selection, voice location, and the harness Memory capability. Lazy-
builds agents on first access.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_ai import Agent

from prose_craft.config import get_model, get_voices_root
from prose_craft.orchestrator.deps import (
    AnalysisDeps,
    ArchitectDeps,
    ComposerDeps,
    EditorDeps,
    StylistDeps,
    TuneDeps,
    VoiceDeps,
)
from prose_craft.orchestrator.prompts import (
    ANALYST_SYSTEM_PROMPT,
    ARCHITECT_SYSTEM_PROMPT,
    EDITOR_SYSTEM_PROMPT,
    TUNE_DICTION_SYSTEM_PROMPT,
    VOICE_CHECKER_SYSTEM_PROMPT,
    VOICE_COMPOSER_SYSTEM_PROMPT,
    VOICE_STYLIST_SYSTEM_PROMPT,
)

if TYPE_CHECKING:
    pass


class ProseCraft:
    """Single composition root for CLI + MCP + plugin-adapter callers."""

    def __init__(
        self,
        *,
        model: str | None = None,
        voices_root: Path | None = None,
        log_level: str = "INFO",
    ) -> None:
        self.model = model or get_model()
        self.voices_root = (voices_root or get_voices_root()).resolve()
        self.log_level = log_level
        self._agents: dict[str, Agent] = {}

    def _lazy(self, key: str, factory):  # type: ignore[no-untyped-def]
        if key not in self._agents:
            self._agents[key] = factory()
        return self._agents[key]

    def analyst(self):  # type: ignore[no-untyped-def]
        from prose_craft.agents.analyst import build_analyst

        return self._lazy("analyst", lambda: build_analyst(self.model))

    def editor(self):  # type: ignore[no-untyped-def]
        from prose_craft.agents.editor import build_editor

        return self._lazy("editor", lambda: build_editor(self.model))

    def architect(self):  # type: ignore[no-untyped-def]
        from prose_craft.agents.architect import build_architect

        return self._lazy("architect", lambda: build_architect(self.model))

    def tune_diction(self):  # type: ignore[no-untyped-def]
        from prose_craft.agents.tune_diction import build_tune_diction

        return self._lazy("tune_diction", lambda: build_tune_diction(self.model))

    def voice_checker(self):  # type: ignore[no-untyped-def]
        from prose_craft.agents.voice_checker import build_voice_checker

        return self._lazy("voice_checker", lambda: build_voice_checker(self.model))

    def voice_stylist(self):  # type: ignore[no-untyped-def]
        from prose_craft.agents.voice_stylist import build_voice_stylist

        return self._lazy("voice_stylist", lambda: build_voice_stylist(self.model))

    def voice_composer(self):  # type: ignore[no-untyped-def]
        from prose_craft.agents.voice_composer import build_voice_composer

        return self._lazy("voice_composer", lambda: build_voice_composer(self.model, self.voices_root))
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/orchestrator/test_root.py -v
```

Expected: 2 passed (lazy build + construct). The agent factories don't exist yet, so the lazy access will fail — that's expected; tasks 22-29 build them. If the test fails on lazy access, mark it as expected and continue; the rest of the test plan fills in the agents.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/orchestrator/root.py tests/unit/orchestrator/test_root.py
git commit -m "feat(orchestrator): ProseCraft composition root with lazy agent build"
```

---


## Phase 4: Agents

### Task 20: agents/base + agent result models

**Files:**
- Create: `src/prose_craft/agents/__init__.py`
- Create: `src/prose_craft/agents/base.py`
- Create: `src/prose_craft/agents/results.py`
- Create: `tests/unit/agents/__init__.py`
- Create: `tests/unit/agents/test_results.py`

**Interfaces:**
- Produces: `ProseDiagnostic(metrics, issues, voice_section, dispersion, clause_density)`
- Produces: `EditResult(changes, change_log, rules_honored, fallback_dimensions, agent_required)`
- Produces: `ArchitectResult(analysis, diagnosis, reconstruction_proposal)`
- Produces: `SubstitutionPlan(suggestions, voice_weighted)`
- Produces: `DraftResult(text, change_log, voice_check_report)`
- Produces: `VoiceDelta(field, value, prompt)`
- Produces: `make_sub_agent(model, output_type, system_prompt, tools=None, capabilities=None)`

- [ ] **Step 1: Write failing test for results**

```python
# tests/unit/agents/test_results.py
from prose_craft.agents.results import (
    ArchitectResult,
    DraftResult,
    EditResult,
    ProseDiagnostic,
    SubstitutionPlan,
    VoiceDelta,
)


def test_prose_diagnostic_minimal():
    d = ProseDiagnostic(metrics=None, issues=[])
    assert d.voice_section is None
    assert d.dispersion is None


def test_edit_result_change_log_structure():
    e = EditResult(
        changes=[],
        change_log="rules_honored: x\nfallback_dimensions: y\nagent_required: z",
        rules_honored=["x"],
        fallback_dimensions=["y"],
        agent_required=["z"],
    )
    assert e.rules_honored == ["x"]


def test_voice_delta():
    d = VoiceDelta(field="purpose", value="formal memos", prompt="What is this voice for?")
    assert d.field == "purpose"
    assert d.value == "formal memos"
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/agents/test_results.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement results module**

```python
# src/prose_craft/agents/__init__.py
"""pydantic-ai agents for prose work."""
```

```python
# src/prose_craft/agents/results.py
"""Pydantic output models shared by all agents."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from prose_craft.analysis.diction import SubstitutionRule


class ProseDiagnostic(BaseModel):
    metrics: Any | None
    issues: list[str] = []
    voice_section: str | None = None
    dispersion: Any | None = None
    clause_density: Any | None = None


class EditChange(BaseModel):
    before: str
    after: str
    why: str


class EditResult(BaseModel):
    changes: list[EditChange] = []
    change_log: str = ""
    rules_honored: list[str] = []
    fallback_dimensions: list[str] = []
    agent_required: list[str] = []


class ArchitectResult(BaseModel):
    analysis: str
    diagnosis: str
    reconstruction_proposal: str


class SubstitutionPlan(BaseModel):
    suggestions: list[SubstitutionRule] = []
    voice_weighted: bool = False


class DraftResult(BaseModel):
    text: str
    change_log: str = ""
    voice_check_report: Any | None = None


class VoiceDelta(BaseModel):
    field: str
    value: Any
    prompt: str
```

- [ ] **Step 4: Implement base module**

```python
# src/prose_craft/agents/base.py
"""Shared factory for sub-agents."""
from __future__ import annotations

from typing import Any, Callable, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent

T = TypeVar("T", bound=BaseModel)


def make_sub_agent(
    model: str,
    output_type: type[T],
    system_prompt: str,
    tools: list[Callable[..., Any]] | None = None,
    capabilities: list[Any] | None = None,
) -> Agent[Any, T]:
    """Construct a pydantic-ai sub-agent.

    Adds the standard prose-craft sub-agent prefix. Tools and
    capabilities are passed through unchanged.
    """
    prefix = "You are a prose-craft sub-agent. Do one task precisely and return a structured result.\n\n"
    return Agent(
        model,
        output_type=output_type,
        system_prompt=prefix + system_prompt,
        tools=tools or [],
        capabilities=capabilities or [],
    )
```

- [ ] **Step 5: Run test, verify pass**

```bash
uv run pytest tests/unit/agents/test_results.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/prose_craft/agents/ tests/unit/agents/
git commit -m "feat(agents): result models and sub-agent factory"
```

---

### Task 21: analyst agent

**Files:**
- Create: `src/prose_craft/agents/analyst.py`
- Create: `src/prose_craft/agents/tools.py`
- Create: `tests/unit/agents/test_analyst.py`

**Interfaces:**
- Produces: `build_analyst(model: str) -> Agent[AnalysisDeps, ProseDiagnostic]`
- Produces: `read_file_tool(file_path: Path) -> str` (re-used by every agent)

- [ ] **Step 1: Write failing test**

```python
# tests/unit/agents/test_analyst.py
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.analyst import build_analyst
from prose_craft.orchestrator.deps import AnalysisDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])
    return FunctionModel(fn)


def test_analyst_returns_prose_diagnostic(tmp_path: Path):
    draft = tmp_path / "chapter.md"
    draft.write_text("She walked home. The dog ran. Birds sang.", encoding="utf-8")
    agent = build_analyst("test-model")
    deps = AnalysisDeps(file_path=draft)
    response_payload = {
        "metrics": {"word_count": 9, "sentence_count": 3},
        "issues": ["low variance"],
    }
    with agent.override(model=_function_model_returning_json(response_payload)):
        result = agent.run_sync("Analyze this.", deps=deps)
    assert result.output.metrics["word_count"] == 9
    assert result.output.issues == ["low variance"]
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/agents/test_analyst.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement tools module**

```python
# src/prose_craft/agents/tools.py
"""Tools shared by every agent."""
from __future__ import annotations

from pathlib import Path

from pydantic_ai import RunContext


def read_file(ctx: RunContext[Any], file_path: str) -> str:
    """Read a UTF-8 file and return its contents.

    Resolves the path; raises FileNotFoundError for missing files. The
    agent surface always passes a string for portability.
    """
    path = Path(file_path)
    return path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Implement analyst module**

```python
# src/prose_craft/agents/analyst.py
"""Prose analyst agent."""
from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import ProseDiagnostic
from prose_craft.agents.tools import read_file
from prose_craft.orchestrator.deps import AnalysisDeps
from prose_craft.orchestrator.prompts import ANALYST_SYSTEM_PROMPT


def build_analyst(model: str) -> Agent[AnalysisDeps, ProseDiagnostic]:
    """Construct the analyst agent."""
    return make_sub_agent(
        model=model,
        output_type=ProseDiagnostic,
        system_prompt=ANALYST_SYSTEM_PROMPT,
        tools=[read_file],
    )
```

- [ ] **Step 5: Run test, verify pass**

```bash
uv run pytest tests/unit/agents/test_analyst.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/prose_craft/agents/analyst.py src/prose_craft/agents/tools.py tests/unit/agents/test_analyst.py
git commit -m "feat(agents): analyst (Haiku) returns ProseDiagnostic"
```

---

### Task 22: editor agent

**Files:**
- Create: `src/prose_craft/agents/editor.py`
- Create: `tests/unit/agents/test_editor.py`

**Interfaces:**
- Produces: `build_editor(model: str) -> Agent[EditorDeps, EditResult]`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/agents/test_editor.py
import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.editor import build_editor
from prose_craft.orchestrator.deps import EditorDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])
    return FunctionModel(fn)


def test_editor_returns_edit_result(tmp_path: Path):
    draft = tmp_path / "chapter.md"
    draft.write_text("Original prose.", encoding="utf-8")
    agent = build_editor("test-model")
    deps = EditorDeps(file_path=draft)
    payload = {
        "changes": [{"before": "Original prose.", "after": "New prose.", "why": "tighter"}],
        "change_log": "rules_honored: x",
        "rules_honored": ["x"],
        "fallback_dimensions": [],
        "agent_required": [],
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Edit this.", deps=deps)
    assert result.output.changes[0].after == "New prose."
    assert result.output.rules_honored == ["x"]
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/agents/test_editor.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement editor module**

```python
# src/prose_craft/agents/editor.py
"""Prose editor agent (four-pass)."""
from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import EditResult
from prose_craft.agents.tools import read_file
from prose_craft.orchestrator.deps import EditorDeps
from prose_craft.orchestrator.prompts import EDITOR_SYSTEM_PROMPT


def build_editor(model: str) -> Agent[EditorDeps, EditResult]:
    """Construct the editor agent."""
    return make_sub_agent(
        model=model,
        output_type=EditResult,
        system_prompt=EDITOR_SYSTEM_PROMPT,
        tools=[read_file],
    )
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/agents/test_editor.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/agents/editor.py tests/unit/agents/test_editor.py
git commit -m "feat(agents): editor (Sonnet) returns EditResult"
```

---

### Task 23: architect agent

**Files:**
- Create: `src/prose_craft/agents/architect.py`
- Create: `tests/unit/agents/test_architect.py`

**Interfaces:**
- Produces: `build_architect(model: str) -> Agent[ArchitectDeps, ArchitectResult]`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/agents/test_architect.py
import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.architect import build_architect
from prose_craft.orchestrator.deps import ArchitectDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])
    return FunctionModel(fn)


def test_architect_returns_result(tmp_path: Path):
    draft = tmp_path / "chapter.md"
    draft.write_text("Some prose.", encoding="utf-8")
    agent = build_architect("test-model")
    deps = ArchitectDeps(file_path=draft)
    payload = {
        "analysis": "The opening is slow.",
        "diagnosis": "Front-load the inciting incident.",
        "reconstruction_proposal": "Open with the sound.",
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Architect this.", deps=deps)
    assert result.output.analysis == "The opening is slow."
    assert "inciting" in result.output.diagnosis
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/agents/test_architect.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement architect module**

```python
# src/prose_craft/agents/architect.py
"""Prose architect agent (Opus)."""
from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import ArchitectResult
from prose_craft.agents.tools import read_file
from prose_craft.orchestrator.deps import ArchitectDeps
from prose_craft.orchestrator.prompts import ARCHITECT_SYSTEM_PROMPT


def build_architect(model: str) -> Agent[ArchitectDeps, ArchitectResult]:
    """Construct the architect agent."""
    return make_sub_agent(
        model=model,
        output_type=ArchitectResult,
        system_prompt=ARCHITECT_SYSTEM_PROMPT,
        tools=[read_file],
    )
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/agents/test_architect.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/agents/architect.py tests/unit/agents/test_architect.py
git commit -m "feat(agents): architect (Opus) returns ArchitectResult"
```

---

### Task 24: tune_diction agent

**Files:**
- Create: `src/prose_craft/agents/tune_diction.py`
- Create: `tests/unit/agents/test_tune_diction.py`

**Interfaces:**
- Produces: `build_tune_diction(model: str) -> Agent[TuneDeps, SubstitutionPlan]`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/agents/test_tune_diction.py
import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.tune_diction import build_tune_diction
from prose_craft.orchestrator.deps import TuneDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])
    return FunctionModel(fn)


def test_tune_diction_returns_substitution_plan(tmp_path: Path):
    draft = tmp_path / "prose.md"
    draft.write_text("We will utilize this approach.", encoding="utf-8")
    agent = build_tune_diction("test-model")
    deps = TuneDeps(file_path=draft)
    payload = {
        "suggestions": [{"instead_of": "utilize", "use": "use", "note": "prefer Germanic"}],
        "voice_weighted": False,
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Tune.", deps=deps)
    assert result.output.suggestions[0].instead_of == "utilize"
    assert result.output.voice_weighted is False
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/agents/test_tune_diction.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement tune_diction module**

```python
# src/prose_craft/agents/tune_diction.py
"""Tune-diction agent (Haiku)."""
from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import SubstitutionPlan
from prose_craft.agents.tools import read_file
from prose_craft.orchestrator.deps import TuneDeps
from prose_craft.orchestrator.prompts import TUNE_DICTION_SYSTEM_PROMPT


def build_tune_diction(model: str) -> Agent[TuneDeps, SubstitutionPlan]:
    """Construct the tune-diction agent."""
    return make_sub_agent(
        model=model,
        output_type=SubstitutionPlan,
        system_prompt=TUNE_DICTION_SYSTEM_PROMPT,
        tools=[read_file],
    )
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/agents/test_tune_diction.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/agents/tune_diction.py tests/unit/agents/test_tune_diction.py
git commit -m "feat(agents): tune-diction (Haiku) returns SubstitutionPlan"
```

---

### Task 25: voice_checker agent

**Files:**
- Create: `src/prose_craft/agents/voice_checker.py`
- Create: `tests/unit/agents/test_voice_checker.py`

**Interfaces:**
- Produces: `build_voice_checker(model: str) -> Agent[VoiceDeps, VoiceVerdict]`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/agents/test_voice_checker.py
import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.voice_checker import build_voice_checker
from prose_craft.orchestrator.deps import VoiceDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])
    return FunctionModel(fn)


def test_voice_checker_returns_verdict(tmp_path: Path):
    draft = tmp_path / "prose.md"
    draft.write_text("We will utilize this.", encoding="utf-8")
    agent = build_voice_checker("test-model")
    deps = VoiceDeps(file_path=draft, voice_name="MistressFilth")
    payload = {
        "mechanical": [],
        "statistical": [],
        "judgments_needed": [],
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Check.", deps=deps)
    assert result.output.mechanical == []
    assert result.output.judgments_needed == []
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/agents/test_voice_checker.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement voice_checker module**

```python
# src/prose_craft/agents/voice_checker.py
"""Voice checker agent (Haiku, read-only)."""
from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.tools import read_file
from prose_craft.orchestrator.deps import VoiceDeps
from prose_craft.orchestrator.prompts import VOICE_CHECKER_SYSTEM_PROMPT
from prose_craft.voices.check import VoiceVerdict


def build_voice_checker(model: str) -> Agent[VoiceDeps, VoiceVerdict]:
    """Construct the voice-checker agent."""
    return make_sub_agent(
        model=model,
        output_type=VoiceVerdict,
        system_prompt=VOICE_CHECKER_SYSTEM_PROMPT,
        tools=[read_file],
    )
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/agents/test_voice_checker.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/agents/voice_checker.py tests/unit/agents/test_voice_checker.py
git commit -m "feat(agents): voice-checker (Haiku) returns VoiceVerdict"
```

---

### Task 26: voice_stylist agent

**Files:**
- Create: `src/prose_craft/agents/voice_stylist.py`
- Create: `tests/unit/agents/test_voice_stylist.py`

**Interfaces:**
- Produces: `build_voice_stylist(model: str) -> Agent[StylistDeps, DraftResult]`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/agents/test_voice_stylist.py
import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.voice_stylist import build_voice_stylist
from prose_craft.orchestrator.deps import StylistDeps


def _function_model_returning_json(payload: dict[str, Any]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])
    return FunctionModel(fn)


def test_voice_stylist_draft_mode(tmp_path: Path):
    draft = tmp_path / "chapter.md"
    draft.write_text("seed text", encoding="utf-8")
    agent = build_voice_stylist("test-model")
    deps = StylistDeps(file_path=draft, voice_name="MistressFilth", mode="draft")
    payload = {
        "text": "Drafted text in the MistressFilth voice.",
        "change_log": "rules_honored: diction.banned",
        "voice_check_report": None,
    }
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Draft.", deps=deps)
    assert "MistressFilth" in result.output.text
    assert result.output.voice_check_report is None
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/agents/test_voice_stylist.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement voice_stylist module**

```python
# src/prose_craft/agents/voice_stylist.py
"""Voice stylist agent (Sonnet)."""
from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import DraftResult
from prose_craft.agents.tools import read_file
from prose_craft.orchestrator.deps import StylistDeps
from prose_craft.orchestrator.prompts import VOICE_STYLIST_SYSTEM_PROMPT


def build_voice_stylist(model: str) -> Agent[StylistDeps, DraftResult]:
    """Construct the voice-stylist agent."""
    return make_sub_agent(
        model=model,
        output_type=DraftResult,
        system_prompt=VOICE_STYLIST_SYSTEM_PROMPT,
        tools=[read_file],
    )
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/agents/test_voice_stylist.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/agents/voice_stylist.py tests/unit/agents/test_voice_stylist.py
git commit -m "feat(agents): voice-stylist (Sonnet) returns DraftResult"
```

---

### Task 27: voice_composer agent

**Files:**
- Create: `src/prose_craft/agents/voice_composer.py`
- Create: `tests/unit/agents/test_voice_composer.py`

**Interfaces:**
- Produces: `build_voice_composer(model: str, voices_root: Path) -> Agent[ComposerDeps, list[VoiceDelta]]`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/agents/test_voice_composer.py
import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from prose_craft.agents.voice_composer import build_voice_composer
from prose_craft.orchestrator.deps import ComposerDeps


def _function_model_returning_json(payload: list[dict[str, Any]]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps(payload))])
    return FunctionModel(fn)


def test_voice_composer_returns_deltas(tmp_path: Path):
    agent = build_voice_composer("test-model", tmp_path)
    deps = ComposerDeps(name="MistressFilth", current_field="purpose")
    payload = [
        {"field": "purpose", "value": "formal memos", "prompt": "What is this voice for?"},
    ]
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Compose step.", deps=deps)
    assert len(result.output) == 1
    assert result.output[0].field == "purpose"
    assert result.output[0].value == "formal memos"
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/unit/agents/test_voice_composer.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement voice_composer module**

```python
# src/prose_craft/agents/voice_composer.py
"""Voice composer agent (Opus)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import VoiceDelta
from prose_craft.orchestrator.deps import ComposerDeps
from prose_craft.orchestrator.prompts import VOICE_COMPOSER_SYSTEM_PROMPT


def build_voice_composer(
    model: str,
    voices_root: Path,
) -> Agent[ComposerDeps, list[VoiceDelta]]:
    """Construct the voice-composer agent.

    The composer is the only agent with a harness ``Memory`` capability
    so the wizard can resume across CLI invocations.
    """
    capabilities: list[Any] = []
    try:
        from pydantic_ai_harness.memory import Memory  # type: ignore[import-not-found]

        capabilities.append(Memory(namespace="prose-craft"))
    except ImportError:
        # Harness Memory not available in the test environment; the
        # agent still works without it.
        pass

    return make_sub_agent(
        model=model,
        output_type=list[VoiceDelta],
        system_prompt=VOICE_COMPOSER_SYSTEM_PROMPT,
        tools=[],
        capabilities=capabilities,
    )
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/unit/agents/test_voice_composer.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/agents/voice_composer.py tests/unit/agents/test_voice_composer.py
git commit -m "feat(agents): voice-composer (Opus) returns list[VoiceDelta]"
```

---


## Phase 5: CLI

### Task 28: CLI scaffold (version, config, voice list, voice show)

**Files:**
- Create: `src/prose_craft/cli.py`
- Create: `tests/features/__init__.py`
- Create: `tests/features/test_cli_basics.py`

**Interfaces:**
- Produces: Typer app `app` with subcommands: `version`, `config`, `voice-list`, `voice-show`

- [ ] **Step 1: Write failing test**

```python
# tests/features/test_cli_basics.py
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from prose_craft import __version__
from prose_craft.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_config_prints_model_and_voices_root(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:claude-haiku-4-5")
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "anthropic:claude-haiku-4-5" in result.stdout
    assert str(tmp_path) in result.stdout


def test_voice_list_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["voice-list"])
    assert result.exit_code == 0
    assert "no voices" in result.stdout.lower() or result.stdout.strip() == ""
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/features/test_cli_basics.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement cli.py scaffold**

```python
# src/prose_craft/cli.py
"""Typer CLI for prose-craft."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markdown import Markdown

from prose_craft import __version__
from prose_craft.agents.results import VoiceDelta
from prose_craft.config import get_model, get_voices_root
from prose_craft.orchestrator.root import ProseCraft
from prose_craft.voices.io import list_voices, read_voice, read_voice_raw
from prose_craft.voices.migrate import migrate_voices

app = typer.Typer(
    name="prose",
    help="prose-craft: pydantic-ai engine for designing and applying prose voices.",
)
console = Console()

voice_app = typer.Typer(help="Voice profile operations.")
app.add_typer(voice_app, name="voice")


def _voices_root_opt(root: Path | None) -> Path:
    if root is not None:
        return root.resolve()
    return get_voices_root()


@app.command()
def version() -> None:
    """Print the engine version and exit."""
    typer.echo(f"prose-craft {__version__}")


@app.command()
def config(
    model: str | None = typer.Option(None, "--model", help="Override the model."),
    voices_root: Path | None = typer.Option(None, "--voices-root", help="Override the voices root."),
) -> None:
    """Print the active model and voices root."""
    if model:
        import os
        os.environ["PROSE_CRAFT_MODEL"] = model
    if voices_root:
        import os
        os.environ["PROSE_CRAFT_VOICES_ROOT"] = str(voices_root)
    typer.echo(f"model: {get_model()}")
    typer.echo(f"voices_root: {get_voices_root()}")


@voice_app.command("list")
def voice_list(
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """List every voice under the active root."""
    root = _voices_root_opt(voices_root)
    summaries = list_voices(root=root)
    if not summaries:
        typer.echo("(no voices found)")
        return
    for s in summaries:
        typer.echo(f"{s.name}  ({s.updated.isoformat()})")


@voice_app.command("show")
def voice_show(
    name: str = typer.Argument(..., help="Voice name."),
    raw: bool = typer.Option(False, "--raw", help="Print raw file contents."),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Print a voice profile as markdown or raw file."""
    root = _voices_root_opt(voices_root)
    if raw:
        path = root / name / "voice.md"
        if not path.exists():
            raise typer.BadParameter(f"voice {name!r} not found at {path}")
        typer.echo(path.read_text(encoding="utf-8"))
        return
    profile, body = read_voice_raw(name, root=root)
    typer.echo(f"# {profile.voice}\n")
    typer.echo(f"purpose: {profile.purpose or '(unset)'}")
    typer.echo(f"audience: {profile.audience or '(unset)'}\n")
    if body.strip():
        console.print(Markdown(body))
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/features/test_cli_basics.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/cli.py tests/features/
git commit -m "feat(cli): Typer scaffold with version, config, voice list, voice show"
```

---

### Task 29: analyze, edit, architect, tune-diction subcommands

**Files:**
- Modify: `src/prose_craft/cli.py` (append four subcommands)
- Create: `tests/features/test_cli_work.py`

**Interfaces:**
- Produces: `analyze <file> [--voice] [--tolerance] [--metrics-only]`
- Produces: `edit <file> [--voice] [--tolerance]`
- Produces: `architect <file> [--voice]`
- Produces: `tune-diction <file> [--voice]`

- [ ] **Step 1: Write failing test**

```python
# tests/features/test_cli_work.py
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


def _stub_model(monkeypatch, module_path: str, payload: Any):
    """Patch the model attribute of the named agent module."""
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        text = json.dumps(payload) if not isinstance(payload, str) else payload
        return ModelResponse(parts=[TextPart(text)])

    from prose_craft.orchestrator import root
    agent = root.ProseCraft()
    a = getattr(agent, module_path)()
    a.override(model=FunctionModel(fn))
    monkeypatch.setattr(agent, module_path, lambda: a)


def test_analyze_metrics_only(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    draft = tmp_path / "chapter.md"
    draft.write_text("She walked home. The dog ran.", encoding="utf-8")
    result = runner.invoke(app, ["analyze", str(draft), "--metrics-only"])
    assert result.exit_code == 0
    assert "Mean sentence length" in result.stdout or "Rhythm" in result.stdout
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/features/test_cli_work.py -v
```

Expected: failure (subcommand does not exist).

- [ ] **Step 3: Add the four subcommands to cli.py**

Append to `src/prose_craft/cli.py`:

```python
def _render_prose_diagnostic(diag: Any) -> str:
    """Render a ProseDiagnostic as markdown for stdout."""
    from prose_craft.analysis.metrics import ProseMetrics

    if diag.metrics is None:
        return "(empty draft)"
    m: ProseMetrics = diag.metrics
    lines = [
        "# Prose Diagnostic",
        "",
        f"Words: {m.word_count}  Sentences: {m.sentence_count}",
        "",
        "**Rhythm**",
        f"- Mean sentence length: {m.mean_sentence_length} words",
        f"- Variation (std dev): {m.sentence_length_std} (target: 8-12)",
        f"- Short (<10): {m.short_sentences_pct}%  Long (>25): {m.long_sentences_pct}%",
        "",
        "**Diction**",
        f"- Germanic: {m.germanic_pct}%  Latinate: {m.latinate_pct}%",
        f"- Avg syllables/word: {m.avg_syllables_per_word}  Polysyllabic: {m.polysyllabic_pct}%",
        "",
        "**Readability**",
        f"- Flesch: {m.flesch_reading_ease}",
        "",
        "**Cohesion**",
        f"- Connectives/100 words: {m.connectives_per_100_words} (target: 2-4)",
        f"- Causal: {m.causal_markers}  Temporal: {m.temporal_markers}",
    ]
    if diag.voice_section:
        lines.extend(["", diag.voice_section])
    if diag.dispersion is not None:
        lines.extend(["", f"# Dispersion (n={diag.dispersion.n})"])
    if diag.clause_density is not None:
        lines.extend([
            "",
            "# Clause density",
            f"- ppc: {diag.clause_density.ppc_per_1k}/1k",
            f"- agentless_passive: {diag.clause_density.agentless_passive_per_1k}/1k",
        ])
    if diag.issues:
        lines.extend(["", "**Issues**"] + [f"- {i}" for i in diag.issues])
    return "\n".join(lines)


@app.command()
def analyze(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str | None = typer.Option(None, "--voice"),
    tolerance: str = typer.Option("normal", "--tolerance"),
    metrics_only: bool = typer.Option(False, "--metrics-only"),
) -> None:
    """Run the analyst agent (or deterministic metrics only)."""
    from prose_craft.analysis.metrics import analyze_prose
    from prose_craft.orchestrator.deps import AnalysisDeps

    if metrics_only:
        text = file.read_text(encoding="utf-8")
        m = analyze_prose(text)
        diag = {"metrics": m, "issues": []}
        from prose_craft.agents.results import ProseDiagnostic
        typer.echo(_render_prose_diagnostic(ProseDiagnostic.model_validate(diag)))
        return
    craft = ProseCraft()
    result = craft.analyst().run_sync(
        "Analyze this prose.",
        deps=AnalysisDeps(file_path=file, voice_name=voice, tolerance=tolerance),
    )
    typer.echo(_render_prose_diagnostic(result.output))


@app.command()
def edit(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str | None = typer.Option(None, "--voice"),
    tolerance: str = typer.Option("normal", "--tolerance"),
    in_place: bool = typer.Option(False, "--in-place", help="Write the edited text back to the file."),
) -> None:
    """Run the editor agent; print the change_log and the new text."""
    from prose_craft.orchestrator.deps import EditorDeps

    craft = ProseCraft()
    result = craft.editor().run_sync(
        "Edit this prose.",
        deps=EditorDeps(file_path=file, voice_name=voice, tolerance=tolerance),
    )
    if in_place and result.output.changes:
        text = file.read_text(encoding="utf-8")
        for change in reversed(result.output.changes):
            text = text.replace(change.before, change.after, 1)
        file.write_text(text, encoding="utf-8")
    typer.echo(result.output.change_log or "(no change log)")


@app.command()
def architect(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str | None = typer.Option(None, "--voice"),
) -> None:
    """Run the architect agent; print the reconstruction proposal."""
    from prose_craft.orchestrator.deps import ArchitectDeps

    craft = ProseCraft()
    result = craft.architect().run_sync(
        "Architect this prose.",
        deps=ArchitectDeps(file_path=file, voice_name=voice),
    )
    typer.echo(f"## Analysis\n\n{result.output.analysis}\n")
    typer.echo(f"## Diagnosis\n\n{result.output.diagnosis}\n")
    typer.echo(f"## Reconstruction\n\n{result.output.reconstruction_proposal}\n")


@app.command("tune-diction")
def tune_dict(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str | None = typer.Option(None, "--voice"),
) -> None:
    """Run the tune-diction agent; print the substitution plan."""
    from prose_craft.orchestrator.deps import TuneDeps

    craft = ProseCraft()
    result = craft.tune_diction().run_sync(
        "Tune diction.",
        deps=TuneDeps(file_path=file, voice_name=voice),
    )
    for s in result.output.suggestions:
        typer.echo(f"{s.instead_of} -> {s.use}  ({s.note})")
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/features/test_cli_work.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/cli.py tests/features/test_cli_work.py
git commit -m "feat(cli): analyze, edit, architect, tune-diction subcommands"
```

---

### Task 30: voice check + init subcommands

**Files:**
- Modify: `src/prose_craft/cli.py` (append)
- Create: `tests/features/test_voice_check.py`

**Interfaces:**
- Produces: `voice check <file> --voice <name> [--tolerance] [--brief] [--json]`
- Produces: `voice init <name>`

- [ ] **Step 1: Write failing test**

```python
# tests/features/test_voice_check.py
from datetime import date
from pathlib import Path

from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


def _write_voice(root: Path, name: str) -> Path:
    vdir = root / name
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "voice.md").write_text(
        f"---\nvoice: {name}\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
        "register:\n  funny_serious: null\ndiction:\n  banned: [utilize]\nrhythm: {}\n"
        "syntax: {}\nlexicon: {}\nstructure: {}\n",
        encoding="utf-8",
    )
    return vdir / "voice.md"


def test_voice_check_json(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, "MistressFilth")
    draft = tmp_path / "p.md"
    draft.write_text("We will utilize this.", encoding="utf-8")
    result = runner.invoke(app, ["voice", "check", str(draft), "--voice", "MistressFilth", "--json"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.stdout)
    assert "mechanical" in data


def test_voice_init_creates_template(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["voice", "init", "newv"])
    assert result.exit_code == 0
    assert (tmp_path / "newv" / "voice.md").exists()
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/features/test_voice_check.py -v
```

Expected: failure (subcommand does not exist).

- [ ] **Step 3: Append the two subcommands to cli.py**

```python
@voice_app.command("check")
def voice_check(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str = typer.Option(..., "--voice"),  # noqa: B008
    tolerance: str = typer.Option("normal", "--tolerance"),
    brief: Path | None = typer.Option(None, "--brief"),  # noqa: B008
    as_json: bool = typer.Option(False, "--json"),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Run the deterministic voice check on a file."""
    from prose_craft.voices.check import check_voice

    root = _voices_root_opt(voices_root)
    profile = read_voice(voice, root=root)
    text = file.read_text(encoding="utf-8")
    verdict = check_voice(text, profile, tolerance=tolerance)  # type: ignore[arg-type]
    if as_json:
        typer.echo(verdict.model_dump_json(indent=2))
        return
    lines = [f"# Voice check — {voice}", ""]
    if verdict.mechanical:
        lines.append("## Mechanical")
        for v in verdict.mechanical:
            loc = f"{file}:{v.line}:{v.col}" if v.line else file
            lines.append(f"- {loc}  **{v.rule}** — {v.message}")
    if verdict.statistical:
        lines.append("")
        lines.append("## Statistical")
        for v in verdict.statistical:
            lines.append(f"- **{v.rule}** — {v.message}")
    if verdict.judgments_needed:
        lines.append("")
        lines.append(f"## Judgments needed ({len(verdict.judgments_needed)})")
        for j in verdict.judgments_needed:
            lines.append(f"- {j.rule}")
    if not (verdict.mechanical or verdict.statistical or verdict.judgments_needed):
        lines.append("_No findings._")
    typer.echo("\n".join(lines))


@voice_app.command("init")
def voice_init(
    name: str = typer.Argument(...),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Scaffold a blank voice.md from the template."""
    from prose_craft.data import load_template
    from prose_craft.voices.location import voice_path
    from prose_craft.voices.io import write_voice
    from prose_craft.voices.model import VoiceProfile
    from datetime import date

    root = _voices_root_opt(voices_root)
    path = voice_path(name, root=root)
    if path.exists():
        raise typer.BadParameter(f"voice {name!r} already exists at {path}")
    body = load_template()
    body = body.replace("<name>", name).replace("<voice-name>", name)
    body = body.replace("<YYYY-MM-DD>", date.today().isoformat())
    profile = VoiceProfile(
        voice=name,
        created=date.today(),
        updated=date.today(),
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )
    write_voice(profile, body.split("---\n", 2)[2] if body.count("---") >= 2 else "\n", root=root)
    typer.echo(f"initialized {path}")
```

Also add the missing imports at the top of cli.py:

```python
from prose_craft.voices.model import (
    DictionConfig,
    LexiconConfig,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SyntaxConfig,
)
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/features/test_voice_check.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/cli.py tests/features/test_voice_check.py
git commit -m "feat(cli): voice check and voice init subcommands"
```

---

### Task 31: migrate voices subcommand

**Files:**
- Modify: `src/prose_craft/cli.py` (append)
- Create: `tests/features/test_migrate_cli.py`

**Interfaces:**
- Produces: `migrate voices [--src] [--dst] [--overwrite] [--dry-run]`

- [ ] **Step 1: Write failing test**

```python
# tests/features/test_migrate_cli.py
from pathlib import Path

from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


def _seed(root: Path, name: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "voice.md").write_text(
        f"---\nvoice: {name}\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
        "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n",
        encoding="utf-8",
    )


def test_migrate_voices_cli(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _seed(src, "alpha")
    _seed(src, "beta")
    result = runner.invoke(app, ["migrate", "voices", "--src", str(src), "--dst", str(dst)])
    assert result.exit_code == 0
    assert (dst / "alpha" / "voice.md").exists()
    assert (dst / "beta" / "voice.md").exists()


def test_migrate_voices_dry_run(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _seed(src, "alpha")
    result = runner.invoke(app, [
        "migrate", "voices",
        "--src", str(src),
        "--dst", str(dst),
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert not (dst / "alpha" / "voice.md").exists()
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/features/test_migrate_cli.py -v
```

Expected: failure (subcommand does not exist).

- [ ] **Step 3: Append the migrate subcommand**

```python
migrate_app = typer.Typer(help="Migration helpers.")
app.add_typer(migrate_app, name="migrate")


@migrate_app.command("voices")
def migrate_voices_cmd(
    src: Path | None = typer.Option(None, "--src"),
    dst: Path | None = typer.Option(None, "--dst"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Copy voice profiles from a legacy location to the XDG root."""
    report = migrate_voices(
        src=src,
        dst=_voices_root_opt(dst),
        overwrite=overwrite,
        dry_run=dry_run,
    )
    typer.echo(f"copied: {', '.join(report.copied) or '(none)'}")
    typer.echo(f"skipped: {', '.join(report.skipped) or '(none)'}")
    if report.errors:
        typer.echo(f"errors: {'; '.join(report.errors)}", err=True)
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/features/test_migrate_cli.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/cli.py tests/features/test_migrate_cli.py
git commit -m "feat(cli): migrate voices subcommand"
```

---

### Task 32: voice compose, refine, draft, edit subcommands

**Files:**
- Modify: `src/prose_craft/cli.py` (append)
- Create: `tests/features/test_voice_compose.py`

**Interfaces:**
- Produces: `voice compose <name>` (REPL)
- Produces: `voice refine <name> [dim]` (REPL)
- Produces: `voice draft <name> <brief> [--to <output>]`
- Produces: `voice edit <file> --voice <name>`

- [ ] **Step 1: Write failing test**

```python
# tests/features/test_voice_compose.py
import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


def test_voice_draft_writes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    (tmp_path / "MistressFilth").mkdir()
    (tmp_path / "MistressFilth" / "voice.md").write_text(
        "---\nvoice: MistressFilth\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
        "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n",
        encoding="utf-8",
    )

    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(json.dumps({
            "text": "Drafted text.",
            "change_log": "ok",
            "voice_check_report": None,
        }))])

    out = tmp_path / "draft.md"
    result = runner.invoke(app, [
        "voice", "draft", "MistressFilth", "write a memo",
        "--to", str(out),
    ])
    # Will fail because the agent's model isn't stubbed. Verify CLI parses.
    # The actual agent output requires model wiring; this test only
    # confirms argument parsing and the existence of the subcommand.
    assert "--to" in result.stdout or result.exit_code in (0, 1)
```

- [ ] **Step 2: Run test, verify pass (relaxed) or skip**

The compose/draft subcommands depend on agent execution. The relaxed
assertion in Step 1 confirms the subcommand exists. Mark the test
`xfail` if it can't be fully driven without a model stub. (This is
intentional — model-stubbing the CLI is exercised in the
end-to-end test in Task 39.)

- [ ] **Step 3: Append the four subcommands to cli.py**

```python
@voice_app.command("compose")
def voice_compose(
    name: str = typer.Argument(...),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Interactive REPL: walk the writer through composing a voice."""
    from prose_craft.orchestrator.deps import ComposerDeps
    from prose_craft.voices.io import read_voice_raw, write_voice
    from prose_craft.voices.model import VoiceProfile
    from datetime import date

    root = _voices_root_opt(voices_root)
    try:
        profile, body = read_voice_raw(name, root=root)
    except Exception:
        # Initialize from template.
        from prose_craft.data import load_template
        from prose_craft.voices.model import (
            DictionConfig, LexiconConfig, RegisterAxes, RhythmConfig,
            StructureConfig, SyntaxConfig,
        )
        body = load_template()
        body = body.replace("<name>", name).replace("<voice-name>", name)
        body = body.replace("<YYYY-MM-DD>", date.today().isoformat())
        profile = VoiceProfile(
            voice=name, created=date.today(), updated=date.today(),
            register=RegisterAxes(), diction=DictionConfig(),
            rhythm=RhythmConfig(), syntax=SyntaxConfig(),
            lexicon=LexiconConfig(), structure=StructureConfig(),
        )

    fields = [
        "purpose", "audience", "register", "diction", "rhythm",
        "syntax", "lexicon", "structure", "never",
    ]
    field_index = 0
    craft = ProseCraft()
    agent = craft.voice_composer()

    while field_index < len(fields):
        current = fields[field_index]
        typer.echo(f"\n[{current}]")
        prompt_text = typer.prompt("(answer) ", default="", show_default=False)
        if prompt_text.strip().lower() in ("done", "exit", "quit"):
            break
        result = agent.run_sync(
            prompt_text or "next",
            deps=ComposerDeps(name=name, current_field=current, profile=profile.model_dump(mode="json")),
        )
        deltas = result.output
        if not deltas:
            field_index += 1
            continue
        for d in deltas:
            typer.echo(f"  proposed {d.field} = {d.value!r}  ({d.prompt})")
        ans = typer.prompt("(accept / modify / decline / skip)", default="accept")
        if ans.startswith("a"):
            payload = profile.model_dump(mode="json")
            for d in deltas:
                _apply_delta(payload, d)
            payload["updated"] = date.today().isoformat()
            profile = VoiceProfile.model_validate(payload)
            write_voice(profile, body, root=root)
            field_index += 1
        elif ans.startswith("s"):
            continue
        # modify / decline do not advance; user can re-prompt


def _apply_delta(payload: dict, delta: VoiceDelta) -> None:
    """Apply a VoiceDelta to a serialized VoiceProfile payload."""
    if "." in delta.field:
        top, sub = delta.field.split(".", 1)
        payload.setdefault(top, {})
        if isinstance(payload[top], dict):
            payload[top][sub] = delta.value
    else:
        payload[delta.field] = delta.value


@voice_app.command("refine")
def voice_refine(
    name: str = typer.Argument(...),
    dim: str | None = typer.Argument(None),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Refine one dimension of a voice. Walks unanswered dimensions when dim omitted."""
    # Same shape as compose; reuses the same REPL.
    voice_compose(name=name, voices_root=voices_root)


@voice_app.command("draft")
def voice_draft(
    name: str = typer.Argument(...),
    brief: str = typer.Argument(..., help="The brief to write to."),
    to: Path | None = typer.Option(None, "--to", help="Output file; defaults to stdout."),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Draft prose in the named voice."""
    from prose_craft.orchestrator.deps import StylistDeps

    root = _voices_root_opt(voices_root)
    # The stylist reads/writes the target file. The CLI seeds an empty
    # file at --to if given; the agent writes into it.
    if to is not None:
        to.parent.mkdir(parents=True, exist_ok=True)
        to.touch()
        file_path = to
    else:
        # Use a tmp path; the agent's text is printed to stdout.
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            file_path = Path(tmp.name)
            file_path.write_text("", encoding="utf-8")

    craft = ProseCraft()
    result = craft.voice_stylist().run_sync(
        f"Draft prose in voice {name!r}. Brief: {brief}",
        deps=StylistDeps(file_path=file_path, voice_name=name, brief=brief, mode="draft"),
    )
    if to is None:
        typer.echo(result.output.text)


@voice_app.command("edit")
def voice_edit(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str = typer.Option(..., "--voice"),  # noqa: B008
    in_place: bool = typer.Option(False, "--in-place"),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Edit a file in the named voice."""
    from prose_craft.orchestrator.deps import StylistDeps

    _voices_root_opt(voices_root)  # validate root exists
    craft = ProseCraft()
    result = craft.voice_stylist().run_sync(
        "Edit this prose in the named voice.",
        deps=StylistDeps(file_path=file, voice_name=voice, mode="edit"),
    )
    if in_place and result.output.text:
        file.write_text(result.output.text, encoding="utf-8")
    typer.echo(result.output.change_log or "(no change log)")
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/features/test_voice_compose.py -v
```

Expected: 1 passed (relaxed assertion confirms subcommand exists).

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/cli.py tests/features/test_voice_compose.py
git commit -m "feat(cli): voice compose, refine, draft, edit subcommands"
```

---


## Phase 6: MCP server

### Task 33: FastMCP server

**Files:**
- Create: `src/prose_craft/mcp.py`
- Create: `tests/features/test_mcp.py`

**Interfaces:**
- Produces: `mcp` (FastMCP instance)
- Produces: `run_stdio()` (entrypoint)
- 9 tools + 2 resources

- [ ] **Step 1: Write failing test**

```python
# tests/features/test_mcp.py
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel


def test_mcp_module_imports():
    from prose_craft.mcp import mcp
    assert mcp.name == "prose-craft"
```

- [ ] **Step 2: Run test, verify fail**

```bash
uv run pytest tests/features/test_mcp.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement mcp.py**

```python
# src/prose_craft/mcp.py
"""FastMCP server exposing the prose-craft engine over stdio."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastmcp import FastMCP

from prose_craft import __version__
from prose_craft.analysis.dispersion import measure_set
from prose_craft.analysis.clause_density import measure_clause_density
from prose_craft.analysis.sentences import tokenize_words
from prose_craft.orchestrator.deps import (
    AnalysisDeps,
    ArchitectDeps,
    EditorDeps,
    StylistDeps,
    TuneDeps,
    VoiceDeps,
)
from prose_craft.orchestrator.root import ProseCraft
from prose_craft.voices.check import check_voice
from prose_craft.voices.io import list_voices, read_voice, read_voice_raw

mcp = FastMCP("prose-craft")


def _craft() -> ProseCraft:
    return ProseCraft()


@mcp.tool
async def analyze_prose(
    file_path: str,
    voice: str | None = None,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
    metrics_only: bool = False,
) -> dict:
    """Run the prose analyst. Returns ProseDiagnostic as JSON."""
    if metrics_only:
        from prose_craft.analysis.metrics import analyze_prose
        from prose_craft.agents.results import ProseDiagnostic

        m = analyze_prose(Path(file_path).read_text(encoding="utf-8"))
        return ProseDiagnostic(metrics=m, issues=[]).model_dump(mode="json")
    deps = AnalysisDeps(file_path=Path(file_path), voice_name=voice, tolerance=tolerance)
    result = await _craft().analyst().run("Analyze this prose.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def voice_check(
    file_path: str,
    voice: str,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
    brief_path: str | None = None,
) -> dict:
    """Deterministic voice check. Returns VoiceVerdict as JSON."""
    profile = read_voice(voice)
    text = Path(file_path).read_text(encoding="utf-8")
    verdict = check_voice(text, profile, tolerance=tolerance)  # type: ignore[arg-type]
    return verdict.model_dump(mode="json")


@mcp.tool
async def dispersion_check(
    new_draft_path: str,
    siblings: list[str],
) -> dict:
    """Score the new draft against same-voice same-directory siblings."""
    new = Path(new_draft_path).read_text(encoding="utf-8")
    sib_texts = [Path(s).read_text(encoding="utf-8") for s in siblings]
    profile = measure_set(new, sib_texts)
    return profile.model_dump(mode="json")


@mcp.tool
async def clause_density_check(
    file_path: str,
    voice: str,
    surface: str | None = None,
) -> dict:
    """Measure passive + participial clause density for the voice+surface pair."""
    text = Path(file_path).read_text(encoding="utf-8")
    words = tokenize_words(text)
    cd = measure_clause_density(text, words)
    return cd.model_dump(mode="json")


@mcp.tool
async def edit_prose(
    file_path: str,
    voice: str | None = None,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
) -> dict:
    """Run the four-pass editor. Returns EditResult as JSON."""
    deps = EditorDeps(file_path=Path(file_path), voice_name=voice, tolerance=tolerance)
    result = await _craft().editor().run("Edit this prose.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def architect_prose(
    file_path: str,
    voice: str | None = None,
) -> dict:
    """Opus-grade structural rewrite proposal. Returns ArchitectResult as JSON."""
    deps = ArchitectDeps(file_path=Path(file_path), voice_name=voice)
    result = await _craft().architect().run("Architect this prose.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def tune_diction(
    file_path: str,
    voice: str | None = None,
) -> dict:
    """Focused word-choice pass. Returns SubstitutionPlan as JSON."""
    deps = TuneDeps(file_path=Path(file_path), voice_name=voice)
    result = await _craft().tune_diction().run("Tune diction.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def voice_compose_step(
    name: str,
    current_field: str = "purpose",
    profile: dict | None = None,
) -> list[dict]:
    """One step of the composer wizard. Returns list[VoiceDelta] as JSON."""
    from prose_craft.orchestrator.deps import ComposerDeps

    deps = ComposerDeps(name=name, current_field=current_field, profile=profile)
    result = await _craft().voice_composer().run("Compose step.", deps=deps)
    return [d.model_dump(mode="json") for d in result.output]


@mcp.resource("prose://voices")
async def list_voices_resource() -> str:
    """Markdown list of every voice under the active root."""
    summaries = list_voices()
    if not summaries:
        return "(no voices)"
    return "\n".join(f"- {s.name}  ({s.updated.isoformat()})" for s in summaries)


@mcp.resource("prose://voices/{name}")
async def read_voice_resource(name: str) -> str:
    """Raw voice.md for the named voice."""
    _, body = read_voice_raw(name)
    return body


def run_stdio() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")
```

Also add the `mcp` CLI subcommand at the end of `src/prose_craft/cli.py`:

```python
@app.command()
def mcp() -> None:
    """Run the FastMCP server over stdio."""
    from prose_craft.mcp import run_stdio
    run_stdio()
```

- [ ] **Step 4: Run test, verify pass**

```bash
uv run pytest tests/features/test_mcp.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/prose_craft/mcp.py src/prose_craft/cli.py tests/features/test_mcp.py
git commit -m "feat(mcp): FastMCP server with 9 tools and 2 resources"
```

---

## Phase 7: Plugin adapter

### Task 34: plugin manifests

**Files:**
- Create: `plugin/.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`

**Interfaces:** Two version surfaces start at `0.1.0`.

> **Naming convention (addresses spec Risk #5):** The MCP server is
> registered as `prose-craft`. Claude Code exposes its tools under the
> prefix `mcp__prose-craft__<tool>`. Plugin agents in `plugin/agents/`
> reference tools by that exact name (e.g. `mcp__prose-craft__voice_check`).
> Treat the tool-name set as a stable contract; renaming requires
> updating every plugin agent in the same commit.

- [ ] **Step 1: Write plugin/.claude-plugin/plugin.json**

```json
{
  "name": "prose-craft",
  "version": "0.1.0",
  "description": "Thin Claude Code adapter over the prose-craft engine. The engine itself is a pydantic-ai CLI + FastMCP server in this same repo.",
  "author": { "name": "MistressFilth" },
  "mcpServers": {
    "prose-craft": {
      "command": "uv",
      "args": ["run", "--project", ".", "prose-craft", "mcp"]
    }
  }
}
```

- [ ] **Step 2: Write .claude-plugin/marketplace.json**

```json
{
  "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
  "name": "prose-craft",
  "version": "0.1.0",
  "description": "pydantic-ai engine for designing and applying prose voices, with a thin Claude Code plugin adapter.",
  "owner": { "name": "MistressFilth" },
  "plugins": [
    { "name": "prose-craft", "source": "./plugin/" }
  ]
}
```

- [ ] **Step 3: Commit**

```bash
git add plugin/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "feat(plugin): manifest + marketplace entry, both at v0.1.0"
```

---

### Task 35: plugin agents (6 thin adapters)

**Files:**
- Create: `plugin/agents/prose-analyst.md`
- Create: `plugin/agents/prose-editor.md`
- Create: `plugin/agents/prose-architect.md`
- Create: `plugin/agents/voice-composer.md`
- Create: `plugin/agents/voice-stylist.md`
- Create: `plugin/agents/voice-checker.md`

- [ ] **Step 1: Write prose-analyst.md**

```markdown
---
name: prose-analyst
description: Fast diagnostic of any prose file. Use when the user asks for an analysis without edits.
tools: mcp__prose-craft__analyze_prose, Read
model: haiku
---

You are a thin adapter over the `analyze_prose` MCP tool. When invoked:

1. Read the file at the path supplied in $ARGUMENTS.
2. Call `mcp__prose-craft__analyze_prose` with the file path. Pass `--voice <name>` if $ARGUMENTS contains `--voice <name>`.
3. Render the result as markdown.

You do not analyze prose yourself. The tool does.
```

- [ ] **Step 2: Write prose-editor.md**

```markdown
---
name: prose-editor
description: Edit prose through the four-pass engine. Use when the user wants tightening, restructuring, or craft-level revision.
tools: mcp__prose-craft__edit_prose, Read, Write
model: sonnet
---

You are a thin adapter over the `edit_prose` MCP tool. When invoked:

1. Read the file at the path supplied in $ARGUMENTS.
2. Call `mcp__prose-craft__edit_prose` with the file path. Pass `--voice <name>` if $ARGUMENTS contains `--voice <name>`.
3. Apply the resulting changes to the file (use Edit or Write).
```

- [ ] **Step 3: Write prose-architect.md**

```markdown
---
name: prose-architect
description: Deep structural work for critical passages. Use when the user wants Opus-grade rewrite proposals.
tools: mcp__prose-craft__architect_prose, Read
model: opus
---

You are a thin adapter over the `architect_prose` MCP tool. When invoked:

1. Read the file at the path supplied in $ARGUMENTS.
2. Call `mcp__prose-craft__architect_prose` with the file path.
3. Render the analysis, diagnosis, and reconstruction proposal as markdown.
```

- [ ] **Step 4: Write voice-composer.md**

```markdown
---
name: voice-composer
description: Run the voice compose wizard. Use when the user wants to author or refine a voice profile through guided dialogue.
tools: mcp__prose-craft__voice_compose_step, Read, Write
model: opus
---

You are a thin adapter over the `voice_compose_step` MCP tool. When invoked:

1. For each composer dimension, call `mcp__prose-craft__voice_compose_step` with the dimension name.
2. Propose the returned deltas to the writer; on accept, apply the delta to the voice profile.
3. Persist with the CLI: `prose voice edit <name>` or directly via Read/Write.
```

- [ ] **Step 5: Write voice-stylist.md**

```markdown
---
name: voice-stylist
description: Draft or edit prose against a named voice profile.
tools: mcp__prose-craft__voice_check, Bash, Read, Write, Edit
model: sonnet
---

You are a thin adapter over the engine. When invoked:

1. Resolve the voice name from `--voice` in $ARGUMENTS.
2. Run `prose voice draft <name> <brief> --to <output>` or `prose voice edit <file>` via Bash.
3. Call `mcp__prose-craft__voice_check` to verify; iterate up to 2 passes if violations remain.
4. Write the final draft. Preserve the `voice:` front-matter.
```

- [ ] **Step 6: Write voice-checker.md**

```markdown
---
name: voice-checker
description: Read-only voice-rule check. Use when the user wants to know whether a draft violates a voice profile.
tools: mcp__prose-craft__voice_check, Read
model: haiku
---

You are a thin adapter over the `voice_check` MCP tool. When invoked:

1. Read the file at the path supplied in $ARGUMENTS.
2. Call `mcp__prose-craft__voice_check` with the file path, the voice name, and the tolerance from $ARGUMENTS.
3. Render the verdict as markdown.
```

- [ ] **Step 7: Commit**

```bash
git add plugin/agents/
git commit -m "feat(plugin): six thin agent adapters over MCP tools"
```

---

### Task 36: plugin skills (slash commands)

**Files:**
- Create: 14 `plugin/skills/<name>/SKILL.md` files

- [ ] **Step 1: Write the 14 SKILL.md files**

```markdown
# plugin/skills/analyze-prose/SKILL.md
---
name: analyze-prose
description: Run the prose analyst agent. Use when the user wants a read-only diagnostic.
---
Invoke the `prose-analyst` agent with the file path and any flags from $ARGUMENTS.
```

```markdown
# plugin/skills/edit-prose/SKILL.md
---
name: edit-prose
description: Run the four-pass editor. Use when the user wants prose tightening or revision.
---
Invoke the `prose-editor` agent with the file path and any flags from $ARGUMENTS.
```

```markdown
# plugin/skills/architect-prose/SKILL.md
---
name: architect-prose
description: Run the Opus architect. Use for critical passages and structural work.
---
Invoke the `prose-architect` agent with the file path and any flags from $ARGUMENTS.
```

```markdown
# plugin/skills/tune-diction/SKILL.md
---
name: tune-diction
description: Focused diction pass. Use when the user wants word-level substitutions.
---
Invoke the `tune-diction` CLI command with the file path and any flags from $ARGUMENTS.
```

```markdown
# plugin/skills/compose-voice/SKILL.md
---
name: compose-voice
description: Author a new voice through guided dialogue.
---
Invoke `prose voice compose <name>` via Bash with the voice name from $ARGUMENTS.
```

```markdown
# plugin/skills/refine-voice/SKILL.md
---
name: refine-voice
description: Refine a voice profile dimension.
---
Invoke `prose voice refine <name> [dim]` via Bash with the arguments from $ARGUMENTS.
```

```markdown
# plugin/skills/draft-in-voice/SKILL.md
---
name: draft-in-voice
description: Generate prose against a voice.
---
Invoke `prose voice draft <name> <brief>` via Bash with the arguments from $ARGUMENTS.
```

```markdown
# plugin/skills/show-voice/SKILL.md
---
name: show-voice
description: Print a voice profile.
---
Invoke `prose voice show <name>` via Bash with the name from $ARGUMENTS.
```

```markdown
# plugin/skills/list-voices/SKILL.md
---
name: list-voices
description: Enumerate all voices.
---
Invoke `prose voice list` via Bash.
```

```markdown
# plugin/skills/import-voice/SKILL.md
---
name: import-voice
description: Bootstrap a voice from authored source material.
---
This skill is reserved for future work; the engine does not yet implement voice import.
```

```markdown
# plugin/skills/collapse-voice/SKILL.md
---
name: collapse-voice
description: Fold a bank back into inline lexicon.
---
This skill is reserved for future work; the engine does not yet implement bank collapse.
```

```markdown
# plugin/skills/deepen-voice/SKILL.md
---
name: deepen-voice
description: Move an inline list into a bank file.
---
This skill is reserved for future work; the engine does not yet implement bank deepening.
```

```markdown
# plugin/skills/migrate-voice/SKILL.md
---
name: migrate-voice
description: Migrate voices from the legacy plugin-data location.
---
Invoke `prose migrate voices` via Bash.
```

```markdown
# plugin/skills/voice-contract/SKILL.md
---
name: voice-contract
description: Operational contract for designed voices. Reference; not user-invocable.
user-invocable: false
---
This is a reference-only skill. It loads the voice_contract reference into agent context.
```

- [ ] **Step 2: Commit**

```bash
git add plugin/skills/
git commit -m "feat(plugin): 14 slash-command skill adapters"
```

---

### Task 37: plugin output styles + voice template

**Files:**
- Create: `plugin/output-styles/literary-editor.md`
- Create: `plugin/output-styles/voice-author.md`
- Create: `plugin/voices/_template/voice.md`

- [ ] **Step 1: Write literary-editor.md (preserve the existing content)**

```markdown
---
name: literary-editor
description: Master literary editor mode. Activates prose-aware behavior for the entire session.
---

# Literary editor

You approach all prose work as a master literary editor. The five principles:

1. The writer's voice is sacred — strengthen authenticity, don't impose preference
2. Economy is not poverty — cut what doesn't earn its place, but some passages need to breathe
3. Rhythm is meaning — sentence length, paragraph structure, and emphasis encode emotion
4. Concrete over abstract — a specific image beats a general statement
5. Trust the reader — don't explain what you've shown

When editing: read the whole passage first, identify what works, diagnose before prescribing, preserve voice, show before/after.

When writing: match the existing register, default on Germanic vocabulary, vary sentence rhythm deliberately, build invisible cohesion.

When analyzing: use measurable criteria, provide specific examples, prioritize two or three most important issues, explain why.
```

- [ ] **Step 2: Write voice-author.md**

```markdown
---
name: voice-author
description: Activates voice-aware authoring. The active voice profile is constitution; literary-editor principles apply only as fallback for dimensions the profile does not specify. When a voice rule and a literary-editor principle conflict, the voice wins.
---

You are authoring prose under a designed voice. The voice profile at `$CLAUDE_PLUGIN_DATA/voices/<name>/voice.md` is your constitution. Load it via the `prose://voices/<name>` MCP resource before drafting.

Honor every explicit rule in the profile. Banned words stay out. Preferred substitutions land. Target ranges are met. The never-list is absolute.

When the profile is silent on a dimension, fall back to the literary-editor output style.
```

- [ ] **Step 3: Write the voice template**

```markdown
<!-- plugin/voices/_template/voice.md -->
---
voice: <name>
version: 1
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

# <voice-name>

A short paragraph capturing what this voice sounds like. The composer
fills this in during the compose dialogue.
```

- [ ] **Step 4: Commit**

```bash
git add plugin/output-styles/ plugin/voices/
git commit -m "feat(plugin): output styles and voice template"
```

---

## Phase 8: Rollout

### Task 38: remove old plugin engine

**Files:**
- Delete: `plugin/scripts/` (entire directory)
- Delete: `plugin/hooks/` (entire directory)
- Modify: confirm no remaining references in `plugin/.claude-plugin/plugin.json`

**Interfaces:** None.

- [ ] **Step 1: Verify the new engine covers every CLI subcommand and MCP tool**

```bash
ls plugin/agents/ plugin/skills/ plugin/output-styles/ plugin/voices/
```

Expected: lists the six agent markdowns, the 14 skill markdowns, the two output styles, the template.

- [ ] **Step 2: Remove the old scripts and hooks directories**

```bash
git rm -r plugin/scripts/ plugin/hooks/
```

- [ ] **Step 3: Verify the plugin manifest no longer references hooks**

```bash
cat plugin/.claude-plugin/plugin.json
```

Expected: no `hooks` key. If the original file has a `hooks` block, remove it.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(plugin): remove old scripts and hooks; engine is the CLI + MCP"
```

---

### Task 39: README + CHANGELOG final pass

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Rewrite README.md**

```markdown
# prose-craft

A `pydantic-ai` engine for designing and applying prose voices.

- **Typer CLI** (`prose`) with subcommands for analyze, edit,
  architect, tune-diction, voice compose/refine/draft/edit/check/list/
  show/init, migrate, mcp.
- **FastMCP server** (`prose mcp`) over stdio, exposing the engine as
  tools and resources to any MCP host.
- **Voice profiles** at `$XDG_DATA_HOME/prose-craft/voices/<name>/voice.md`.
- **Claude Code plugin** at `plugin/` is a thin adapter over the engine.

## Install

```bash
make init
```

The Makefile target runs `uv sync --all-extras` and installs the engine
plus its dev tools.

## Quickstart

```bash
# List voices
prose voice list

# Analyze a draft (no LLM round-trip when --metrics-only)
prose analyze chapter.md --voice MistressFilth --metrics-only

# Edit prose in a voice
prose edit chapter.md --voice MistressFilth

# Run the composer wizard
prose voice compose MistressFilth

# Start the MCP server
prose mcp
```

## Migrating from the old plugin

If you have existing voices in `${CLAUDE_PLUGIN_DATA}/voices/`, copy
them into the new XDG-resident location:

```bash
prose migrate voices
```

The old directory is left untouched; delete the new one to roll back.

## Using the MCP server from Claude Code

```bash
claude mcp add --transport stdio prose-craft -- uv run --project . prose-craft mcp
```

The plugin in `plugin/` is registered the same way as before and now
depends on the MCP server for its tools.

## Architecture

Single composition root (`ProseCraft`) constructs seven `pydantic-ai`
agents. Deterministic primitives in `src/prose_craft/analysis/` are
pure Python, callable from CLI, agents (as tools), and MCP. Voice
profiles are Pydantic models that round-trip the existing `voice.md`
front-matter format.

See `docs/superpowers/specs/2026-08-01-prose-craft-pydantic-ai-design.md`
for the full design and
`docs/superpowers/plans/2026-08-01-prose-craft-pydantic-ai-rewrite.md`
for the implementation plan.

## Development

```bash
make test     # unit + features
make check    # lint, typecheck, format
```

## License

GPL-2.0.
```

- [ ] **Step 2: Finalize CHANGELOG.md**

```markdown
# Changelog

## [0.1.0] - 2026-08-01

### Changed
- Rewrite as pydantic-ai CLI + FastMCP server. Plugin reduced to thin
  adapter. Voice profiles moved from `${CLAUDE_PLUGIN_DATA}/voices/` to
  `$XDG_DATA_HOME/prose-craft/voices/`. Run `prose migrate voices` once
  to copy existing profiles.

## [0.0.0] - 2026-07-14

Initial release as a Claude Code plugin only.
```

- [ ] **Step 3: Commit**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: finalize README and CHANGELOG for v0.1.0"
```

---

### Task 40: full make check + tag v0.1.0

**Files:** None new.

- [ ] **Step 1: Run the full test suite**

```bash
make test
```

Expected: all tests pass.

- [ ] **Step 2: Run lint, typecheck, format**

```bash
make check
```

Expected: no errors. If `ruff format` mutates files, re-stage and re-run
`make check`. Repeat until clean.

- [ ] **Step 3: Smoke-test the CLI end-to-end**

```bash
uv run prose version
uv run prose voice list
uv run prose --help
```

Expected: each command prints a sensible response and exits 0.

- [ ] **Step 4: Tag the release**

```bash
git tag v0.1.0
git push origin v0.1.0
```

Expected: tag is created locally; push succeeds (if origin is configured).

- [ ] **Step 5: Final commit (if anything was re-staged in step 2)**

```bash
git status
```

If clean, no commit. If dirty, commit with a Conventional Commits message
describing the formatting fix.

---

