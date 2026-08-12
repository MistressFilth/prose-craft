"""Voice profile naming and path construction.

Root resolution lives in :mod:`prose_craft.config`; this module owns
only the name grammar and the ``<root>/<name>/voice.md`` layout.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*$")


def _discover_project_root(cwd: Path | None = None) -> Path | None:
    """Walk from cwd toward filesystem root. Return the closest
    `<dir>/.prose-craft/voices/` real directory, or None.

    Refuses to ascend through a symlinked directory. Refuses a symlinked
    marker. Walks until `cur.parent == cur` (filesystem root reached).
    """
    start = cwd if cwd is not None else Path(os.getcwd())
    if not start.is_dir():
        return None
    cur = start
    while True:
        if cur.is_symlink():
            return None
        marker = cur / ".prose-craft" / "voices"
        if marker.is_dir() and not marker.is_symlink():
            return marker
        parent = cur.parent
        if parent == cur:
            return None  # filesystem root reached
        cur = parent


class VoiceNameError(ValueError):
    """Raised when a voice name fails validation."""


def voice_roots() -> list[Path]:
    """Voices roots in precedence order: user, project, then shared.

    The user root comes from :func:`prose_craft.config.load_settings`.
    The project root is discovered from the current working directory by
    :func:`_discover_project_root` — ``<dir>/.prose-craft/voices/`` at the
    closest ancestor that contains one. Shared roots are
    :func:`prose_craft.xdg.data_dirs` with the ``prose-craft/voices`` suffix
    appended.
    """
    from prose_craft.config import load_settings
    from prose_craft.xdg import data_dirs

    roots = [load_settings().voices_root]
    project = _discover_project_root()
    if project is not None:
        roots.append(project)
    roots.extend(d / "prose-craft" / "voices" for d in data_dirs())
    return roots


def voice_path(name: str, *, root: Path | None = None) -> Path:
    """Return the resolved path for ``name``.

    When ``root`` is given, return ``<root>/<name>/voice.md`` directly
    (single-root escape hatch, used by tests and explicit overrides).

    Otherwise walk :func:`voice_roots` in precedence order; the first
    root containing ``<name>/voice.md`` wins. Raises :class:`VoiceNameError`
    if the name itself is invalid; absence of the file is signaled by
    the caller (``read_voice`` raises :class:`VoiceProfileNotFound``).
    """
    if _NAME_RE.fullmatch(name) is None:
        raise VoiceNameError(f"invalid voice name {name!r}: must match [a-zA-Z][a-zA-Z0-9-]*")
    if root is not None:
        return root / name / "voice.md"
    for r in voice_roots():
        candidate = r / name / "voice.md"
        if candidate.is_file():
            return candidate
    # Fall back to the user-root candidate so existing callers that
    # synthesize a path even for missing voices (write_voice) get the
    # expected target location.
    from prose_craft.config import load_settings

    return load_settings().voices_root / name / "voice.md"


def lexicon_path(name: str, *, root: Path | None = None) -> Path:
    """Return the resolved path for a lexicon ``<name>``.

    Mirrors :func:`voice_path` against ``_lexicons/<name>.yaml`` in each
    voice root. First match wins; absent falls back to the user-root
    candidate so callers that synthesize a path even for missing
    lexicons (write paths, future authoring tools) get the expected
    target location.
    """
    if _NAME_RE.fullmatch(name) is None:
        raise VoiceNameError(f"invalid lexicon name {name!r}: must match [a-zA-Z][a-zA-Z0-9-]*")
    if root is not None:
        return root / "_lexicons" / f"{name}.yaml"
    for r in voice_roots():
        candidate = r / "_lexicons" / f"{name}.yaml"
        if candidate.is_file():
            return candidate
    from prose_craft.config import load_settings

    return load_settings().voices_root / "_lexicons" / f"{name}.yaml"


def never_list_path(name: str, *, root: Path | None = None) -> Path:
    """Return the resolved path for a never-list ``<name>``.

    Mirrors :func:`voice_path` against ``_never_lists/<name>.yaml`` in
    each voice root.
    """
    if _NAME_RE.fullmatch(name) is None:
        raise VoiceNameError(f"invalid never-list name {name!r}: must match [a-zA-Z][a-zA-Z0-9-]*")
    if root is not None:
        return root / "_never_lists" / f"{name}.yaml"
    for r in voice_roots():
        candidate = r / "_never_lists" / f"{name}.yaml"
        if candidate.is_file():
            return candidate
    from prose_craft.config import load_settings

    return load_settings().voices_root / "_never_lists" / f"{name}.yaml"
