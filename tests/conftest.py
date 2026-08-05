"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

_CLEARED_VARS = (
    "PROSE_CRAFT_MODEL",
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

_ROLE_VARS = {
    "XDG_DATA_HOME": "data",
    "XDG_CONFIG_HOME": "config",
    "XDG_CACHE_HOME": "cache",
    "XDG_STATE_HOME": "state",
    "XDG_RUNTIME_DIR": "runtime",
}


@pytest.fixture(autouse=True)
def _isolated_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point every resolved root at this test's tmp_path.

    Clears the developer's ambient values first so an exported
    ``PROSE_CRAFT_VOICES_ROOT`` cannot reach a test, then redirects the
    five roots into ``tmp_path/.xdg/<role>``.

    Redirecting via ``XDG_*`` works on all three platforms because the
    resolution chain honors those variables everywhere — the same
    property this design gives macOS and Windows users, exercised on
    every run.

    The directories are NOT created: many tests assert on the exact
    contents of ``tmp_path``, and the resolvers create what they need
    on demand.
    """
    for var in _CLEARED_VARS:
        monkeypatch.delenv(var, raising=False)
    for var, role in _ROLE_VARS.items():
        monkeypatch.setenv(var, str(tmp_path / ".xdg" / role))
    # Path.home() reads HOME on POSIX and USERPROFILE on Windows.
    # Pin both, or a resolver that falls through to a native default
    # escapes into the developer's real home directory.
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


@pytest.fixture
def tmp_voices_root(tmp_path: Path) -> Path:
    """An isolated voices root for the duration of one test."""
    root = tmp_path / "voices"
    root.mkdir()
    return root
