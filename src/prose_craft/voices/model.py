"""Pydantic models for voice profiles.

Mirrors the D1-D10 + audiences + attributions schema from the existing
plugin. ``extra="forbid"`` rejects unknown keys so writers discover
typos at parse time.
"""

from __future__ import annotations

import datetime
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
    """Provenance record for a YAML field or rule id.

    Uses ``datetime.date`` (fully qualified) on the ``date`` field so
    the field name does not shadow the type during PEP 563 annotation
    evaluation; the runtime type is identical to ``date``.
    """

    field: str
    source: str
    license: str
    citation: str | None = None
    date: datetime.date | None = None


class VoiceProfile(BaseModel):
    """D1-D10 + audiences + attributions."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    voice: str
    version: int = 1
    created: datetime.date
    updated: datetime.date
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
