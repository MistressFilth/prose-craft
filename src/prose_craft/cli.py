"""Typer CLI for prose-craft.

Subcommands:

* ``version`` — print the engine version and exit.
* ``config`` — print the config file path and the effective model and
  voices root, or initialize a new config file with ``--init``.
* ``voice list`` — enumerate every voice under the active root.
* ``voice show`` — print a voice profile (markdown rendering or raw file).
* ``analyze`` — run the analyst agent (or deterministic metrics only).
* ``edit`` — run the editor agent; optionally write the result back to the file.
* ``architect`` — run the architect agent; print a structural analysis.
* ``tune-diction`` — run the tune-diction agent; print a substitution plan.
* ``voice check`` — run the deterministic voice check (mechanical,
  statistical, judgments-needed) and render markdown or ``--json``.
* ``voice init`` — scaffold a blank voice.md from the template.
* ``voice compose`` — interactive REPL to design a voice profile.
* ``voice refine`` — alias of ``voice compose`` for iterating on an
  existing profile.
* ``voice draft`` — run the voice-stylist agent in draft mode.
* ``voice edit`` — run the voice-stylist agent in edit mode against a file.
* ``voice delete`` — remove a voice from the user root; refuses shared-only
  voices even with ``--force``; ``--voices-root`` bypasses the shared check.
* ``mcp`` — launch the FastMCP server over stdio for MCP hosts.
* ``migrate voices`` — copy voice profiles from a legacy location to the
  XDG root.
"""

from __future__ import annotations

from functools import wraps
from pathlib import Path
import os
import sys
import traceback
from typing import Any, Literal

import click
import typer
from pydantic_ai import ModelRetry, UsageLimitExceeded
from rich.console import Console
from rich.markdown import Markdown

from prose_craft import __version__
from prose_craft.agents.results import VoiceDelta
from prose_craft.config import (
    ConfigurationError,
    ProseCraftSettings,
    config_file,
    initialize_config,
    load_settings,
)
from prose_craft.orchestrator.root import ProseCraft
from prose_craft.voices.audience import AudienceNotFoundError
from prose_craft.voices.io import (
    VoiceDeleteError,
    VoiceProfileNotFound,
    list_voices,
    read_voice,
    read_voice_raw,
)
from prose_craft.voices.location import VoiceNameError, voice_path

__all__ = ["app", "voice_app"]


app = typer.Typer(
    name="prose",
    help="prose-craft: pydantic-ai engine for designing and applying prose voices.",
)
console = Console()


def _settings(
    *,
    model: str | None = None,
    voices_root: Path | None = None,
) -> ProseCraftSettings:
    """Build effective settings from CLI overrides.

    Each call constructs a fresh :class:`ProseCraftSettings` so failures
    surface cleanly. Explicit arguments win; everything else is read
    from the XDG config file and the environment via the precedence
    chain implemented in :func:`prose_craft.config.load_settings`.
    """
    return load_settings(
        model=model,
        voices_root=voices_root.resolve() if voices_root is not None else None,
    )


def _handle_errors(func: Any) -> Any:
    """Render the CLI's documented exception classes consistently."""

    @wraps(func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except typer.Exit:
            # Propagate Exit unchanged so a subcommand that calls another
            # Typer-wrapped command (``voice_refine`` → ``voice_compose``)
            # does not downgrade the inner exit code through the generic
            # ``Exception`` arm.
            raise
        except (ModelRetry, UsageLimitExceeded) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        except VoiceProfileNotFound as exc:
            typer.echo(str(exc), err=True)
            typer.echo("Run `prose voice list` to see available voices.", err=True)
            raise typer.Exit(code=2) from exc
        except VoiceNameError as exc:
            # Path-traversal attempts and other invalid voice names reach
            # here from ``voice_path`` via ``read_voice`` /
            # ``read_voice_raw`` / ``write_voice``. ``ValueError`` parents
            # include it, but the handler is registered explicitly so the
            # message lands once on stderr with no traceback and the exit
            # code is 2 — a documented user-input error, not a crash.
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except VoiceDeleteError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except AudienceNotFoundError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except ConfigurationError as exc:
            typer.echo(f"configuration error: {exc}", err=True)
            raise typer.Exit(code=2) from exc
        except (typer.BadParameter, click.UsageError) as exc:
            # Parameter conflicts (``--init`` + ``--model``, etc.) and
            # any other user-facing argument validation errors must not
            # print a traceback. ``typer.BadParameter`` and
            # ``click.UsageError`` are sibling class hierarchies
            # (typer's exceptions live in ``typer._click.exceptions``);
            # catching both keeps the handler robust whichever one a
            # given command raises.
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=2) from exc
        except Exception:
            traceback.print_exc(file=sys.stderr)
            raise typer.Exit(code=1)

    return wrapped


voice_app = typer.Typer(help="Voice profile operations.")
app.add_typer(voice_app, name="voice")


def _voices_root_opt(root: Path | None) -> Path:
    """Return the configured voices root, honoring a CLI override.

    The override is resolved to an absolute path so the printed value
    matches what the rest of the run will see — a relative
    ``--voices-root`` would otherwise compare unequal under
    ``voice list`` (which uses the resolved path).
    """
    if root is not None:
        return root.resolve()
    return load_settings().voices_root


@app.command()
@_handle_errors
def version() -> None:
    """Print the engine version and exit."""
    typer.echo(f"prose-craft {__version__}")


@app.command()
@_handle_errors
def config(
    init: bool = typer.Option(False, "--init", help="Create the configuration file."),
    model: str | None = typer.Option(None, "--model", help="Override the model."),
    voices_root: Path | None = typer.Option(
        None,
        "--voices-root",
        help="Override the voices root.",
    ),
) -> None:
    """Print the config file path and effective values.

    With ``--init``, create the XDG config file with built-in defaults
    and exit. ``--init`` is mutually exclusive with ``--model`` and
    ``--voices-root`` so callers cannot silently capture a one-shot
    override into persistent storage.
    """
    if init:
        if model is not None or voices_root is not None:
            raise typer.BadParameter("--init cannot be combined with --model or --voices-root")
        typer.echo(f"created: {initialize_config()}")
        return
    effective = _settings(model=model, voices_root=voices_root)
    typer.echo(f"config_file: {config_file()}")
    typer.echo(f"model: {effective.model}")
    typer.echo(f"voices_root: {effective.voices_root}")


@voice_app.command("list")
@_handle_errors
def voice_list(
    voices_root: Path | None = typer.Option(None, "--voices-root"),
    origin: str = typer.Option(
        "all",
        "--origin",
        help="Filter by voice origin.",
        case_sensitive=False,
    ),
) -> None:
    """List voices under the active root (user + shared by default)."""
    from prose_craft.voices.index import Origin, VoiceIndex
    from prose_craft.voices.io import list_voice_errors

    if origin not in ("user", "shared", "all"):
        raise typer.BadParameter("--origin must be one of: user, shared, all")

    if voices_root is not None:
        # Explicit override → single-root semantics, same as v0.4.0.
        root = _voices_root_opt(voices_root)
        summaries = list_voices(root=root)
        if not summaries:
            typer.echo("(no voices found)")
        else:
            for s in summaries:
                typer.echo(f"{s.name}  ({s.updated.isoformat()})")
        errors = list_voice_errors(root=root)
        for e in errors:
            typer.echo(f"error: {e.name}: {e.error}", err=True)
        return

    # Default → multi-root scan via VoiceIndex.
    idx = VoiceIndex.load_or_build()
    rows: list[tuple[str, Origin]] = []
    for name, entry in idx:
        if origin != "all" and (
            (origin == "user" and entry.origin is not Origin.USER)
            or (origin == "shared" and entry.origin is not Origin.SHARED)
        ):
            continue
        rows.append((name, entry.origin))
    rows.sort(key=lambda r: r[0])
    if not rows:
        typer.echo("(no voices found)")
        return
    for name, o in rows:
        typer.echo(f"{name} [{o.value}]")


@voice_app.command("show")
@_handle_errors
def voice_show(
    name: str = typer.Argument(..., help="Voice name."),
    raw: bool = typer.Option(False, "--raw", help="Print raw file contents."),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Print a voice profile as markdown or raw file."""
    from prose_craft.voices.index import VoiceIndex
    from prose_craft.voices.location import voice_path

    if voices_root is not None:
        # Explicit --voices-root → single-root semantics (matches v0.4.0).
        root = _voices_root_opt(voices_root)
        typer.echo(f"[user] {root / name / 'voice.md'}")
        if raw:
            from prose_craft.voices.io import _resolve_voice_path

            path = _resolve_voice_path(name, root)
            if path is None:
                raise typer.BadParameter(
                    f"voice {name!r} not found at {voice_path(name, root=root)}"
                )
            typer.echo(path.read_text(encoding="utf-8"))
            return
        profile, body = read_voice_raw(name, root=root)
    else:
        # Multi-root lookup via VoiceIndex. The annotation line surfaces
        # where the voice actually came from so an operator running the
        # command does not have to cross-reference `voice list`.
        #
        # Validate the name format FIRST via ``voice_path`` (cheap
        # explicit-root variant — regex check + path join, no scan).
        # ``VoiceIndex.build()`` does not enforce ``_NAME_RE``; it just
        # enumerates whatever directories exist. Without this guard an
        # invalidly named directory like ``123bad/voice.md`` could be
        # picked up by the index and then read directly via
        # ``entry.path.read_text()`` under ``--raw``, never raising the
        # documented ``VoiceNameError``.
        voice_path(name, root=load_settings().voices_root)
        entry = VoiceIndex.build().get(name)
        if entry is not None:
            typer.echo(f"[{entry.origin.value}] {entry.path}")
        else:
            # Name is valid but the voice does not exist anywhere.
            typer.echo(f"[user] {load_settings().voices_root / name / 'voice.md'}")
        if raw:
            if entry is None:
                raise typer.BadParameter(f"voice {name!r} not found")
            typer.echo(entry.path.read_text(encoding="utf-8"))
            return
        # ``root=None`` lets ``voice_path`` walk every root in
        # precedence order so a shared voice resolves correctly.
        profile, body = read_voice_raw(name, root=None)
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
@_handle_errors
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
    settings = _settings()
    craft = ProseCraft(model=settings.model, voices_root=settings.voices_root)
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
@_handle_errors
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

    settings = _settings()
    craft = ProseCraft(model=settings.model, voices_root=settings.voices_root)
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
@_handle_errors
def architect(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str | None = typer.Option(None, "--voice"),
) -> None:
    """Run the architect agent; print the reconstruction proposal."""
    from prose_craft.orchestrator.deps import ArchitectDeps

    settings = _settings()
    craft = ProseCraft(model=settings.model, voices_root=settings.voices_root)
    result = craft.architect().run_sync(
        "Architect this prose.",
        deps=ArchitectDeps(file_path=file, voice_name=voice),
    )
    typer.echo(f"## Analysis\n\n{result.output.analysis}\n")
    typer.echo(f"## Diagnosis\n\n{result.output.diagnosis}\n")
    typer.echo(f"## Reconstruction\n\n{result.output.reconstruction_proposal}\n")


@app.command("tune-diction")
@_handle_errors
def tune_dict(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str | None = typer.Option(None, "--voice"),
) -> None:
    """Run the tune-diction agent; print the substitution plan."""
    from prose_craft.orchestrator.deps import TuneDeps

    settings = _settings()
    craft = ProseCraft(model=settings.model, voices_root=settings.voices_root)
    result = craft.tune_diction().run_sync(
        "Tune diction.",
        deps=TuneDeps(file_path=file, voice_name=voice),
    )
    for s in result.output.suggestions:
        typer.echo(f"{s.instead_of} -> {s.use}  ({s.note})")


@voice_app.command("check")
@_handle_errors
def voice_check(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str = typer.Option(..., "--voice"),  # noqa: B008
    tolerance: Literal["strict", "normal", "relaxed"] = typer.Option("normal", "--tolerance"),
    as_json: bool = typer.Option(False, "--json"),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
    audience: str | None = typer.Option(
        None, "--audience", help="Audience name (private/team/external/...)."
    ),
    severity: int | None = typer.Option(
        None,
        "--severity",
        help="Severity ceiling 0-5 (overrides audience).",
        min=0,
        max=5,
    ),
    dial: float | None = typer.Option(
        None,
        "--dial",
        help="Dial ceiling 0.0-1.0 (overrides audience).",
        min=0.0,
        max=1.0,
    ),
    surface: str | None = typer.Option(
        None, "--surface", help="Target surface (e.g. memo/rfc/tweet)."
    ),
) -> None:
    """Run the deterministic voice check on a file."""
    from prose_craft.voices.audience import resolve_audience
    from prose_craft.voices.check import check_voice

    root = _voices_root_opt(voices_root)
    profile = read_voice(voice, root=root)
    text = file.read_text(encoding="utf-8")
    resolved = resolve_audience(
        voice,
        cli_audience=audience,
        cli_severity=severity,
        cli_dial=dial,
        cli_surface=surface,
        front_matter_path=file,
        voices_root=root,
    )
    for w in resolved.warnings if resolved else []:
        typer.echo(f"warning: {w}", err=True)
    target_surface = surface
    if target_surface is None and resolved is not None:
        target_surface = resolved.surface_target
    if target_surface is None:
        ext = file.suffix.lstrip(".")
        target_surface = ext or None
    verdict = check_voice(
        text,
        profile,
        tolerance=tolerance,
        audience=resolved,
        surface=target_surface,
    )
    if as_json:
        typer.echo(verdict.model_dump_json(indent=2))
        return
    lines = [f"# Voice check — {voice}", ""]
    if verdict.audience is not None:
        a = verdict.audience
        lines.append(
            f"Audience: {a.name}  (source: {a.source}, "
            f"severity ≤ {a.severity_ceiling}, dial ≤ {a.dial_ceiling})"
        )
        lines.append("")
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
@_handle_errors
def voice_init(
    name: str = typer.Argument(...),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Scaffold a blank voice.md from the template."""
    from prose_craft.voices.io import init_from_template, write_voice

    root = _voices_root_opt(voices_root)
    path = voice_path(name, root=root)
    if path.exists():
        raise typer.BadParameter(f"voice {name!r} already exists at {path}")
    profile, prose_body = init_from_template(name, root=root)
    write_voice(profile, prose_body, root=root)
    from prose_craft.voices.io import invalidate_index_cache as _invalidate

    _invalidate()
    typer.echo(f"initialized {path}")


def _apply_delta(payload: dict[str, Any], delta: VoiceDelta) -> None:
    """Apply a VoiceDelta to a serialized VoiceProfile payload."""
    if "." in delta.field:
        top, sub = delta.field.split(".", 1)
        payload.setdefault(top, {})
        if isinstance(payload[top], dict):
            payload[top][sub] = delta.value
    else:
        payload[delta.field] = delta.value


def _voice_compose_repl(name: str, root: Path, model: str) -> None:
    """Walk a writer through composing a voice, one dimension at a time."""
    from datetime import date

    from prose_craft.orchestrator.deps import ComposerDeps
    from prose_craft.voices.io import init_from_template, write_voice
    from prose_craft.voices.model import (
        VoiceProfile,
    )

    # Validate the name up front: ``voice_path`` raises ``VoiceNameError``
    # for empty / whitespace / path-traversal names and the CLI handler
    # surfaces that as exit 2 with no traceback. Without this guard the
    # blanket ``except Exception`` below would silently swallow the error
    # and proceed to construct an agent against an invalid name.
    voice_path(name, root=root)

    try:
        profile, body = read_voice_raw(name, root=root)
    except VoiceProfileNotFound:
        # Initialize from template.
        profile, body = init_from_template(name, root=root)
        write_voice(profile, body, root=root)
        from prose_craft.voices.io import invalidate_index_cache as _invalidate

        _invalidate()

    fields = [
        "purpose",
        "audience",
        "register",
        "diction",
        "rhythm",
        "syntax",
        "lexicon",
        "structure",
        "never",
    ]
    field_index = 0
    craft = ProseCraft(model=model, voices_root=root)
    agent = craft.voice_composer()

    while field_index < len(fields):
        current = fields[field_index]
        typer.echo(f"\n[{current}]")
        prompt_text = typer.prompt("(answer) ", default="", show_default=False)
        if prompt_text.strip().lower() in ("done", "exit", "quit"):
            break
        result = agent.run_sync(
            prompt_text or "next",
            deps=ComposerDeps(
                name=name,
                current_field=current,
                profile=profile.model_dump(mode="json"),
            ),
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


@voice_app.command("compose")
@_handle_errors
def voice_compose(
    name: str = typer.Argument(...),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Interactive REPL: walk the writer through composing a voice."""
    settings = _settings(voices_root=voices_root)
    _voice_compose_repl(name, settings.voices_root, settings.model)


@voice_app.command("refine")
@_handle_errors
def voice_refine(
    name: str = typer.Argument(...),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Refine a voice profile (alias of ``voice compose``)."""
    voice_compose(name=name, voices_root=voices_root)


@voice_app.command("draft")
@_handle_errors
def voice_draft(
    name: str = typer.Argument(...),
    brief: str = typer.Argument(..., help="The brief to write to."),
    to: Path | None = typer.Option(None, "--to", help="Output file; defaults to stdout."),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
    audience: str | None = typer.Option(
        None, "--audience", help="Audience name (private/team/external/...)."
    ),
    severity: int | None = typer.Option(
        None,
        "--severity",
        help="Severity ceiling 0-5 (overrides audience).",
        min=0,
        max=5,
    ),
    dial: float | None = typer.Option(
        None,
        "--dial",
        help="Dial ceiling 0.0-1.0 (overrides audience).",
        min=0.0,
        max=1.0,
    ),
    surface: str | None = typer.Option(
        None, "--surface", help="Target surface (e.g. memo/rfc/tweet)."
    ),
) -> None:
    """Draft prose in the named voice."""
    import tempfile

    from prose_craft.orchestrator.deps import StylistDeps
    from prose_craft.paths import scratch_dir
    from prose_craft.voices.audience import resolve_audience

    settings = _settings(voices_root=voices_root)
    root = settings.voices_root  # honor the override for env consistency
    # The stylist reads/writes the target file. The CLI seeds an empty
    # file at --to if given; the agent writes into it. Without --to we
    # use a scratch file under the runtime dir and remove it after.
    scratch: Path | None = None
    if to is not None:
        to.parent.mkdir(parents=True, exist_ok=True)
        to.touch()
        file_path = to
    else:
        fd, tmp_name = tempfile.mkstemp(suffix=".md", dir=scratch_dir())
        os.close(fd)
        scratch = Path(tmp_name)
        file_path = scratch

    try:
        resolved = resolve_audience(
            name,
            cli_audience=audience,
            cli_severity=severity,
            cli_dial=dial,
            cli_surface=surface,
            front_matter_path=file_path,
            voices_root=root,
        )
        for w in resolved.warnings if resolved else []:
            typer.echo(f"warning: {w}", err=True)

        craft = ProseCraft(model=settings.model, voices_root=root)
        result = craft.voice_stylist(audience=resolved).run_sync(
            f"Draft prose in voice {name!r}. Brief: {brief}",
            deps=StylistDeps(
                file_path=file_path,
                voice_name=name,
                brief=brief,
                mode="draft",
                audience=resolved,
            ),
        )
        if to is None:
            typer.echo(result.output.text)
    finally:
        if scratch is not None:
            scratch.unlink(missing_ok=True)


@voice_app.command("edit")
@_handle_errors
def voice_edit(
    file: Path = typer.Argument(..., exists=True),  # noqa: B008
    voice: str = typer.Option(..., "--voice"),  # noqa: B008
    in_place: bool = typer.Option(False, "--in-place"),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
    audience: str | None = typer.Option(
        None, "--audience", help="Audience name (private/team/external/...)."
    ),
    severity: int | None = typer.Option(
        None,
        "--severity",
        help="Severity ceiling 0-5 (overrides audience).",
        min=0,
        max=5,
    ),
    dial: float | None = typer.Option(
        None,
        "--dial",
        help="Dial ceiling 0.0-1.0 (overrides audience).",
        min=0.0,
        max=1.0,
    ),
    surface: str | None = typer.Option(
        None, "--surface", help="Target surface (e.g. memo/rfc/tweet)."
    ),
) -> None:
    """Edit a file in the named voice."""
    from prose_craft.config import load_settings
    from prose_craft.voices.index import Origin, VoiceIndex
    from prose_craft.voices.io import VoiceImportError, import_voice

    shadow_root = voices_root if voices_root is not None else load_settings().voices_root
    entry = VoiceIndex.build().get(voice)
    if entry is not None and entry.origin is Origin.SHARED:
        try:
            import_voice(voice, root=shadow_root)
        except VoiceImportError:
            pass  # already in user root (default or override); no-op

    from prose_craft.orchestrator.deps import StylistDeps
    from prose_craft.voices.audience import resolve_audience

    settings = _settings(voices_root=voices_root)
    root = settings.voices_root  # validate root exists

    resolved = resolve_audience(
        voice,
        cli_audience=audience,
        cli_severity=severity,
        cli_dial=dial,
        cli_surface=surface,
        front_matter_path=file,
        voices_root=root,
    )
    for w in resolved.warnings if resolved else []:
        typer.echo(f"warning: {w}", err=True)

    craft = ProseCraft(model=settings.model, voices_root=root)
    result = craft.voice_stylist(audience=resolved).run_sync(
        "Edit this prose in the named voice.",
        deps=StylistDeps(
            file_path=file,
            voice_name=voice,
            mode="edit",
            audience=resolved,
        ),
    )
    if in_place and result.output.text:
        file.write_text(result.output.text, encoding="utf-8")
    typer.echo(result.output.change_log or "(no change log)")


migrate_app = typer.Typer(help="Migration helpers.")
app.add_typer(migrate_app, name="migrate")


@app.command()
@_handle_errors
def mcp() -> None:
    """Run the FastMCP server over stdio."""
    from prose_craft.mcp import run_stdio

    run_stdio()


@migrate_app.command("voices")
@_handle_errors
def migrate_voices_cmd(
    src: Path | None = typer.Option(None, "--src"),
    dst: Path | None = typer.Option(None, "--dst"),
    overwrite: bool = typer.Option(False, "--overwrite"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Copy voice profiles from a legacy location to the XDG root."""
    from prose_craft.voices.migrate import migrate_voices

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


@voice_app.command("import")
@_handle_errors
def voice_import(
    name: str = typer.Argument(..., help="Voice name to import from a shared root."),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Copy a shared voice into the user root without editing."""
    from prose_craft.voices.io import VoiceImportError, import_voice

    shadow_root = voices_root if voices_root is not None else None
    try:
        target = import_voice(name, root=shadow_root)
    except VoiceImportError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)
    from prose_craft.voices.io import invalidate_index_cache as _invalidate

    _invalidate()
    typer.echo(f"imported {name!r} to {target}")


@voice_app.command("delete")
@_handle_errors
def voice_delete(
    name: str = typer.Argument(..., help="Voice name."),
    force: bool = typer.Option(False, "--force", help="Confirm deletion."),
    voices_root: Path | None = typer.Option(None, "--voices-root"),
) -> None:
    """Remove a voice from the user root.

    Refuses shared-only voices even with --force. Without --force, prints
    the path that would be deleted and exits 2 so the command is safe to
    use as a preview. With ``--voices-root PATH`` the command operates in
    single-root mode and bypasses the shared-voice check.
    """
    from prose_craft.config import load_settings
    from prose_craft.voices.io import VoiceDeleteError as _VD
    from prose_craft.voices.io import delete_voice as _delete
    from prose_craft.voices.location import voice_path as _voice_path
    from prose_craft.voices.location import voice_roots

    # Defense-in-depth: surface invalid names as a CLI error before any
    # ``user_root / name`` arithmetic. ``_voice_path`` raises
    # ``VoiceNameError`` directly.
    user_root = (
        _voices_root_opt(voices_root) if voices_root is not None else load_settings().voices_root
    )
    _voice_path(name, root=user_root if voices_root is not None else None)
    target = user_root / name

    # Find every root that holds this voice, so we can (a) detect
    # shared-only and (b) warn when both copies exist.
    roots = [user_root] if voices_root is not None else voice_roots()
    hits = [r for r in roots if (r / name / "voice.md").is_file()]

    if not hits:
        # Defer to delete_voice() so the error message + VoiceProfileNotFound
        # wiring are identical to the library path.
        _delete(name, root=user_root if voices_root is not None else None)
        return  # unreachable; _delete raises

    user_hit = user_root in hits

    if not user_hit:
        # Shared-only — refuse regardless of --force.
        raise _VD(f"voice {name!r} is shared-only; refusing to delete (root {hits[0]})")

    if not force:
        shared_note = ""
        if len(hits) > 1:
            shared_paths = [r / name for r in hits if r != user_root]
            shared_note = f"; shared copy at {shared_paths[0]} remains"
        typer.echo(
            f"would delete: {target}{shared_note} (pass --force to confirm)",
            err=True,
        )
        raise typer.Exit(code=2)

    deleted = _delete(name, root=user_root if voices_root is not None else None)
    from prose_craft.voices.io import invalidate_index_cache as _invalidate

    _invalidate()
    if len(hits) > 1:
        shared_paths = [r / name for r in hits if r != user_root]
        typer.echo(f"deleted: {deleted}; shared copy at {shared_paths[0]} remains")
    else:
        typer.echo(f"deleted: {deleted}")
