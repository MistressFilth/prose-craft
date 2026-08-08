"""Tests for prose_craft.xdg — cross-platform directory resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from prose_craft import xdg

_ALL_VARS = (
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

_ROLES = (
    ("data_home", "XDG_DATA_HOME"),
    ("config_home", "XDG_CONFIG_HOME"),
    ("cache_home", "XDG_CACHE_HOME"),
    ("state_home", "XDG_STATE_HOME"),
    ("runtime_dir", "XDG_RUNTIME_DIR"),
)


@pytest.fixture(autouse=True)
def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from a known-empty variable set."""
    for var in _ALL_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# env_path: the validity rule
# ---------------------------------------------------------------------------


def test_env_path_returns_none_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOME_VAR", raising=False)
    assert xdg.env_path("SOME_VAR") is None


def test_env_path_returns_none_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOME_VAR", "")
    assert xdg.env_path("SOME_VAR") is None


@pytest.mark.parametrize("value", ["relative/path", "../up", "./here", "bare"])
def test_env_path_rejects_relative(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """The specification requires a relative value be treated as invalid."""
    monkeypatch.setenv("SOME_VAR", value)
    assert xdg.env_path("SOME_VAR") is None


def test_env_path_accepts_absolute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SOME_VAR", str(tmp_path / "abs"))
    assert xdg.env_path("SOME_VAR") == tmp_path / "abs"


def test_env_path_expands_tilde(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Path.home() reads HOME on POSIX and USERPROFILE on Windows."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("SOME_VAR", "~/inside")
    assert xdg.env_path("SOME_VAR") == tmp_path / "inside"


# ---------------------------------------------------------------------------
# Precedence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("resolver", "spec_var"), _ROLES)
def test_override_beats_spec_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resolver: str, spec_var: str
) -> None:
    monkeypatch.setenv(f"PROSE_CRAFT_{spec_var}", str(tmp_path / "override"))
    monkeypatch.setenv(spec_var, str(tmp_path / "spec"))
    assert getattr(xdg, resolver)() == tmp_path / "override"


@pytest.mark.parametrize(("resolver", "spec_var"), _ROLES)
def test_spec_var_honored_on_every_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resolver: str, spec_var: str
) -> None:
    """XDG variables are the escape hatch on macOS and Windows too."""
    monkeypatch.setenv(spec_var, str(tmp_path / "spec"))
    assert getattr(xdg, resolver)() == tmp_path / "spec"


def test_invalid_override_does_not_shadow_spec_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PROSE_CRAFT_XDG_DATA_HOME", "relative")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "spec"))
    assert xdg.data_home() == tmp_path / "spec"


def test_falls_back_to_platformdirs() -> None:
    """With no variables set, the native default is used."""
    import platformdirs

    assert xdg.data_home() == Path(platformdirs.user_data_dir())


# ---------------------------------------------------------------------------
# The sanitized-environment guard
# ---------------------------------------------------------------------------


def test_relative_spec_var_does_not_leak_through_platformdirs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The critical regression.

    platformdirs reads XDG_DATA_HOME itself on Linux and does not apply
    the validity rule. Without the sanitized-environment guard, a
    relative value rejected by env_path() is honored by platformdirs a
    moment later and the violation re-enters.
    """
    monkeypatch.setenv("XDG_DATA_HOME", "relative/leak")
    resolved = xdg.data_home()
    assert resolved.is_absolute()
    assert "relative/leak" not in resolved.as_posix()


def test_relative_runtime_dir_does_not_leak_through_platformdirs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """platformdirs' macOS backend reads XDG_RUNTIME_DIR, so the guard
    is not a Linux-only concern."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", "relative/leak")
    resolved = xdg.runtime_dir()
    assert resolved.is_absolute()
    assert "relative/leak" not in resolved.as_posix()


def test_sanitized_env_restores_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard must not leave the process environment mutated."""
    monkeypatch.setenv("XDG_DATA_HOME", "relative/leak")
    xdg.data_home()
    assert os.environ["XDG_DATA_HOME"] == "relative/leak"


def test_sanitized_env_leaves_valid_values_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", "relative/leak")
    xdg.data_home()
    assert os.environ["XDG_CACHE_HOME"] == str(tmp_path / "cache")
    assert os.environ["XDG_DATA_HOME"] == "relative/leak"


# ---------------------------------------------------------------------------
# Module-wide invariants
# ---------------------------------------------------------------------------


def test_all_roots_are_absolute() -> None:
    for resolver, _ in _ROLES:
        assert getattr(xdg, resolver)().is_absolute(), resolver


def test_module_knows_no_application_name() -> None:
    """Namespacing belongs to paths.py."""
    for resolver, _ in _ROLES:
        assert "prose-craft" not in str(getattr(xdg, resolver)()), resolver


# ---------------------------------------------------------------------------
# data_dirs: $XDG_DATA_DIRS resolver
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-style /a, /b, /c paths are not absolute on Windows",
)
class TestDataDirs:
    def test_returns_empty_when_unset(self, monkeypatch):
        monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
        assert xdg.data_dirs() == [Path("/usr/local/share"), Path("/usr/share")]

    def test_splits_on_pathsep(self, monkeypatch):
        monkeypatch.setenv("XDG_DATA_DIRS", os.pathsep.join(["/a", "/b", "/c"]))
        assert xdg.data_dirs() == [Path("/a"), Path("/b"), Path("/c")]

    def test_skips_empty_entries(self, monkeypatch):
        monkeypatch.setenv("XDG_DATA_DIRS", os.pathsep.join(["/a", "", "/b", ""]))
        assert xdg.data_dirs() == [Path("/a"), Path("/b")]

    def test_skips_relative_entries(self, monkeypatch):
        monkeypatch.setenv("XDG_DATA_DIRS", os.pathsep.join(["/a", "relative", "../up"]))
        assert xdg.data_dirs() == [Path("/a")]

    def test_returns_default_when_only_invalid(self, monkeypatch):
        monkeypatch.setenv("XDG_DATA_DIRS", "relative:../up")
        assert xdg.data_dirs() == [Path("/usr/local/share"), Path("/usr/share")]


def test_config_dirs_default_when_unset(monkeypatch):
    """config_dirs() returns ["/etc/xdg"] when XDG_CONFIG_DIRS is unset."""
    from prose_craft import xdg

    monkeypatch.delenv("XDG_CONFIG_DIRS", raising=False)
    assert xdg.config_dirs() == [Path("/etc/xdg")]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-style /a, /b, /c paths are not absolute on Windows",
)
def test_config_dirs_parses_multiple_entries(monkeypatch):
    """config_dirs() splits on os.pathsep and returns one Path per entry."""
    from prose_craft import xdg

    monkeypatch.setenv("XDG_CONFIG_DIRS", "/etc/xdg/prose:/opt/share/prose-craft")
    assert xdg.config_dirs() == [Path("/etc/xdg/prose"), Path("/opt/share/prose-craft")]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX-style /a, /b, /c paths are not absolute on Windows",
)
def test_config_dirs_drops_invalid_entries(monkeypatch):
    """config_dirs() drops relative or empty entries per spec validity rule."""
    from prose_craft import xdg

    monkeypatch.setenv("XDG_CONFIG_DIRS", "/etc/xdg/prose:relative/path::/opt/share")
    assert xdg.config_dirs() == [Path("/etc/xdg/prose"), Path("/opt/share")]


def test_config_dirs_empty_after_drop_falls_back_to_default(monkeypatch):
    """If all entries are invalid, fall back to the spec default."""
    from prose_craft import xdg

    monkeypatch.setenv("XDG_CONFIG_DIRS", "relative/path::")
    assert xdg.config_dirs() == [Path("/etc/xdg")]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows' Path.expanduser() reads USERPROFILE, not HOME",
)
def test_env_path_for_config_dirs_expands_user(monkeypatch, tmp_path):
    """Tilde-expansion works for entries that begin with ~/."""
    from prose_craft import xdg

    monkeypatch.setenv("HOME", str(tmp_path))
    assert xdg.env_path_for_config_dirs("~/prose-config") == tmp_path / "prose-config"
