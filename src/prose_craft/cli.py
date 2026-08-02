"""Typer CLI for prose-craft.

Subcommands:

* ``version`` — print the engine version and exit.
* ``config`` — print the active model and voices root.
* ``voice list`` — enumerate every voice under the active root.
* ``voice show`` — print a voice profile (markdown rendering or raw file).
* ``analyze`` — run the analyst agent (or deterministic metrics only).
* ``edit`` — run the editor agent; optionally write the result back to the file.
* ``architect`` — run the architect agent; print a structural analysis.
* ``tune-diction`` — run the tune-diction agent; print a substitution plan.

Subsequent CLI tasks (30-32) will add ``voice check``, ``voice init``,
``migrate-voice``, and ``voice compose``/``voice refine``/``voice draft``/
``voice edit`` under the same ``voice`` sub-typer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import typer
from rich.console import Console
from rich.markdown import Markdown

from prose_craft import __version__
from prose_craft.config import get_model, get_voices_root
from prose_craft.orchestrator.root import ProseCraft
from prose_craft.voices.io import list_voices, read_voice_raw

__all__ = ["app", "voice_app"]


app = typer.Typer(
    name="prose",
    help="prose-craft: pydantic-ai engine for designing and applying prose voices.",
)
console = Console()

voice_app = typer.Typer(help="Voice profile operations.")
app.add_typer(voice_app, name="voice")


def _voices_root_opt(root: Path | None) -> Path:
    """Return the active voices root, honoring a CLI override."""
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
    voices_root: Path | None = typer.Option(
        None, "--voices-root", help="Override the voices root."
    ),
) -> None:
    """Print the active model and voices root."""
    import os

    if model:
        os.environ["PROSE_CRAFT_MODEL"] = model
    if voices_root:
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
        lines.extend(
            [
                "",
                "# Clause density",
                f"- ppc: {diag.clause_density.ppc_per_1k}/1k",
                f"- agentless_passive: {diag.clause_density.agentless_passive_per_1k}/1k",
            ]
        )
    if diag.issues:
        lines.extend(["", "**Issues**"] + [f"- {i}" for i in diag.issues])
    return "\n".join(lines)


@app.command()
def analyze(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str | None = typer.Option(None, "--voice"),
    tolerance: Literal["strict", "normal", "relaxed"] = typer.Option("normal", "--tolerance"),
    metrics_only: bool = typer.Option(False, "--metrics-only"),
) -> None:
    """Run the analyst agent (or deterministic metrics only)."""
    from prose_craft.agents.results import ProseDiagnostic
    from prose_craft.analysis.metrics import analyze_prose
    from prose_craft.orchestrator.deps import AnalysisDeps

    if metrics_only:
        text = file.read_text(encoding="utf-8")
        m = analyze_prose(text)
        diag = ProseDiagnostic.model_validate({"metrics": m, "issues": []})
        typer.echo(_render_prose_diagnostic(diag))
        return
    craft = ProseCraft()
    result = craft.analyst().run_sync(
        "Analyze this prose.",
        deps=AnalysisDeps(
            file_path=file,
            voice_name=voice,
            tolerance=tolerance,
        ),
    )
    typer.echo(_render_prose_diagnostic(result.output))


@app.command()
def edit(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str | None = typer.Option(None, "--voice"),
    tolerance: Literal["strict", "normal", "relaxed"] = typer.Option("normal", "--tolerance"),
    in_place: bool = typer.Option(
        False, "--in-place", help="Write the edited text back to the file."
    ),
) -> None:
    """Run the editor agent; print the change_log and the new text."""
    from prose_craft.orchestrator.deps import EditorDeps

    craft = ProseCraft()
    result = craft.editor().run_sync(
        "Edit this prose.",
        deps=EditorDeps(
            file_path=file,
            voice_name=voice,
            tolerance=tolerance,
        ),
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
