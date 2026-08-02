"""FastMCP server exposing the prose-craft engine over stdio."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

from prose_craft.analysis.clause_density import measure_clause_density
from prose_craft.analysis.dispersion import measure_set
from prose_craft.analysis.sentences import tokenize_words
from prose_craft.orchestrator.deps import (
    AnalysisDeps,
    ArchitectDeps,
    EditorDeps,
    TuneDeps,
)
from prose_craft.orchestrator.root import ProseCraft
from prose_craft.voices.check import check_voice
from prose_craft.voices.io import list_voices, read_voice, read_voice_file

mcp = FastMCP("prose-craft")


def _craft() -> ProseCraft:
    return ProseCraft()


@mcp.tool
async def analyze_prose(
    file_path: str,
    voice: str | None = None,
    tolerance: Literal["strict", "normal", "relaxed"] = "normal",
    metrics_only: bool = False,
) -> dict[str, object]:
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
) -> dict[str, object]:
    """Deterministic voice check. Returns VoiceVerdict as JSON."""
    profile = read_voice(voice)
    text = Path(file_path).read_text(encoding="utf-8")
    verdict = check_voice(text, profile, tolerance=tolerance)
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
) -> dict[str, object]:
    """Run the four-pass editor. Returns EditResult as JSON."""
    deps = EditorDeps(file_path=Path(file_path), voice_name=voice, tolerance=tolerance)
    result = await _craft().editor().run("Edit this prose.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def architect_prose(
    file_path: str,
    voice: str | None = None,
) -> dict[str, object]:
    """Opus-grade structural rewrite proposal. Returns ArchitectResult as JSON."""
    deps = ArchitectDeps(file_path=Path(file_path), voice_name=voice)
    result = await _craft().architect().run("Architect this prose.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def tune_diction(
    file_path: str,
    voice: str | None = None,
) -> dict[str, object]:
    """Focused word-choice pass. Returns SubstitutionPlan as JSON."""
    deps = TuneDeps(file_path=Path(file_path), voice_name=voice)
    result = await _craft().tune_diction().run("Tune diction.", deps=deps)
    return result.output.model_dump(mode="json")


@mcp.tool
async def voice_compose_step(
    name: str,
    current_field: str = "purpose",
    profile: dict[str, object] | None = None,
) -> list[dict[str, object]]:
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
    """Raw voice.md for the named voice, including front-matter + prose body."""
    return read_voice_file(name)


def run_stdio() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")
