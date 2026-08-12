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

The voices root honors ``PROSE_CRAFT_VOICES_ROOT`` and the XDG config
chain through :mod:`prose_craft.config`; this module only owns the
XDG-derived default. ``--voices-root`` is the per-invocation
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
    "default_voices_root",
    "scratch_dir",
]


def app_data_dir() -> Path:
    """``<data_root>/prose-craft``. Not created."""
    return xdg.data_home() / APP


def app_state_dir() -> Path:
    """``<state_root>/prose-craft``. Not created."""
    return xdg.state_home() / APP


def app_runtime_dir() -> Path:
    """``<runtime_root>/prose-craft``, created.

    If the advertised runtime root cannot be used, fall back to
    ``<state_root>/prose-craft/run``. Environments routinely export
    ``XDG_RUNTIME_DIR`` without creating it — WSL, containers, cron, and
    ssh sessions with no login session all do — and the specification
    sanctions a replacement directory rather than a hard failure.

    Mode ``0700`` is applied on POSIX, where the specification asks for
    it, and is re-applied on every call so a loosened directory heals
    itself. It is skipped on Windows: ``os.chmod`` there honors only the
    read-only bit, so calling it would imply a guarantee that does not
    hold.
    """
    path = xdg.runtime_dir() / APP
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = xdg.state_home() / APP / "run"
        path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        _apply_owner_only_dacl(path)
    else:
        path.chmod(0o700)
    return path


def _apply_owner_only_dacl(path: Path) -> None:
    """Restrict ``path`` on Windows so only the current user can access it.

    POSIX has ``chmod(0o700)``; Windows honors only the read-only bit
    on ``os.chmod``, so we apply an explicit DACL via win32security
    instead. The runtime directory is created with this ACL so child
    dirs (``scratch/``) and files inherit the restriction.

    Raises :class:`RuntimeError` if ``pywin32`` is not installed.
    Failure to apply the ACL raises rather than silently leaving the
    directory world-readable.
    """
    try:
        import win32security  # type: ignore[import-not-found]  # ty: ignore[unresolved-import]
        from win32security import (  # type: ignore[import-not-found]  # ty: ignore[unresolved-import]
            CONTAINER_INHERIT_ACE,
            DACL_SECURITY_INFORMATION,
            INHERIT_ONLY_ACE,
            OBJECT_INHERIT_ACE,
            PROTECTED_DACL_SECURITY_INFORMATION,
            SE_FILE_OBJECT,
            ACL,
            SetSecurityInfo,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Windows runtime ACL requires pywin32; install with "
            "`uv pip install 'prose-craft[windows]'` or "
            "`pip install pywin32`"
        ) from exc

    user_sid, _, _ = win32security.LookupAccountName(None, win32security.GetUserName())
    everyone_sid = win32security.ConvertStringSidToSid("S-1-1-0")

    acl = ACL()
    # ACE 1: grant owner full control on the directory itself.
    acl.AddAccessAllowedAce(win32security.FILE_ALL_ACCESS, 0, user_sid)
    # ACE 2: grant owner full control on future children (inherit-only).
    acl.AddAccessAllowedAce(
        win32security.FILE_ALL_ACCESS,
        OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE | INHERIT_ONLY_ACE,
        user_sid,
    )
    # ACE 3: deny Everyone on the directory itself.
    acl.AddAccessDeniedAce(win32security.FILE_ALL_ACCESS, 0, everyone_sid)
    # ACE 4: deny Everyone on future children (inherit-only).
    acl.AddAccessDeniedAce(
        win32security.FILE_ALL_ACCESS,
        OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE | INHERIT_ONLY_ACE,
        everyone_sid,
    )
    SetSecurityInfo(
        str(path),
        SE_FILE_OBJECT,
        DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION,
        None,
        None,
        acl,
        None,
    )


def default_voices_root() -> Path:
    """Return the XDG-derived default voice profile store without creating it."""
    return app_data_dir() / "voices"


def composer_state_dir() -> Path:
    """The composer agent's ``FileStore`` root. Not created."""
    return app_state_dir() / "composer-state"


def scratch_dir() -> Path:
    """Short-lived working files, created on demand."""
    path = app_runtime_dir() / "scratch"
    path.mkdir(parents=True, exist_ok=True)
    return path
