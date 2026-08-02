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
