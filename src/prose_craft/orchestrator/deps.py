"""Pydantic dep models shared by every agent."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from prose_craft.voices.audience import ResolvedAudience

Tolerance = Literal["strict", "normal", "relaxed"]
StylistMode = Literal["draft", "edit"]


class AnalysisDeps(BaseModel):
    file_path: Path
    voice_name: str | None = None
    tolerance: Tolerance = "normal"
    audience: ResolvedAudience | None = None


class EditorDeps(BaseModel):
    file_path: Path
    voice_name: str | None = None
    tolerance: Tolerance = "normal"
    audience: ResolvedAudience | None = None


class ArchitectDeps(BaseModel):
    file_path: Path
    voice_name: str | None = None
    audience: ResolvedAudience | None = None


class TuneDeps(BaseModel):
    file_path: Path
    voice_name: str | None = None
    audience: ResolvedAudience | None = None


class VoiceDeps(BaseModel):
    file_path: Path
    voice_name: str
    tolerance: Tolerance = "normal"
    brief_path: Path | None = None
    audience: ResolvedAudience | None = None


class StylistDeps(BaseModel):
    file_path: Path
    voice_name: str
    brief: str | None = None
    mode: StylistMode = "draft"
    audience: ResolvedAudience | None = None


class ComposerDeps(BaseModel):
    name: str
    current_field: str = "purpose"
    profile: dict[str, object] | None = None
    history: list[dict[str, object]] = []
    audience: ResolvedAudience | None = None
