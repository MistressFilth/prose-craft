"""Behavioral tests for the prose CLI scaffold."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai import ModelRetry, UsageLimitExceeded
from typer.testing import CliRunner

import prose_craft.cli as cli_module
from prose_craft import __version__
from prose_craft.cli import app
from prose_craft.voices.io import VoiceProfileNotFound

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
    """An empty user root shows "(no voices)" — no bundled fallback."""
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["voice", "list"])
    assert result.exit_code == 0
    assert "no voices" in result.stdout.lower() or result.stdout.strip() == ""


def test_voice_show_raw_rejects_path_traversal(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["voice", "show", "../../etc/passwd", "--raw"])
    assert result.exit_code == 1
    assert "invalid voice name" in result.output


class _FailingAgent:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def run_sync(self, *_args, **_kwargs):
        raise self.error


class _FailingCraft:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def analyst(self) -> _FailingAgent:
        return _FailingAgent(self.error)


@pytest.mark.parametrize(
    "error",
    [ModelRetry("retry with a clearer prompt"), UsageLimitExceeded("usage limit reached")],
)
def test_cli_model_errors_print_hint_and_exit_one(
    monkeypatch, tmp_path: Path, error: Exception
) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    monkeypatch.setattr(cli_module, "ProseCraft", lambda: _FailingCraft(error))
    result = runner.invoke(app, ["analyze", str(draft)])
    assert result.exit_code == 1
    assert str(error) in result.output


def test_cli_missing_voice_prints_list_hint_and_exits_two(monkeypatch, tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    monkeypatch.setattr(
        cli_module,
        "read_voice_raw",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(VoiceProfileNotFound("missing voice")),
    )
    result = runner.invoke(app, ["voice", "show", "missing"])
    assert result.exit_code == 2
    assert "missing voice" in result.output
    assert "prose voice list" in result.output


def test_cli_unexpected_error_prints_traceback_and_exits_one(monkeypatch, tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("A draft.", encoding="utf-8")
    monkeypatch.setattr(cli_module, "ProseCraft", lambda: _FailingCraft(RuntimeError("boom")))
    result = runner.invoke(app, ["analyze", str(draft)])
    assert result.exit_code == 1
    assert "Traceback (most recent call last)" in result.output
    assert "RuntimeError: boom" in result.output
