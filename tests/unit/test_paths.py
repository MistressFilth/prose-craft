"""Tests for prose_craft.paths — prose-craft's directory layout."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from prose_craft import paths

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX modes only")

_ALL_VARS = (
    "PROSE_CRAFT_VOICES_ROOT",
    "PROSE_CRAFT_XDG_DATA_HOME",
    "PROSE_CRAFT_XDG_CONFIG_HOME",
    "PROSE_CRAFT_XDG_CACHE_HOME",
    "PROSE_CRAFT_XDG_STATE_HOME",
    "PROSE_CRAFT_XDG_RUNTIME_DIR",
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR",
)


@pytest.fixture(autouse=True)
def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from a known-empty variable set."""
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# Application directories
# ---------------------------------------------------------------------------


def test_app_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert paths.app_data_dir() == tmp_path / "data" / "prose-craft"


def test_app_state_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert paths.app_state_dir() == tmp_path / "state" / "prose-craft"


def test_app_data_dir_is_not_created(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Pure computation; write_voice creates what it needs."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert not paths.app_data_dir().exists()


# ---------------------------------------------------------------------------
# Voices root
# ---------------------------------------------------------------------------


def test_voices_root_composes_from_data_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert paths.voices_root() == tmp_path / "data" / "prose-craft" / "voices"


def test_voices_root_honors_direct_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The direct override names a directory outright, suffix and all."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "elsewhere"))
    assert paths.voices_root() == tmp_path / "elsewhere"


def test_voices_root_override_beats_prose_craft_xdg_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "elsewhere"))
    assert paths.voices_root() == tmp_path / "elsewhere"


@pytest.mark.parametrize("value", ["relative/voices", "../up", ""])
def test_voices_root_ignores_invalid_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", value)
    assert paths.voices_root() == tmp_path / "data" / "prose-craft" / "voices"


# ---------------------------------------------------------------------------
# Composer state
# ---------------------------------------------------------------------------


def test_composer_state_dir_composes_from_state_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    assert paths.composer_state_dir() == tmp_path / "state" / "prose-craft" / "composer-state"


def test_composer_state_dir_is_outside_the_voices_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The invariant that holds on every platform.

    On macOS and Windows the data and state roots are the same
    directory, so composer-state is a *sibling* of voices/ rather than
    living under a different root. Asserting "outside the data root"
    would fail on two of three platforms; what actually matters is that
    list_voices() — which globs <voices_root>/*/voice.md — can never
    see it.
    """
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    composer = paths.composer_state_dir()
    voices = paths.voices_root()
    assert voices not in composer.parents
    assert composer != voices


def test_composer_state_dir_outside_voices_when_roots_coincide(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Force the macOS/Windows shape explicitly: one root for both."""
    shared = str(tmp_path / "shared")
    monkeypatch.setenv("XDG_DATA_HOME", shared)
    monkeypatch.setenv("XDG_STATE_HOME", shared)
    composer = paths.composer_state_dir()
    voices = paths.voices_root()
    assert voices not in composer.parents
    assert composer.parent == voices.parent


# ---------------------------------------------------------------------------
# Runtime directory
# ---------------------------------------------------------------------------


def test_app_runtime_dir_uses_runtime_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    assert paths.app_runtime_dir() == tmp_path / "run" / "prose-craft"


def test_app_runtime_dir_is_created(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    assert paths.app_runtime_dir().is_dir()


@posix_only
def test_app_runtime_dir_is_0700_on_posix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    created = paths.app_runtime_dir()
    assert stat.S_IMODE(created.stat().st_mode) == 0o700


@posix_only
def test_app_runtime_dir_tightens_a_loose_existing_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The mode is enforced on every call, so it is self-healing."""
    runtime = tmp_path / "run"
    loose = runtime / "prose-craft"
    loose.mkdir(parents=True)
    loose.chmod(0o777)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    created = paths.app_runtime_dir()
    assert stat.S_IMODE(created.stat().st_mode) == 0o700


def test_app_runtime_dir_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    assert paths.app_runtime_dir() == paths.app_runtime_dir()


def test_scratch_dir_created_under_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    scratch = paths.scratch_dir()
    assert scratch == tmp_path / "run" / "prose-craft" / "scratch"
    assert scratch.is_dir()


def test_app_runtime_dir_falls_back_when_runtime_root_unusable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An advertised-but-unusable runtime root must not break the app.

    WSL, containers, cron, and ssh sessions without a login session all
    export XDG_RUNTIME_DIR without creating it. The specification
    sanctions a replacement directory rather than a hard failure.
    """
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(blocker / "run"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    resolved = paths.app_runtime_dir()

    assert resolved == tmp_path / "state" / "prose-craft" / "run"
    assert resolved.is_dir()


def test_scratch_dir_uses_the_fallback_too(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(blocker / "run"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    scratch = paths.scratch_dir()

    assert scratch == tmp_path / "state" / "prose-craft" / "run" / "scratch"
    assert scratch.is_dir()
