"""Tests for prose_craft.config."""

from __future__ import annotations

import json
import os
from os import PathLike
from pathlib import Path

import pytest

from prose_craft.config import (
    DEFAULT_MODEL,
    ConfigAlreadyExists,
    ConfigurationError,
    PathsSettings,
    ProseCraftSettings,
    config_file,
    get_model,
    initialize_config,
    load_settings,
    serialize_config,
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
# Deterministic serialization (Task 4)
# ---------------------------------------------------------------------------


def test_serialize_config_is_deterministic(tmp_path: Path) -> None:
    voices = tmp_path / "voices"
    # On Linux str(path) and as_posix() agree; on Windows str(path) preserves
    # native backslashes which json.dumps escapes safely. We assert against
    # the JSON-escaped form so the test reads the same way on every platform.
    voices_literal = json.dumps(str(voices))
    assert serialize_config("anthropic:test", voices) == (
        f'model = "anthropic:test"\n\n[paths]\nvoices_root = {voices_literal}\n'
    )


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
# Atomic initialization (Task 4)
# ---------------------------------------------------------------------------


def test_initialize_writes_built_in_and_xdg_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_MODEL", "anthropic:environment")
    monkeypatch.setenv(
        "PROSE_CRAFT_VOICES_ROOT",
        str(tmp_path / "environment-voices"),
    )

    created = initialize_config()
    text = created.read_text(encoding="utf-8")

    assert f'model = "{DEFAULT_MODEL}"' in text
    assert "anthropic:environment" not in text
    assert "environment-voices" not in text
    # env overrides toml, so unset before parsing the generated file to prove
    # round-trip validity of the defaults we just wrote.
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)
    monkeypatch.delenv("PROSE_CRAFT_MODEL", raising=False)
    assert load_settings().voices_root == default_voices_root()


def test_initialize_refuses_existing_file_without_parsing() -> None:
    path = config_file()
    path.parent.mkdir(parents=True)
    original = b"\xffnot valid toml"
    path.write_bytes(original)

    with pytest.raises(ConfigAlreadyExists):
        initialize_config()

    assert path.read_bytes() == original


def test_initialize_cleans_temporary_file_after_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = config_file()

    def collide(source: PathLike[str], destination: PathLike[str]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("winner = true\n", encoding="utf-8")
        raise FileExistsError(destination)

    monkeypatch.setattr(os, "link", collide)

    with pytest.raises(ConfigAlreadyExists):
        initialize_config()

    assert target.read_text(encoding="utf-8") == "winner = true\n"
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []


def test_initialize_cleans_temporary_file_after_link_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = config_file()

    def fail_link(source: PathLike[str], destination: PathLike[str]) -> None:
        raise OSError("link failed")

    monkeypatch.setattr(os, "link", fail_link)

    with pytest.raises(ConfigurationError, match="link failed"):
        initialize_config()

    assert not target.exists()
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []


def test_initialize_cleans_temporary_file_after_fsync_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = config_file()

    def fail_fsync(descriptor: int) -> None:
        raise OSError("sync failed")

    monkeypatch.setattr(os, "fsync", fail_fsync)

    with pytest.raises(ConfigurationError, match="sync failed"):
        initialize_config()

    assert not target.exists()
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []


# ---------------------------------------------------------------------------
# Public model types exist (frozen import check)
# ---------------------------------------------------------------------------


def test_paths_settings_forbids_unknown_keys() -> None:
    with pytest.raises(Exception):
        PathsSettings(unknown_field=True)  # type: ignore[call-arg]


def test_prose_craft_settings_default_model() -> None:
    settings = ProseCraftSettings()
    assert settings.model == DEFAULT_MODEL
