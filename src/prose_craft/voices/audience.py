"""Audience / severity / dial / surface resolution for voice profiles.

Resolves per-call knobs (CLI flag, target-file front-matter, voice
defaults) into a single ``ResolvedAudience`` struct that downstream
deps + agent prompts consume.

The on-disk schema is described in the voice profile design spec; this
module is the runtime boundary that converts that schema into prompt
context.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from prose_craft.voices.model import NeverEntry, SurfaceFilter

Source = Literal["cli", "frontmatter", "voice_default"]


class AudienceNotFoundError(ValueError):
    """Raised when CLI or front-matter names an audience not in the voice."""

    def __init__(self, *, voice: str, audience: str, available: list[str]) -> None:
        self.voice = voice
        self.audience = audience
        self.available = available
        super().__init__(
            f"voice {voice!r} has no audience {audience!r}; "
            f"available: {', '.join(available) if available else '(none)'}"
        )


class ResolvedAudience(BaseModel):
    """Resolved per-call audience context. See spec."""

    name: str
    voice_name: str
    severity_ceiling: int = 5
    dial_ceiling: float = 1.0
    never: list[NeverEntry] = []
    surface_filter: SurfaceFilter | None = None
    surface_target: str | None = None
    closed: bool = False
    reason: str | None = None
    warnings: list[str] = []
    source: Source = "voice_default"


__all__ = ["AudienceNotFoundError", "ResolvedAudience", "Source"]
