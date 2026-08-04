"""Pydantic models for voice profiles.

Mirrors the D1-D10 + audiences + attributions schema from the existing
plugin. ``extra="forbid"`` rejects unknown keys so writers discover
typos at parse time.
"""

from __future__ import annotations

import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# Re-export SubstitutionRule from analysis.diction so the voice
# schema can import it from a single place.
from prose_craft.analysis.diction import SubstitutionRule  # noqa: F401


def _coerce_to_never_entry(v: Any) -> Any:
    """Coerce a bare string into a ``NeverEntry(rule=v)`` instance.

    The voice schema lets authors write the never list as either a
    list of dicts (``{rule: ..., detection: ...}``) or a list of bare
    strings (just the rule text). Bare strings default to
    ``detection="agent-required"`` because the agent is the only
    thing that can judge whether the draft trips the rule.
    """
    if isinstance(v, str):
        return {"rule": v}
    return v


NeverEntryOrStr = Annotated["NeverEntry | str", BeforeValidator(_coerce_to_never_entry)]


def _coerce_to_attribution(v: Any) -> Any:
    """Coerce a bare string into an ``Attribution`` record.

    Authors may list attributions as bare strings (a citation note);
    parse them as an ``Attribution(field="?", source=str, license="?")``
    so downstream code can treat the list uniformly.
    """
    if isinstance(v, str):
        return {"field": "?", "source": v, "license": "?"}
    return v


AttributionOrStr = Annotated["Attribution | str", BeforeValidator(_coerce_to_attribution)]


class RegisterAxes(BaseModel):
    """D3 — six register axes. None = silent (composer has not asked)."""

    funny_serious: float | str | None = None
    formal_casual: float | str | None = None
    respectful_irreverent: float | str | None = None
    enthusiastic_matter_of_fact: float | str | None = None
    certainty: float | str | None = None
    density: float | str | None = None


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
    never_extend: list[NeverEntryOrStr] = []
    surface_filter: SurfaceFilter | None = None
    closed: bool = False
    reason: str | None = None


class AudiencesBlock(BaseModel):
    """Per-voice audiences block: a rationale + the standard audiences.

    ``rationale`` captures why this configuration exists. The three
    standard audience slots (``private``, ``team``, ``external``) are
    Optional so a freshly-initialized voice with no scaffolded block
    parses cleanly; the resolver distinguishes "not configured" from
    "configured to defaults" via ``model_fields_set``.

    Custom audiences (anything beyond the three named slots) are
    rejected by ``extra="forbid"`` — the spec fixes the audience
    vocabulary to keep downstream agent prompts deterministic.
    """

    model_config = ConfigDict(extra="forbid")

    rationale: str | None = None
    private: AudienceCeiling | None = None
    team: AudienceCeiling | None = None
    external: AudienceCeiling | None = None

    def entries(self) -> dict[str, AudienceCeiling]:
        """Return the configured audiences as ``name -> AudienceCeiling``.

        Only audiences explicitly set on the block are returned;
        ``None`` slots are skipped. The resolver uses this to
        enumerate valid audience names when validating CLI flags or
        front-matter keys.
        """
        out: dict[str, AudienceCeiling] = {}
        if self.private is not None:
            out["private"] = self.private
        if self.team is not None:
            out["team"] = self.team
        if self.external is not None:
            out["external"] = self.external
        return out


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
    author: str | None = None
    imported_from: str | None = None
    voice_persona: str | None = None
    purpose: str | None = None
    audience: str | None = None
    audiences: AudiencesBlock = Field(default_factory=AudiencesBlock)
    register: RegisterAxes
    diction: DictionConfig
    rhythm: RhythmConfig
    syntax: SyntaxConfig
    lexicon: LexiconConfig
    structure: StructureConfig
    never: list[NeverEntryOrStr] = []
    lore_corpus: dict[str, Any] = Field(default_factory=dict)
    fallbacks: dict[str, Any] = Field(default_factory=dict)
    depth: list[dict[str, Any]] = Field(default_factory=list)
    base: str | None = None
    audience_secondary: str | None = None
    attributions: list[AttributionOrStr] = []


AudienceCeiling.model_rebuild()
