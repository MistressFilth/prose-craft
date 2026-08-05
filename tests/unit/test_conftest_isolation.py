"""The autouse isolation fixture must cover every root, on every OS."""

from __future__ import annotations

import os
from pathlib import Path

from prose_craft import paths, xdg


def test_roots_are_redirected_into_tmp_path(tmp_path: Path) -> None:
    """Every resolved root sits under this test's tmp_path."""
    for resolver in (
        xdg.data_home,
        xdg.config_home,
        xdg.cache_home,
        xdg.state_home,
        xdg.runtime_dir,
    ):
        assert str(resolver()).startswith(str(tmp_path)), resolver.__name__


def test_voices_root_is_redirected(tmp_path: Path) -> None:
    assert str(paths.voices_root()).startswith(str(tmp_path))


def test_ambient_values_are_cleared() -> None:
    """A developer's exported values must not leak into tests."""
    assert "PROSE_CRAFT_VOICES_ROOT" not in os.environ
    assert "PROSE_CRAFT_MODEL" not in os.environ
    for role in ("DATA_HOME", "CONFIG_HOME", "CACHE_HOME", "STATE_HOME", "RUNTIME_DIR"):
        assert f"PROSE_CRAFT_XDG_{role}" not in os.environ


def test_isolation_leaves_tmp_path_clean(tmp_path: Path) -> None:
    """The fixture must not create directories a test might assert over.

    Many tests assert on the exact contents of tmp_path; the fixture
    points the roots at a hidden subdirectory and creates nothing.
    """
    assert list(tmp_path.iterdir()) == []


def test_home_is_redirected(tmp_path: Path) -> None:
    """Path.home() must not reach the developer's real home.

    On Windows Path.home() reads USERPROFILE and ignores HOME, so the
    fixture pins both. Without this, any resolver falling through to a
    native default escapes the sandbox.
    """
    assert Path.home() == tmp_path / "home"
