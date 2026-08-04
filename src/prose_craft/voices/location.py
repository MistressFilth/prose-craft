"""XDG-compliant voice profile location."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path

_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*$")


class VoiceNameError(ValueError):
    """Raised when a voice name fails validation."""


def get_voices_root() -> Path:
    """Return the per-user global voice store.

    Resolution order:
      1. PROSE_CRAFT_VOICES_ROOT environment variable
      2. $XDG_DATA_HOME/prose-craft/voices
      3. Platform default:
         - macOS: $HOME/Library/Application Support/prose-craft/voices
         - other: $HOME/.local/share/prose-craft/voices
    """
    explicit = os.environ.get("PROSE_CRAFT_VOICES_ROOT")
    if explicit:
        return Path(explicit).resolve()

    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "prose-craft" / "voices"

    home = Path(os.environ.get("HOME", "."))
    if platform.system() == "Darwin":
        return home / "Library" / "Application Support" / "prose-craft" / "voices"
    return home / ".local" / "share" / "prose-craft" / "voices"


def get_bundled_voices_root() -> Path | None:
    """Return the read-only root for voices shipped with the wheel, or None.

    Looks for the ``../voices`` directory at the repository root — the
    bare-repo layout puts shipped voices one level up from each
    worktree. Returns ``None`` when the directory does not exist (e.g.
    in a packaged wheel install where the bundled voices were not
    force-included, or in a non-repository environment).

    Callers should treat a ``None`` return as "no shipped voices
    available" and continue with the user root alone.
    """
    # ``src/prose_craft/voices/location.py`` → ``src/prose_craft/voices``
    # → ``src/prose_craft`` → ``src`` → ``<repo_root>`` → ``<bare_root>`` → ``<bare_root>/voices``.
    here = Path(__file__).resolve()
    bare_root = here.parents[3].parent
    bundled = bare_root / "voices"
    if bundled.is_dir():
        return bundled
    return None


def voice_path(name: str, *, root: Path | None = None) -> Path:
    """Return ``<root>/<name>/voice.md`` for a valid voice name.

    Voice names must match ``^[a-zA-Z][a-zA-Z0-9-]*$``. Invalid names,
    including path-traversal attempts, raise :class:`VoiceNameError`.
    """
    if _NAME_RE.fullmatch(name) is None:
        raise VoiceNameError(f"invalid voice name {name!r}: must match [a-zA-Z][a-zA-Z0-9-]*")
    base = (root or get_voices_root()) / name
    return base / "voice.md"
