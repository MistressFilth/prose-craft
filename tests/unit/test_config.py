"""Tests for prose_craft.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from prose_craft.config import (
    DEFAULT_MODEL,
    ConfigurationError,
    PathsSettings,
    ProseCraftSettings,
    config_file,
    get_model,
    load_settings,
)
from prose_craft.paths import default_voices_root


# ---------------------------------------------------------------------------
# Public surface: get_model is preserved for downstream migration.
# ---------------------------------------------------------------------------


def test_get_model_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    assert get_model() == DEFAULT_MODEL
    assert DEFAULT_MODEL == "anthropic:claude-opus-4-5"


def test_get_model_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:claude-sonnet-4-5")
    assert get_model() == "anthropic:claude-sonnet-4-5"


def test_get_voices_root_re_export_is_gone() -> None:
    """Callers import voices_root from prose_craft.paths now."""
    from prose_craft import config

    assert not hasattr(config, "get_voices_root")


# ---------------------------------------------------------------------------
# Config location and missing-file defaults
# ---------------------------------------------------------------------------


def test_config_file_uses_xdg_config_home(tmp_path: Path) -> None:
    assert config_file() == (tmp_path / ".xdg" / "config" / "prose-craft" / "config.toml")


def test_missing_config_uses_defaults(tmp_path: Path) -> None:
    settings = load_settings()

    assert settings.model == DEFAULT_MODEL
    assert settings.voices_root == (tmp_path / ".xdg" / "data" / "prose-craft" / "voices")


# ---------------------------------------------------------------------------
# Full and partial TOML
# ---------------------------------------------------------------------------


def _write_config(text: str) -> Path:
    path = config_file()
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_full_toml_loads(tmp_path: Path) -> None:
    configured = tmp_path / "configured-voices"
    _write_config(f'model = "anthropic:test"\n\n[paths]\nvoices_root = "{configured.as_posix()}"\n')

    settings = load_settings()

    assert settings.model == "anthropic:test"
    assert settings.voices_root == configured


def test_partial_toml_preserves_path_default() -> None:
    _write_config('model = "anthropic:test"\n')

    settings = load_settings()

    assert settings.model == "anthropic:test"
    assert settings.voices_root == default_voices_root()


# ---------------------------------------------------------------------------
# Strict schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("unknown = true\n", "unknown"),
        ("[paths]\nunknown = true\n", "unknown"),
        ("model = 7\n", "model"),
        ("[paths]\nvoices_root = 7\n", "voices_root"),
        ('[paths]\nvoices_root = ""\n', "must not be empty"),
        ('[paths]\nvoices_root = "relative/voices"\n', "must be an absolute path"),
    ],
)
def test_invalid_schema_reports_config_path(text: str, expected: str) -> None:
    path = _write_config(text)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    assert str(path) in str(caught.value)
    assert expected in str(caught.value)


def test_invalid_toml_reports_config_path() -> None:
    path = _write_config('model = "unterminated\n')

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    assert str(path) in str(caught.value)


# ---------------------------------------------------------------------------
# Path expansion and environment-variable compatibility
# ---------------------------------------------------------------------------


def test_toml_voices_root_expands_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    _write_config('[paths]\nvoices_root = "~/voices"\n')

    assert load_settings().voices_root == home / "voices"


def test_flat_environment_root_maps_to_nested_setting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "environment-voices"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(root))

    assert load_settings().voices_root == root


@pytest.mark.parametrize("value", ["", "relative/voices", "../voices"])
def test_invalid_environment_root_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", value)

    assert load_settings().voices_root == default_voices_root()


# ---------------------------------------------------------------------------
# Precedence: env > toml > default; explicit args mask both
# ---------------------------------------------------------------------------


def test_environment_overrides_toml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    toml_root = tmp_path / "toml"
    env_root = tmp_path / "environment"
    _write_config(f'model = "anthropic:toml"\n\n[paths]\nvoices_root = "{toml_root.as_posix()}"\n')
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:environment")
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(env_root))

    settings = load_settings()

    assert settings.model == "anthropic:environment"
    assert settings.voices_root == env_root


def test_explicit_values_override_environment_and_toml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    explicit_root = tmp_path / "explicit"
    _write_config('model = "anthropic:toml"\n')
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:environment")
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "environment"))

    settings = load_settings(
        model="anthropic:explicit",
        voices_root=explicit_root,
    )

    assert settings.model == "anthropic:explicit"
    assert settings.voices_root == explicit_root


def test_explicit_model_does_not_mask_environment_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_root = tmp_path / "environment"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(env_root))

    settings = load_settings(model="anthropic:explicit")

    assert settings.model == "anthropic:explicit"
    assert settings.voices_root == env_root


def test_explicit_root_does_not_mask_environment_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:environment")

    settings = load_settings(voices_root=tmp_path / "explicit")

    assert settings.model == "anthropic:environment"
    assert settings.voices_root == tmp_path / "explicit"


# ---------------------------------------------------------------------------
# Public model types exist (frozen import check)
# ---------------------------------------------------------------------------


def test_paths_settings_forbids_unknown_keys() -> None:
    with pytest.raises(Exception):
        PathsSettings(unknown_field=True)  # type: ignore[call-arg]


def test_prose_craft_settings_default_model() -> None:
    settings = ProseCraftSettings()
    assert settings.model == DEFAULT_MODEL
