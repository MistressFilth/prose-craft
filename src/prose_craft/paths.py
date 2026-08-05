"""Prose-craft's directory layout, composed from resolved roots.

Every application directory is defined here and nowhere else. This is
the module the rest of the codebase imports; :mod:`prose_craft.xdg` is
an implementation detail behind it.

The layout, by role:

=========================  ============================================
Voice profiles (data)      ``<data_root>/prose-craft/voices/``
Composer memory (state)    ``<state_root>/prose-craft/composer-state/``
Draft scratch (runtime)    ``<runtime_root>/prose-craft/scratch/``
=========================  ============================================

Only Linux gives each role its own root. macOS folds config and state
into the data directory; Windows folds all four into ``%LOCALAPPDATA%``.
Where they coincide, ``voices/`` and ``composer-state/`` end up
siblings. That is native behavior and is fine: the point of separating
them was to keep agent memory out of the voice library, and
``list_voices()`` globs ``<voices_root>/*/voice.md``, which never
matches a sibling.

``PROSE_CRAFT_VOICES_ROOT`` is read here rather than in ``xdg`` because
it names an application directory outright, not a root. It wins over
the resolution chain; ``--voices-root`` is its per-invocation
equivalent.
"""

from __future__ import annotations

import os
from pathlib import Path

from prose_craft import xdg

APP = "prose-craft"

__all__ = [
    "APP",
    "app_data_dir",
    "app_runtime_dir",
    "app_state_dir",
    "composer_state_dir",
    "scratch_dir",
    "voices_root",
]


def app_data_dir() -> Path:
    """``<data_root>/prose-craft``. Not created."""
    return xdg.data_home() / APP


def app_state_dir() -> Path:
    """``<state_root>/prose-craft``. Not created."""
    return xdg.state_home() / APP


def app_runtime_dir() -> Path:
    """``<runtime_root>/prose-craft``, created.

    Mode ``0700`` is applied on POSIX, where the specification asks for
    it, and is re-applied on every call so a loosened directory heals
    itself. It is skipped on Windows: ``os.chmod`` there honors only the
    read-only bit, so calling it would imply a guarantee that does not
    hold.
    """
    path = xdg.runtime_dir() / APP
    path.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.chmod(0o700)
    return path


def voices_root() -> Path:
    """The voice profile store.

    ``PROSE_CRAFT_VOICES_ROOT`` if it names an absolute path, otherwise
    ``<data_root>/prose-craft/voices``. Not created; ``write_voice``
    creates it on demand.
    """
    explicit = xdg.env_path("PROSE_CRAFT_VOICES_ROOT")
    if explicit is not None:
        return explicit
    return app_data_dir() / "voices"


def composer_state_dir() -> Path:
    """The composer agent's ``FileStore`` root. Not created."""
    return app_state_dir() / "composer-state"


def scratch_dir() -> Path:
    """Short-lived working files, created on demand."""
    path = app_runtime_dir() / "scratch"
    path.mkdir(parents=True, exist_ok=True)
    return path
