"""Behavioral tests for the prose CLI scaffold."""

from __future__ import annotations

from typer.testing import CliRunner

from prose_craft import __version__
from prose_craft.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_config_prints_model_and_voices_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:claude-haiku-4-5")
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "anthropic:claude-haiku-4-5" in result.stdout
    assert str(tmp_path) in result.stdout


def test_voice_list_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["voice", "list"])
    assert result.exit_code == 0
    assert "no voices" in result.stdout.lower() or result.stdout.strip() == ""
