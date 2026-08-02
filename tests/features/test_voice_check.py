"""Behavioral tests for the voice check and voice init subcommands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


def _write_voice(root: Path, name: str) -> Path:
    vdir = root / name
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "voice.md").write_text(
        f"---\nvoice: {name}\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
        "register:\n  funny_serious: null\ndiction:\n  banned: [utilize]\nrhythm: {}\n"
        "syntax: {}\nlexicon: {}\nstructure: {}\n---\n",
        encoding="utf-8",
    )
    return vdir / "voice.md"


def test_voice_check_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, "MistressFilth")
    draft = tmp_path / "p.md"
    draft.write_text("We will utilize this.", encoding="utf-8")
    result = runner.invoke(app, ["voice", "check", str(draft), "--voice", "MistressFilth", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "mechanical" in data


def test_voice_init_creates_template(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["voice", "init", "newv"])
    assert result.exit_code == 0
    assert (tmp_path / "newv" / "voice.md").exists()
