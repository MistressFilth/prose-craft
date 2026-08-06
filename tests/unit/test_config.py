"""Tests for prose_craft.config."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from os import PathLike
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib as _tomllib
else:  # pragma: no cover - 3.10 is the lowest supported interpreter in CI
    import tomli as _tomllib

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
# JSON-as-TOML string round-trip: ``json.dumps`` produces a JSON string that
# is also a valid TOML basic string for every interesting input we can
# think of. These tests guard against a regression where someone "fixes"
# the serializer with a TOML-specific escaper that drifts from JSON
# semantics (e.g. choosing a TOML literal ``'...'`` and forgetting that
# TOML literals do not allow newlines).
# ---------------------------------------------------------------------------


def _round_trip(model: str, voices_root: Path) -> tuple[str, Path]:
    """Serialize ``(model, voices_root)`` then parse the result back.

    Returns ``(parsed_model, parsed_voices_root)`` so a test can assert
    on both fields independently. The test fixture points
    :func:`config_file` at a per-test ``tmp_path``, so writing the
    serialized blob there exercises the production code path end to end.
    """
    text = serialize_config(model, voices_root)
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    settings = load_settings()
    return settings.model, settings.voices_root


def test_serialize_config_round_trips_windows_backslash_path(tmp_path: Path) -> None:
    """A Windows-style path survives the round-trip via ``json.dumps``.

    JSON and TOML agree that ``\\\\`` decodes to a single backslash, so a
    string produced by ``json.dumps`` is also a valid TOML basic string
    for this case. We parse the serialized blob directly with
    :mod:`tomllib` so the test is independent of :func:`PathsSettings`
    rejecting the non-Linux-absolute path.
    """
    windows_path = "C:\\Users\\Deirdre\\AppData\\Roaming\\prose-craft\\voices"
    text = serialize_config("anthropic:test", Path(windows_path))

    parsed = _tomllib.loads(text)

    assert parsed["model"] == "anthropic:test"
    assert parsed["paths"]["voices_root"] == windows_path


def test_serialize_config_round_trips_quote_in_model(tmp_path: Path) -> None:
    """A double-quote inside the model string is escaped to ``\\"``.

    Both JSON and TOML use the same ``\\"`` escape for the embedded
    delimiter; ``json.dumps`` produces it directly.
    """
    quoted = 'anthropic:"special"'

    model, _ = _round_trip(quoted, tmp_path / "voices")

    assert model == quoted


def test_serialize_config_round_trips_unicode_model(tmp_path: Path) -> None:
    """Non-ASCII letters and accented characters survive the round-trip."""
    model, _ = _round_trip("anthropic:région-1", tmp_path / "voices")

    assert model == "anthropic:région-1"


def test_serialize_config_round_trips_emoji_model(tmp_path: Path) -> None:
    """Emoji (U+1F389 and family) survive the round-trip.

    Regression: ``json.dumps`` defaults to ``ensure_ascii=True`` and emits
    the surrogate pair ``\\uD83C\\uDF89``; Python's ``tomllib`` rejects
    lone surrogates in TOML basic strings, so an emoji-laden config
    written by the production serializer would fail to parse. Switching
    to ``ensure_ascii=False`` keeps the literal UTF-8 bytes, which TOML
    accepts verbatim.
    """
    model, _ = _round_trip("anthropic:🎉-release", tmp_path / "voices")

    assert model == "anthropic:🎉-release"


def test_serialize_config_round_trips_control_characters(tmp_path: Path) -> None:
    """Tab and newline characters survive the round-trip via JSON escapes.

    JSON escapes ``\\t`` and ``\\n``; TOML applies the same escapes, so
    a ``json.dumps``-produced string decodes back to the original code
    points.
    """
    model, _ = _round_trip("anthropic:line1\tcol2\nline2", tmp_path / "voices")

    assert model == "anthropic:line1\tcol2\nline2"


def test_serialize_config_round_trips_path_with_unicode(tmp_path: Path) -> None:
    """Unicode in the voices-root path round-trips correctly."""
    path = tmp_path / "données" / "voix"

    model, voices_root = _round_trip("anthropic:test", path)

    assert model == "anthropic:test"
    assert voices_root == path


def test_serialize_config_round_trips_mixed_separator_path(tmp_path: Path) -> None:
    """A path with mixed forward and back slashes parses as a TOML string.

    We parse the serialized blob directly with :mod:`tomllib` so the test
    is independent of :func:`PathsSettings` rejecting the
    non-Linux-absolute path. The expected value reflects whatever form
    the platform's ``Path.__str__`` normalizes to — Windows's
    ``WindowsPath`` collapses forward slashes to backslashes, so we read
    the post-round-trip value and assert it survives without crashing
    rather than pinning an exact string that would break on the other
    platform.
    """
    weird = "C:/Users\\Deirdre/voices"
    text = serialize_config("anthropic:test", Path(weird))

    parsed = _tomllib.loads(text)

    assert parsed["model"] == "anthropic:test"
    # Both forward and back slashes are preserved in the TOML string on
    # every platform; the serializer escapes each backslash so TOML can
    # decode it. The only platform difference is whether
    # ``WindowsPath.__str__`` collapses forward slashes to backslashes
    # before the round-trip begins.
    expected_root = str(Path(weird))
    assert parsed["paths"]["voices_root"] == expected_root
    # And the parser must have produced a string containing at least
    # one of the two separator characters we wrote.
    assert "\\" in parsed["paths"]["voices_root"] or "/" in parsed["paths"]["voices_root"]


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
        ('model = ""\n', "model must not be empty"),
        ('model = "   "\n', "model must not be empty"),
        ('model = "\\t\\n  "\n', "model must not be empty"),
    ],
)
def test_invalid_schema_reports_config_path(text: str, expected: str) -> None:
    path = _write_config(text)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    assert str(path) in str(caught.value)
    assert expected in str(caught.value)


@pytest.mark.parametrize("value", ["", "   ", "\t\n  "])
def test_empty_environment_model_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """``PROSE_CRAFT_MODEL=""`` is a hard configuration error.

    The schema treats an unset, empty, or whitespace-only model as a
    violation because every downstream call assumes a real model
    identifier; falling back to the default would silently mask the
    misconfiguration and let a user wonder why their override is being
    ignored.
    """
    monkeypatch.setenv("PROSE_CRAFT_MODEL", value)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    assert str(config_file()) in str(caught.value)
    assert "model must not be empty" in str(caught.value)


@pytest.mark.parametrize("value", ["", "   ", "\t\n  "])
def test_empty_explicit_model_raises_configuration_error(value: str) -> None:
    """An explicit ``load_settings(model="")`` is a hard configuration error.

    None means "leave this field to the next source down"; an empty
    string is an actual override attempt and the schema must reject it
    for the same reason as the environment and TOML sources do.
    """
    with pytest.raises(ConfigurationError) as caught:
        load_settings(model=value)

    assert str(config_file()) in str(caught.value)
    assert "model must not be empty" in str(caught.value)


def test_valid_model_with_whitespace_inside_is_preserved(tmp_path: Path) -> None:
    """Whitespace **inside** a model identifier must be preserved.

    The validator strips before testing emptiness; it does not strip the
    stored value. A model like ``" openai: gpt-5  with spaces "`` is a
    hypothetical but legal choice and must round-trip through TOML
    verbatim so the user sees exactly what they configured.
    """
    settings = ProseCraftSettings(model="anthropic: model with spaces")
    assert settings.model == "anthropic: model with spaces"

    parsed_model, _ = _round_trip("anthropic: model with spaces", tmp_path / "voices")
    assert parsed_model == "anthropic: model with spaces"


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


def test_initialize_mkdir_failure_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A read-only parent directory must surface as a clean ConfigurationError.

    Previously ``target.parent.mkdir`` ran before the ``try/except`` block
    so a permission error fell out as a bare ``PermissionError`` and the
    CLI handler would print a traceback. The OSError boundary now wraps
    both ``mkdir`` and ``mkstemp`` so the message matches the failure mode
    and the CLI can exit 2 cleanly.
    """
    target = config_file()

    def fail_mkdir(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(13, "Permission denied", str(target.parent))

    monkeypatch.setattr(Path, "mkdir", fail_mkdir)

    with pytest.raises(ConfigurationError) as caught:
        initialize_config()

    assert "could not write" in str(caught.value)
    assert str(target) in str(caught.value)
    assert not target.exists()
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []


def test_initialize_mkstemp_failure_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ENOSPC at ``mkstemp`` must surface as a clean ConfigurationError.

    Root cause: ``tempfile.mkstemp`` ran on the line *before* the
    ``try`` block; an OSError raised there not only escaped the
    boundary as a bare ``OSError`` but also crashed the ``finally``
    clause on the next line because ``temporary`` was never bound —
    ``NameError: free variable 'temporary' referenced before assignment``
    masked the real failure with a confusing secondary traceback. The
    fix binds ``fd`` and ``temporary`` to safe defaults before the try
    and wraps the creation calls in their own OSError boundary so the
    user sees a single ``ConfigurationError(kind="could not write")``
    line instead of an OSError plus a NameError plus a traceback.
    """
    target = config_file()

    def fail_mkstemp(**_kwargs: object) -> tuple[int, str]:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(tempfile, "mkstemp", fail_mkstemp)

    with pytest.raises(ConfigurationError) as caught:
        initialize_config()

    assert "could not write" in str(caught.value)
    assert "No space left on device" in str(caught.value)
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
