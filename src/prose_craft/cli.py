"""Typer CLI for prose-craft.

Subcommands:

* ``version`` — print the engine version and exit.
* ``config`` — print the active model and voices root.
* ``voice list`` — enumerate every voice under the active root.
* ``voice show`` — print a voice profile (markdown rendering or raw file).

Subsequent CLI tasks (29-32) will add ``voice check``, ``voice init``,
``migrate-voice``, and ``voice compose``/``voice refine``/``voice draft``/
``voice edit`` under the same ``voice`` sub-typer.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown

from prose_craft import __version__
from prose_craft.config import get_model, get_voices_root
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
