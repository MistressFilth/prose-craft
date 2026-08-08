"""FastMCP server exposing the prose-craft engine over stdio."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

from prose_craft.analysis.clause_density import measure_clause_density
from prose_craft.analysis.dispersion import measure_set
from prose_craft.analysis.sentences import tokenize_words
from prose_craft.config import ProseCraftSettings, load_settings
from prose_craft.orchestrator.deps import (
    AnalysisDeps,
    ArchitectDeps,
    EditorDeps,
    TuneDeps,
)
from prose_craft.orchestrator.root import ProseCraft
from prose_craft.voices.audience import ResolvedAudience, resolve_audience
from prose_craft.voices.check import check_voice
from prose_craft.voices.index import VoiceIndex
from prose_craft.voices.io import VoiceProfileNotFound, read_voice

mcp = FastMCP("prose-craft")
_index_cache: VoiceIndex | None = None


def _get_index() -> VoiceIndex:
    global _index_cache
    if _index_cache is None:
        _index_cache = VoiceIndex.build()
    return _index_cache


def _invalidate_index() -> None:
    global _index_cache
    _index_cache = None
    # Co-invalidate the persistent on-disk cache so the next ``load_or_build``
    # (e.g. via ``voice list``) rebuilds. Any MCP handler that mutates a
    # voice should call this; the persistent side is cleared here so
    # callers don't have to remember to do both.
    from prose_craft.voices.io import invalidate_index_cache

    invalidate_index_cache()


def _craft(settings: ProseCraftSettings | None = None) -> ProseCraft:
    """Build :class:`ProseCraft` from the active settings.

    Each tool loads settings once at entry and threads the result into
    both audience/voice reads and :class:`ProseCraft` so the TOML
    config file is parsed exactly once per request. Pass ``settings``
    when the caller already holds them; passing ``None`` triggers a
    fresh load (the test seam uses this).
    """
    if settings is None:
        settings = load_settings()
    return ProseCraft(model=settings.model, voices_root=settings.voices_root)


@mcp.tool
async def analyze_prose(
    file_path: str,
    voice: str | None = None,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
    metrics_only: bool = False,
    audience: str | None = None,
    severity_ceiling: int | None = None,
    dial_ceiling: float | None = None,
    surface: str | None = None,
) -> dict[str, object]:
    """Run the prose analyst. Returns ProseDiagnostic as JSON."""
    # Metrics-only is a deterministic analyzer that reads only the file
    # argument. Loading settings is wasted work and any error there
    # must not poison the command (mirrors CLI's `analyze --metrics-only`).
    # The CLI ignores ``voice`` on this path; the MCP server must too, so
    # a caller that pairs ``metrics_only=True`` with a voice name still
    # gets a deterministic result without parsing the config file.
    if metrics_only:
        from prose_craft.analysis.metrics import analyze_prose
        from prose_craft.agents.results import ProseDiagnostic

        m = analyze_prose(Path(file_path).read_text(encoding="utf-8"))
        return ProseDiagnostic(metrics=m, issues=[]).model_dump(mode="json")
    settings = load_settings()
    resolved: ResolvedAudience | None = None
    if voice is not None:
        resolved = resolve_audience(
            voice,
            cli_audience=audience,
            cli_severity=severity_ceiling,
            cli_dial=dial_ceiling,
            cli_surface=surface,
            front_matter_path=Path(file_path),
            voices_root=settings.voices_root,
        )
    deps = AnalysisDeps(
        file_path=Path(file_path),
        voice_name=voice,
        tolerance=tolerance,
        audience=resolved,
    )
    result = await _craft(settings).analyst(audience=resolved).run("Analyze this prose.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def voice_check(
    file_path: str,
    voice: str,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
    brief_path: str | None = None,
    audience: str | None = None,
    severity_ceiling: int | None = None,
    dial_ceiling: float | None = None,
    surface: str | None = None,
) -> dict[str, object]:
    """Deterministic voice check. Returns VoiceVerdict as JSON."""
    settings = load_settings()
    resolved = resolve_audience(
        voice,
        cli_audience=audience,
        cli_severity=severity_ceiling,
        cli_dial=dial_ceiling,
        cli_surface=surface,
        front_matter_path=Path(file_path),
        voices_root=settings.voices_root,
    )
    profile = read_voice(voice, root=settings.voices_root)
    text = Path(file_path).read_text(encoding="utf-8")
    verdict = check_voice(
        text,
        profile,
        tolerance=tolerance,
        audience=resolved,
        surface=resolved.surface_target if resolved is not None else surface,
    )
    return verdict.model_dump(mode="json")


@mcp.tool
async def dispersion_check(
    new_draft_path: str,
    siblings: list[str],
) -> dict[str, object]:
    """Score the new draft against same-voice same-directory siblings."""
    new = Path(new_draft_path).read_text(encoding="utf-8")
    sib_texts = [Path(s).read_text(encoding="utf-8") for s in siblings]
    profile = measure_set(new, sib_texts)
    return profile.model_dump(mode="json")


@mcp.tool
async def clause_density_check(
    file_path: str,
) -> dict[str, object]:
    """Measure passive + participial clause density."""
    text = Path(file_path).read_text(encoding="utf-8")
    words = tokenize_words(text)
    cd = measure_clause_density(text, words)
    return cd.model_dump(mode="json")


@mcp.tool
async def edit_prose(
    file_path: str,
    voice: str | None = None,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
    audience: str | None = None,
    severity_ceiling: int | None = None,
    dial_ceiling: float | None = None,
    surface: str | None = None,
) -> dict[str, object]:
    """Run the four-pass editor. Returns EditResult as JSON."""
    settings = load_settings()
    resolved: ResolvedAudience | None = None
    if voice is not None:
        resolved = resolve_audience(
            voice,
            cli_audience=audience,
            cli_severity=severity_ceiling,
            cli_dial=dial_ceiling,
            cli_surface=surface,
            front_matter_path=Path(file_path),
            voices_root=settings.voices_root,
        )
    deps = EditorDeps(
        file_path=Path(file_path),
        voice_name=voice,
        tolerance=tolerance,
        audience=resolved,
    )
    result = await _craft(settings).editor(audience=resolved).run("Edit this prose.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def architect_prose(
    file_path: str,
    voice: str | None = None,
    audience: str | None = None,
    severity_ceiling: int | None = None,
    dial_ceiling: float | None = None,
    surface: str | None = None,
) -> dict[str, object]:
    """Opus-grade structural rewrite proposal. Returns ArchitectResult as JSON."""
    settings = load_settings()
    resolved: ResolvedAudience | None = None
    if voice is not None:
        resolved = resolve_audience(
            voice,
            cli_audience=audience,
            cli_severity=severity_ceiling,
            cli_dial=dial_ceiling,
            cli_surface=surface,
            front_matter_path=Path(file_path),
            voices_root=settings.voices_root,
        )
    deps = ArchitectDeps(
        file_path=Path(file_path),
        voice_name=voice,
        audience=resolved,
    )
    result = (
        await _craft(settings).architect(audience=resolved).run("Architect this prose.", deps=deps)
    )
    return result.output.model_dump(mode="json")


@mcp.tool
async def tune_diction(
    file_path: str,
    voice: str | None = None,
    audience: str | None = None,
    severity_ceiling: int | None = None,
    dial_ceiling: float | None = None,
    surface: str | None = None,
) -> dict[str, object]:
    """Focused word-choice pass. Returns SubstitutionPlan as JSON."""
    settings = load_settings()
    resolved: ResolvedAudience | None = None
    if voice is not None:
        resolved = resolve_audience(
            voice,
            cli_audience=audience,
            cli_severity=severity_ceiling,
            cli_dial=dial_ceiling,
            cli_surface=surface,
            front_matter_path=Path(file_path),
            voices_root=settings.voices_root,
        )
    deps = TuneDeps(
        file_path=Path(file_path),
        voice_name=voice,
        audience=resolved,
    )
    result = await _craft(settings).tune_diction(audience=resolved).run("Tune diction.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def voice_compose_step(
    name: str,
    current_field: str = "purpose",
    profile: dict[str, object] | None = None,
    audience: str | None = None,
    severity_ceiling: int | None = None,
    dial_ceiling: float | None = None,
    surface: str | None = None,
) -> list[dict[str, object]]:
    """One step of the composer wizard. Returns list[VoiceDelta] as JSON."""
    from prose_craft.orchestrator.deps import ComposerDeps

    settings = load_settings()
    try:
        resolved = resolve_audience(
            name,
            cli_audience=audience,
            cli_severity=severity_ceiling,
            cli_dial=dial_ceiling,
            cli_surface=surface,
            front_matter_path=None,
            voices_root=settings.voices_root,
        )
    except VoiceProfileNotFound:
        if any(value is not None for value in (audience, severity_ceiling, dial_ceiling, surface)):
            raise
        resolved = None
    deps = ComposerDeps(
        name=name,
        current_field=current_field,
        profile=profile,
        audience=resolved,
    )
    result = (
        await _craft(settings).voice_composer(audience=resolved).run("Compose step.", deps=deps)
    )
    return [d.model_dump(mode="json") for d in result.output]


@mcp.resource("prose://voices")
async def list_voices_resource() -> str:
    """Markdown list of every visible voice (user + shared)."""
    idx = _get_index()
    rows = []
    for name, entry in idx:
        updated = entry.path.stat().st_mtime
        rows.append((name, entry.origin, updated))
    if not rows:
        return "(no voices)"
    rows.sort(key=lambda row: row[0])
    lines = []
    for name, origin, mtime in rows:
        # Best-effort ISO date from mtime; voice files don't carry a stable
        # `updated` field across roots so we use file mtime as a proxy.
        iso = datetime.fromtimestamp(mtime, tz=timezone.utc).date().isoformat()
        lines.append(f"- {name} [{origin.value}]  ({iso})")
    return "\n".join(lines)


@mcp.resource("prose://voices/{name}")
async def read_voice_resource(name: str) -> str:
    """Raw voice.md for the named voice (user or shared)."""
    from prose_craft.voices.location import voice_path

    path = voice_path(name)
    return path.read_text(encoding="utf-8")


def run_stdio() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")
