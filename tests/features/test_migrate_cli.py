"""Behavioral tests for the `prose migrate voices` subcommand."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


def _seed(root: Path, name: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "voice.md").write_text(
        f"---\nvoice: {name}\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
        "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n",
        encoding="utf-8",
    )


def test_migrate_voices_cli(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _seed(src, "alpha")
    _seed(src, "beta")
    result = runner.invoke(
        app, ["migrate", "voices", "--src", str(src), "--dst", str(dst)]
    )
    assert result.exit_code == 0, result.stdout
    assert (dst / "alpha" / "voice.md").exists()
    assert (dst / "beta" / "voice.md").exists()


def test_migrate_voices_dry_run(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _seed(src, "alpha")
    result = runner.invoke(
        app,
        [
            "migrate",
            "voices",
            "--src",
            str(src),
            "--dst",
            str(dst),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert not (dst / "alpha" / "voice.md").exists()