"""Voice profile naming and path construction.

Root resolution lives in :mod:`prose_craft.config`; this module owns
only the name grammar and the ``<root>/<name>/voice.md`` layout.
"""

from __future__ import annotations

import re
from pathlib import Path

_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*$")


class VoiceNameError(ValueError):
    """Raised when a voice name fails validation."""


def voice_path(name: str, *, root: Path | None = None) -> Path:
    """Return ``<root>/<name>/voice.md`` for a valid voice name.

    Voice names must match ``^[a-zA-Z][a-zA-Z0-9-]*$``. Invalid names,
    including path-traversal attempts, raise :class:`VoiceNameError`.
    A ``root`` of ``None`` resolves to the configured voices root via
    :func:`prose_craft.config.load_settings` (deferred import to avoid
    a module cycle).
    """
    if _NAME_RE.fullmatch(name) is None:
        raise VoiceNameError(f"invalid voice name {name!r}: must match [a-zA-Z][a-zA-Z0-9-]*")
    if root is None:
        from prose_craft.config import load_settings

        root = load_settings().voices_root
    return root / name / "voice.md"
