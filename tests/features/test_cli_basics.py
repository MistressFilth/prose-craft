"""Behavioral tests for the prose CLI scaffold."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
import pytest
import typer
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
    """Path traversal in the voice name exits 2 with no traceback.

    Regression: ``VoiceNameError`` is a documented user-input error, not
    an internal crash. The CLI's :func:`_handle_errors` catches it
    alongside ``VoiceProfileNotFound`` so the user sees a one-line
    message instead of a traceback.
    """
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["voice", "show", "../../etc/passwd", "--raw"])
    assert result.exit_code == 2
    assert "invalid voice name" in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize(
    "args, expect_message",
    [
        # Paths that reach ``voice_path`` and therefore raise
        # ``VoiceNameError``; the CLI surfaces that with a one-line
        # ``invalid voice name`` message via the dedicated handler arm.
        (["voice", "show", "../escape"], True),
        (["voice", "show", "../escape", "--raw"], True),
        (["voice", "show", "name with spaces"], True),
        (["voice", "init", "../escape"], True),
        (["voice", "init", "name with spaces"], True),
        (["voice", "compose", "../escape"], True),
        (["voice", "refine", "../escape"], True),
        # Typer rejects an empty positional name up front, before any
        # prose-craft code runs, so the user sees Typer's own message
        # rather than ``VoiceNameError``'s wording. The exit code is
        # still 2 and there is no traceback.
        (["voice", "show", ""], False),
    ],
)
def test_voice_subcommands_reject_invalid_name_without_traceback(
    monkeypatch, tmp_path: Path, args: list[str], expect_message: bool
) -> None:
    """Every voice subcommand surfaces :class:`VoiceNameError` as exit 2.

    Strengthens the original traversal test: rather than exercising one
    code path, it sweeps the documented subcommands that touch
    ``voice_path`` (``read_voice`` / ``read_voice_raw`` / ``write_voice``)
    to make sure the new exception arm in :func:`_handle_errors` covers
    all of them. A failure here means a subcommand silently regressed to
    the generic ``Exception`` arm and prints a traceback.

    ``expect_message=True`` cases hit ``voice_path`` and surface the
    ``invalid voice name`` wording; ``False`` cases are stopped by
    Typer's argument validation (empty string) before any prose-craft
    code runs, so the wording is Typer-owned.
    """
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    if "draft.md" in args:
        (tmp_path / "draft.md").write_text("hello world", encoding="utf-8")
    result = runner.invoke(app, args)
    assert result.exit_code == 2, result.output
    assert "Traceback" not in result.output
    if expect_message:
        assert "invalid voice name" in result.output


def test_voice_check_and_edit_reject_invalid_voice_with_existing_file(
    monkeypatch, tmp_path: Path
) -> None:
    """``voice check`` / ``voice edit`` surface an invalid ``--voice`` as exit 2.

    Separated from the parameterized matrix because both commands take a
    positional ``file`` argument that must exist (``exists=True``); the
    test creates the file at an absolute ``tmp_path`` so Typer's
    pre-flight check passes and the invalid voice name reaches
    ``voice_path`` exactly once.
    """
    draft = tmp_path / "draft.md"
    draft.write_text("hello world", encoding="utf-8")
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))

    for cmd in (["voice", "check"], ["voice", "edit"]):
        result = runner.invoke(app, [*cmd, str(draft), "--voice", "../escape"])
        assert result.exit_code == 2, (cmd, result.output)
        assert "invalid voice name" in result.output
        assert "Traceback" not in result.output


def test_voice_refine_propagates_voice_compose_exit_code(monkeypatch, tmp_path: Path) -> None:
    """Nested Typer wrappers must preserve the inner ``typer.Exit(code)``.

    Regression: ``voice_refine`` calls ``voice_compose`` directly (not
    via the Typer dispatcher), and ``voice_compose``'s ``_handle_errors``
    wrapper raises ``typer.Exit(code=2)`` for an invalid voice name.
    Without an explicit ``except typer.Exit: raise`` at the top of
    ``_handle_errors``, that Exit is a ``RuntimeError`` subclass and the
    outer ``voice_refine`` wrapper's generic ``except Exception`` arm
    catches it, prints a traceback, and re-raises ``typer.Exit(code=1)``
    — silently downgrading the documented exit code and leaking a
    traceback to a user-input error. The fix preserves the inner code
    and suppresses the traceback.
    """
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))

    result = runner.invoke(app, ["voice", "refine", "../escape"])

    assert result.exit_code == 2, result.output
    assert "invalid voice name" in result.output
    assert "Traceback" not in result.output


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
    """`--init` combined with `--model` is a clean exit-2, no traceback.

    Regression: an earlier revision raised ``typer.BadParameter`` inside
    the command and let it fall through the generic ``Exception`` arm of
    ``_handle_errors``, which prints a traceback and exits 1 — wrong for
    a documented, user-facing parameter conflict.
    """
    result = runner.invoke(app, ["config", "--init", "--model", "anthropic:test"])

    assert result.exit_code == 2
    assert "--init" in result.output
    assert "cannot be combined" in result.output
    assert "Traceback" not in result.output


def test_config_init_mkdir_failure_exits_two_without_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Write-side OSError must surface as a clean exit-2 with no traceback.

    Previously the ``mkdir`` ran outside the OSError boundary and a
    ``PermissionError`` reached the generic ``Exception`` arm of the CLI
    error handler, which prints a traceback and exits 1. The fix moves
    ``mkdir`` and ``mkstemp`` inside the boundary so the user sees the
    same ``configuration error: could not write`` wording as a fsync or
    link failure.
    """
    target = config_file()

    def fail_mkdir(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(13, "Permission denied", str(target.parent))

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    result = runner.invoke(app, ["config", "--init"])

    assert result.exit_code == 2, result.output
    assert "could not write" in result.output
    assert "configuration error" in result.output
    assert "Traceback" not in result.output


def test_config_init_mkstemp_failure_exits_two_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ENOSPC at ``mkstemp`` must surface as a clean exit-2 with no traceback."""
    import tempfile as _tempfile

    def fail_mkstemp(**_kwargs: object) -> tuple[int, str]:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(_tempfile, "mkstemp", fail_mkstemp)

    result = runner.invoke(app, ["config", "--init"])

    assert result.exit_code == 2, result.output
    assert "could not write" in result.output
    assert "No space left on device" in result.output
    assert "Traceback" not in result.output


def test_config_rejects_empty_model_flag_without_traceback() -> None:
    """``prose config --model ""`` exits 2 without a traceback.

    The schema rejects an empty/whitespace-only model so a user who
    forgot to fill in the value sees a one-line message instead of the
    analyzer silently falling back to the default. The CLI must surface
    this as a clean configuration error.
    """
    result = runner.invoke(app, ["config", "--model", ""])

    assert result.exit_code == 2, result.output
    assert "configuration error" in result.output
    assert "model must not be empty" in result.output
    assert "Traceback" not in result.output


def test_config_rejects_whitespace_model_flag_without_traceback() -> None:
    """``prose config --model "   "`` exits 2 without a traceback."""
    result = runner.invoke(app, ["config", "--model", "   "])

    assert result.exit_code == 2, result.output
    assert "configuration error" in result.output
    assert "model must not be empty" in result.output
    assert "Traceback" not in result.output


def test_analyze_metrics_only_survives_malformed_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`analyze --metrics-only` must not consult the config file.

    The metrics-only path is a deterministic analyzer that reads only
    the file argument; loading settings is wasted work and any error
    there must not poison the command. A broken TOML config file
    therefore must not affect this command's exit code or output.
    """
    draft = tmp_path / "draft.md"
    draft.write_text("This is a short draft.", encoding="utf-8")
    _write_config('model = "unterminated\n')

    result = runner.invoke(app, ["analyze", "--metrics-only", str(draft)])

    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    assert "configuration error" not in result.output
    assert "Words" in result.output


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


def _prec_toml(toml_root: Path) -> str:
    """The TOML the precedence tests start from.

    ``toml_root`` must be an absolute path under ``tmp_path`` so the
    strict ``PathsSettings.validate_voices_root`` check accepts it on
    every platform. Hard-coding POSIX ``/tmp/...`` would reject the
    value on Windows (``Path.is_absolute()`` returns ``False``), which
    surfaces as ``configuration error`` and breaks the precedence
    ordering before any of the layers can be exercised.
    """
    return f'model = "anthropic:toml-4-5"\n\n[paths]\nvoices_root = {json.dumps(str(toml_root))}\n'


def test_cli_overrides_environment_over_toml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Explicit flags beat the environment, which beats TOML."""
    toml_root = tmp_path / "toml-voices"
    explicit_root = tmp_path / "explicit-voices"
    explicit_model = "anthropic:explicit-4-5"
    environment_root = tmp_path / "env-voices"
    environment_model = "anthropic:env-4-5"
    _write_config(_prec_toml(toml_root))
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(environment_root))
    monkeypatch.setenv("PROSE_CRAFT_MODEL", environment_model)

    result = runner.invoke(
        app,
        [
            "config",
            "--voices-root",
            str(explicit_root),
            "--model",
            explicit_model,
        ],
    )

    assert result.exit_code == 0, result.output
    assert f"model: {explicit_model}" in result.output
    assert f"voices_root: {explicit_root.resolve()}" in result.output


def test_environment_overrides_toml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Env vars beat TOML when no CLI override is given."""
    toml_root = tmp_path / "toml-voices"
    environment_root = tmp_path / "env-voices"
    environment_model = "anthropic:env-4-5"
    _write_config(_prec_toml(toml_root))
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(environment_root))
    monkeypatch.setenv("PROSE_CRAFT_MODEL", environment_model)

    result = runner.invoke(app, ["config"])

    assert result.exit_code == 0, result.output
    assert f"model: {environment_model}" in result.output
    assert f"voices_root: {environment_root}" in result.output


def test_toml_overrides_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When TOML is set and env is clear, TOML wins over defaults."""
    toml_root = tmp_path / "toml-voices"
    toml_model = "anthropic:toml-4-5"
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    _write_config(
        f'model = "{toml_model}"\n\n[paths]\nvoices_root = {json.dumps(str(toml_root))}\n'
    )

    result = runner.invoke(app, ["config"])

    assert result.exit_code == 0, result.output
    assert f"model: {toml_model}" in result.output
    assert f"voices_root: {toml_root}" in result.output


def test_config_init_dirties_no_env_after_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """initialize_config must not leak env vars into the caller.

    The config file this test writes lives under ``tmp_path``; the
    per-test ``_isolated_dirs`` fixture guarantees the next test gets a
    fresh tmp_path, so no manual cleanup is needed.
    """
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)

    result = runner.invoke(app, ["config", "--init"])

    assert result.exit_code == 0, result.output
    assert "PROSE_CRAFT_VOICES_ROOT" not in os.environ
    assert "PROSE_CRAFT_MODEL" not in os.environ
    assert config_file() == tmp_path / ".xdg" / "config" / "prose-craft" / "config.toml"


# ---------------------------------------------------------------------------
# Dependency-contract probe: Typer and Click expose independent class
# hierarchies. ``typer.BadParameter`` lives in ``typer._click.exceptions``
# (Typer's bundled internal copy of Click); the CLI's ``except
# (typer.BadParameter, click.UsageError)`` clause must catch both
# because they are not related by inheritance. Removing either branch
# would silently re-introduce tracebacks on parameter conflicts.
# ---------------------------------------------------------------------------


def test_typer_bad_parameter_is_not_a_click_usage_error_subclass() -> None:
    """Probe: ``typer.BadParameter`` is not a subclass of ``click.UsageError``.

    Verified against ``typer==0.27.0`` and ``click==8.4.2``. If a future
    upgrade unifies the two (e.g. Typer re-exports Click directly), the
    ``except (typer.BadParameter, click.UsageError)`` clause in
    :func:`prose_craft.cli._handle_errors` can be simplified to the
    broader class only — but until that happens, the tuple is required.
    """
    assert typer.BadParameter.__module__ == "typer._click.exceptions"
    assert click.UsageError.__module__ == "click.exceptions"
    assert not issubclass(typer.BadParameter, click.UsageError)
    assert not issubclass(click.UsageError, typer.BadParameter)


def test_config_init_combined_override_still_exits_two_without_traceback() -> None:
    """End-to-end smoke for the exception tuple.

    If :func:`prose_craft.cli._handle_errors` ever drops either
    ``typer.BadParameter`` or ``click.UsageError`` from the catch
    tuple, this command would print a traceback instead of a one-line
    message and exit 2. The probe above pins the contract; this test
    exercises the path.
    """
    result = runner.invoke(app, ["config", "--init", "--model", "anthropic:test"])
    assert result.exit_code == 2
    assert "--init" in result.output
    assert "cannot be combined" in result.output
    assert "Traceback" not in result.output
