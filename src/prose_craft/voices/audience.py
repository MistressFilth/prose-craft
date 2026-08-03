"""Audience / severity / dial / surface resolution for voice profiles.

Resolves per-call knobs (CLI flag, target-file front-matter, voice
defaults) into a single ``ResolvedAudience`` struct that downstream
deps + agent prompts consume.

The on-disk schema is described in the voice profile design spec; this
module is the runtime boundary that converts that schema into prompt
context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from prose_craft.voices.model import AudienceCeiling, AudiencesBlock, NeverEntry, SurfaceFilter

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


def _is_default_audiences(audiences: AudiencesBlock) -> bool:
    """True when the user has not configured any audience ceilings.

    The ``AudiencesBlock`` model ships defaults for ``private``,
    ``team``, and ``external``, so absence of a custom audience block
    on disk still surfaces as a populated ``AudiencesBlock`` in memory.
    We treat the block as "unset" when the only fields present are
    defaults: no custom audiences via ``extra="allow"`` and the three
    built-in audiences are at their factory defaults.
    """
    if audiences.model_extra:
        return False
    default_ceiling = AudienceCeiling()
    return (
        audiences.private == default_ceiling
        and audiences.team == default_ceiling
        and audiences.external == default_ceiling
    )


def _most_permissive(audiences: AudiencesBlock) -> str | None:
    """Return the audience name with the highest severity + dial ceiling."""
    if _is_default_audiences(audiences):
        return None
    entries = audiences.entries()
    # Severity tie broken by dial tie; both descending.
    return max(
        entries.keys(),
        key=lambda n: (entries[n].severity_ceiling, entries[n].dial_ceiling),
    )


def resolve_audience(
    voice_name: str,
    *,
    cli_audience: str | None = None,
    cli_severity: int | None = None,
    cli_dial: float | None = None,
    cli_surface: str | None = None,
    front_matter_path: Path | None = None,
    voices_root: Path | None = None,
) -> ResolvedAudience | None:
    """Resolve audience context for a voice + call. Returns None when no audience applies."""
    from prose_craft.voices.io import read_voice

    profile = read_voice(voice_name, root=voices_root)
    entries = profile.audiences.entries()

    fm_audience = None
    fm_severity = None
    fm_dial = None
    fm_surface = None
    warnings: list[str] = []
    if front_matter_path is not None and front_matter_path.is_file():
        try:
            import frontmatter

            post = frontmatter.loads(front_matter_path.read_text(encoding="utf-8"))
            md: dict[str, Any] = dict(post.metadata or {})
            if "audience" in md:
                fm_audience = str(md["audience"])
            if "severity_ceiling" in md:
                try:
                    fm_severity = int(md["severity_ceiling"])
                except (TypeError, ValueError) as e:
                    raise ValueError(
                        f"front-matter severity_ceiling in {front_matter_path} is not an int: {md['severity_ceiling']!r}"
                    ) from e
            if "dial_ceiling" in md:
                try:
                    fm_dial = float(md["dial_ceiling"])
                except (TypeError, ValueError) as e:
                    raise ValueError(
                        f"front-matter dial_ceiling in {front_matter_path} is not a float: {md['dial_ceiling']!r}"
                    ) from e
            if "surface" in md:
                fm_surface = str(md["surface"])
        except ValueError:
            raise
        except Exception as e:  # yaml / frontmatter parse failure
            warnings.append(f"front-matter parse failed for {front_matter_path}: {e}")

    # Precedence: CLI > front-matter > voice default.
    if cli_audience is not None:
        name, source = cli_audience, "cli"
    elif fm_audience is not None:
        name, source = fm_audience, "frontmatter"
    else:
        name = _most_permissive(profile.audiences)
        source = "voice_default"

    # If voice has no audiences and no flag, skip entirely.
    if name is None:
        return None

    # Validate audience is in the voice's audiences block.
    if name not in entries:
        raise AudienceNotFoundError(
            voice=voice_name,
            audience=name,
            available=sorted(entries.keys()),
        )

    ceiling = entries[name]

    # Flag overrides verbatim (caller responsibility).
    severity = (
        cli_severity
        if cli_severity is not None
        else (fm_severity if fm_severity is not None else ceiling.severity_ceiling)
    )
    dial = (
        cli_dial
        if cli_dial is not None
        else (fm_dial if fm_dial is not None else ceiling.dial_ceiling)
    )

    surface = cli_surface if cli_surface is not None else fm_surface

    # Never merge happens in Task 5; surface_filter.copy and closed/reason in Task 4.

    return ResolvedAudience(
        name=name,
        voice_name=voice_name,
        severity_ceiling=severity,
        dial_ceiling=dial,
        surface_filter=ceiling.surface_filter,
        surface_target=surface,
        closed=ceiling.closed,
        reason=ceiling.reason,
        warnings=warnings,
        source=source,
    )


__all__ = ["AudienceNotFoundError", "ResolvedAudience", "Source", "resolve_audience"]
