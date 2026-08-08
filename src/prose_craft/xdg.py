"""Cross-platform user-directory resolution.

Every root resolves through the same chain:

1. ``PROSE_CRAFT_XDG_<NAME>`` — this application's override
2. ``XDG_<NAME>`` — the freedesktop specification variable
3. The platform's native default, via :mod:`platformdirs`

On Linux the second and third links agree, so Linux follows the XDG
Base Directory Specification exactly. On macOS and Windows the native
default wins by default, and the XDG variables remain available as an
opt-in escape hatch that a native-only implementation would ignore.

A candidate that is unset, empty, or relative is skipped rather than
raising, per the specification: "If an implementation encounters a
relative path in any of these variables it should consider the path
invalid and ignore it."

This module returns bare roots and never handles the application name;
that is :mod:`prose_craft.paths`' responsibility.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import platformdirs

__all__ = [
    "cache_home",
    "config_home",
    "config_dirs",
    "env_path_for_config_dirs",
    "data_dirs",
    "data_home",
    "env_path",
    "runtime_dir",
    "state_home",
]

_OVERRIDE_PREFIX = "PROSE_CRAFT_"

_SPEC_VARS = (
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR",
)


def env_path(var: str) -> Path | None:
    """Return ``var`` as an absolute Path, or None if it is invalid.

    Invalid means unset, empty, or — after ``expanduser()`` — still
    relative. ``~/x`` is therefore accepted while ``../x`` is not.
    """
    raw = os.environ.get(var)
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return None
    return path


@contextmanager
def _sanitized_env() -> Iterator[None]:
    """Temporarily remove invalid ``XDG_*`` values from the environment.

    ``platformdirs`` reads some ``XDG_*`` variables itself — all of them
    on Linux, ``XDG_RUNTIME_DIR`` on macOS — and does not apply the
    specification's validity rule. Without this guard a relative
    ``XDG_DATA_HOME``, correctly rejected by :func:`env_path`, would be
    honored by ``platformdirs`` a moment later and the violation would
    re-enter through the delegation.

    The specification says an invalid value is to be *ignored*, which is
    to say treated as unset. That is exactly what this does. Valid
    values are left in place so the delegation still benefits from
    platformdirs' own handling where it exists.
    """
    removed: dict[str, str] = {}
    for var in _SPEC_VARS:
        raw = os.environ.get(var)
        if raw and env_path(var) is None:
            removed[var] = raw
            del os.environ[var]
    try:
        yield
    finally:
        os.environ.update(removed)


def _xdg_root(spec_var: str, native: Callable[[], str]) -> Path:
    """Resolve one root through the full precedence chain."""
    for var in (f"{_OVERRIDE_PREFIX}{spec_var}", spec_var):
        candidate = env_path(var)
        if candidate is not None:
            return candidate
    with _sanitized_env():
        return Path(native())


_DEFAULT_DATA_DIRS = (Path("/usr/local/share"), Path("/usr/share"))
_DEFAULT_CONFIG_DIRS = (Path("/etc/xdg"),)


def data_dirs() -> list[Path]:
    """System-wide data directories from ``$XDG_DATA_DIRS``.

    Splits on :data:`os.pathsep`, drops entries that are unset, empty,
    or relative (per :func:`env_path`'s validity rule), and falls back
    to the freedesktop-spec default ``["/usr/local/share", "/usr/share"]``
    when the environment yields no valid entries. Returns bare roots;
    callers append the application suffix.
    """
    raw = os.environ.get("XDG_DATA_DIRS")
    if raw:
        out: list[Path] = []
        for piece in raw.split(os.pathsep):
            candidate = env_path_for_data_dirs(piece)
            if candidate is not None:
                out.append(candidate)
        if out:
            return out
    return list(_DEFAULT_DATA_DIRS)


def env_path_for_data_dirs(raw: str) -> Path | None:
    """Validate one ``$XDG_DATA_DIRS`` entry. Mirrors :func:`env_path`."""
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return None
    return path


def config_dirs() -> list[Path]:
    """System-wide config directories from ``$XDG_CONFIG_DIRS``.

    Splits on :data:`os.pathsep`, drops entries that are unset, empty,
    or relative (per :func:`env_path_for_config_dirs`'s validity rule),
    and falls back to the freedesktop-spec default ``["/etc/xdg"]``
    when the environment yields no valid entries. Returns bare roots;
    callers append the application suffix.
    """
    raw = os.environ.get("XDG_CONFIG_DIRS")
    if raw:
        out: list[Path] = []
        for piece in raw.split(os.pathsep):
            candidate = env_path_for_config_dirs(piece)
            if candidate is not None:
                out.append(candidate)
        if out:
            return out
    return list(_DEFAULT_CONFIG_DIRS)


def env_path_for_config_dirs(raw: str) -> Path | None:
    """Validate one ``$XDG_CONFIG_DIRS`` entry. Mirrors the data variant."""
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        return None
    return path


def data_home() -> Path:
    """User-specific data files."""
    return _xdg_root("XDG_DATA_HOME", platformdirs.user_data_dir)


def config_home() -> Path:
    """User-specific configuration."""
    return _xdg_root("XDG_CONFIG_HOME", platformdirs.user_config_dir)


def cache_home() -> Path:
    """User-specific non-essential data."""
    return _xdg_root("XDG_CACHE_HOME", platformdirs.user_cache_dir)


def state_home() -> Path:
    """User-specific state that should persist between restarts.

    ``platformdirs`` returns the same directory as :func:`data_home` on
    macOS and Windows; only Linux separates them.
    """
    return _xdg_root("XDG_STATE_HOME", platformdirs.user_state_dir)


def runtime_dir() -> Path:
    """User-specific runtime and short-lived files."""
    return _xdg_root("XDG_RUNTIME_DIR", platformdirs.user_runtime_dir)
