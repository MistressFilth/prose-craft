"""Behavioral tests for the prose CLI scaffold."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic_ai import ModelRetry, UsageLimitExceeded
from typer.testing import CliRunner

import prose_craft.cli as cli_module
from prose_craft import __version__
from prose_craft.cli import app
from prose_craft.config import (
    DEFAULT_MODEL,
    config_file,
    load_settings,
)
from prose_craft.paths import default_voices_root
from prose_craft.voices.io import VoiceProfileNotFound

runner = CliRunner()


def _write_config(text: str) -> Path:
    """Write ``text`` to the test's XDG config.toml and return the path."""
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


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
    def __init__(self, error: Exception, **_kwargs: object) -> None:
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
    monkeypatch.setattr(cli_module, "ProseCraft", lambda *_a, **_k: _FailingCraft(error))
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
    monkeypatch.setattr(
        cli_module, "ProseCraft", lambda *_a, **_k: _FailingCraft(RuntimeError("boom"))
    )
    result = runner.invoke(app, ["analyze", str(draft)])
    assert result.exit_code == 1
    assert "Traceback (most recent call last)" in result.output
    assert "RuntimeError: boom" in result.output


def test_config_does_not_mutate_environment(monkeypatch, tmp_path) -> None:
    """--voices-root affects the printed value only, not process env."""
    import os

    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)

    result = runner.invoke(
        app,
        ["config", "--voices-root", str(tmp_path), "--model", "anthropic:claude-haiku-4-5"],
    )

    assert result.exit_code == 0
    assert str(tmp_path) in result.stdout
    assert "anthropic:claude-haiku-4-5" in result.stdout
    assert "PROSE_CRAFT_VOICES_ROOT" not in os.environ
    assert "PROSE_CRAFT_MODEL" not in os.environ


# ---------------------------------------------------------------------------
# Persistent settings integration (Task 5)
# ---------------------------------------------------------------------------


def test_config_reports_file_and_effective_values() -> None:
    """`prose config` reports the config file's path and the in-effect values."""
    result = runner.invoke(app, ["config"])

    assert result.exit_code == 0
    assert f"config_file: {config_file()}" in result.output
    assert f"model: {DEFAULT_MODEL}" in result.output
    assert f"voices_root: {default_voices_root()}" in result.output


def test_config_init_creates_active_defaults() -> None:
    """`prose config --init` writes the config file and the values are then effective."""
    result = runner.invoke(app, ["config", "--init"])

    assert result.exit_code == 0, result.output
    assert f"created: {config_file()}" in result.output
    settings = load_settings()
    assert settings.model == DEFAULT_MODEL
    assert settings.voices_root == default_voices_root()


def test_config_init_refuses_existing_file() -> None:
    """`prose config --init` leaves a pre-existing file alone and exits 2."""
    path = config_file()
    path.parent.mkdir(parents=True)
    original = b"\xffinvalid"
    path.write_bytes(original)

    result = runner.invoke(app, ["config", "--init"])

    assert result.exit_code == 2
    assert "already exists" in result.output
    assert path.read_bytes() == original


def test_config_init_rejects_combined_overrides() -> None:
    """`--init` and the override flags are mutually exclusive."""
    result = runner.invoke(app, ["config", "--init", "--model", "anthropic:test"])

    assert result.exit_code != 0
    assert "--init" in result.output


def test_version_ignores_malformed_config() -> None:
    """A broken TOML config must not break the version command."""
    _write_config('model = "unterminated\n')

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_settings_command_reports_malformed_config_without_traceback() -> None:
    """`prose config` reports the bad config path without a traceback."""
    path = _write_config('model = "unterminated\n')

    result = runner.invoke(app, ["config"])

    assert result.exit_code == 2
    assert str(path) in result.output
    assert "configuration error" in result.output
    assert "Traceback" not in result.output


def test_voice_init_uses_toml_voices_root(tmp_path: Path) -> None:
    """Configured voices_root in TOML is the destination for `voice init`."""
    configured = tmp_path / "configured-voices"
    _write_config(f'[paths]\nvoices_root = "{configured.as_posix()}"\n')

    result = runner.invoke(app, ["voice", "init", "layout-probe"])

    assert result.exit_code == 0, result.output
    assert (configured / "layout-probe" / "voice.md").is_file()


# ---------------------------------------------------------------------------
# Precedence: CLI > env > TOML > defaults
# ---------------------------------------------------------------------------


def _prec_toml() -> str:
    """The TOML the precedence tests start from."""
    return 'model = "anthropic:toml-4-5"\n\n[paths]\nvoices_root = "/tmp/toml-voices"\n'


def test_cli_overrides_environment_over_toml(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit flags beat the environment, which beats TOML."""
    _write_config(_prec_toml())
    explicit_root = "/tmp/explicit-voices"
    explicit_model = "anthropic:explicit-4-5"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", "/tmp/env-voices")
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:env-4-5")

    result = runner.invoke(
        app,
        [
            "config",
            "--voices-root",
            explicit_root,
            "--model",
            explicit_model,
        ],
    )

    assert result.exit_code == 0, result.output
    assert f"model: {explicit_model}" in result.output
    assert f"voices_root: {Path(explicit_root).resolve()}" in result.output


def test_environment_overrides_toml(monkeypatch: pytest.MonkeyPatch) -> None:
    """Env vars beat TOML when no CLI override is given."""
    _write_config(_prec_toml())
    environment_root = "/tmp/env-voices"
    environment_model = "anthropic:env-4-5"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", environment_root)
    monkeypatch.setenv("PROSE_CRAFT_MODEL", environment_model)

    result = runner.invoke(app, ["config"])

    assert result.exit_code == 0, result.output
    assert f"model: {environment_model}" in result.output
    assert f"voices_root: {Path(environment_root)}" in result.output


def test_toml_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """When TOML is set and env is clear, TOML wins over defaults."""
    toml_root = "/tmp/toml-voices"
    toml_model = "anthropic:toml-4-5"
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    _write_config(f'model = "{toml_model}"\n\n[paths]\nvoices_root = "{toml_root}"\n')

    result = runner.invoke(app, ["config"])

    assert result.exit_code == 0, result.output
    assert f"model: {toml_model}" in result.output
    assert f"voices_root: {Path(toml_root)}" in result.output


def test_config_init_dirties_no_env_after_load(monkeypatch: pytest.MonkeyPatch) -> None:
    """initialize_config must not leak env vars into the caller."""
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)

    result = runner.invoke(app, ["config", "--init"])

    assert result.exit_code == 0, result.output
    assert "PROSE_CRAFT_VOICES_ROOT" not in os.environ
    assert "PROSE_CRAFT_MODEL" not in os.environ
    # Clean up: remove the freshly written config so conftest isolation
    # stays straightforward for the next test.
    config_file().unlink(missing_ok=True)
