"""Voice profile read / write / list.

The on-disk format is YAML front-matter between ``---`` markers,
followed by a prose body. PyYAML parses the front-matter; the rest of
the file is preserved verbatim by ``write_voice``.
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel

from prose_craft.voices.location import (
    get_bundled_voices_root,
    get_voices_root,
    voice_path,
)

if TYPE_CHECKING:
    from prose_craft.voices.model import VoiceProfile


class VoiceProfileNotFound(FileNotFoundError):
    """Raised when a voice profile does not exist on disk."""


class VoiceParseError(ValueError):
    """Raised when a voice file exists but its front-matter fails to parse.

    Carries the offending file path and a one-line summary so callers
    (``prose voice list``, MCP tools) can surface the problem to the
    user instead of silently dropping the voice from the count.
    """


class VoiceSummary(BaseModel):
    name: str
    updated: date


class VoiceError(BaseModel):
    """One broken voice in a listing: the directory name + the parse error."""

    name: str
    error: str


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)


def read_voice(name: str, *, root: Path | None = None) -> "VoiceProfile":
    """Parse <root>/<name>/voice.md and return a VoiceProfile.

    The prose body is dropped here (VoiceProfile has no body field);
    callers that need the body can call ``read_voice_raw``. Falls back
    to the bundled voices shipped with the wheel when the user root
    has no copy of the voice.
    """
    path = _resolve_voice_path(name, root)
    if path is None:
        raise VoiceProfileNotFound(
            f"voice profile {name!r} not found at {voice_path(name, root=root)}"
        )
    return _parse_voice_file(path)


def read_voice_file(name: str, *, root: Path | None = None) -> str:
    """Return the raw voice.md contents (front-matter + prose body).

    Raises VoiceProfileNotFound if the file does not exist. Falls back
    to the bundled voices shipped with the wheel.
    """
    path = _resolve_voice_path(name, root)
    if path is None:
        raise VoiceProfileNotFound(
            f"voice profile {name!r} not found at {voice_path(name, root=root)}"
        )
    return path.read_text(encoding="utf-8")


def read_voice_raw(name: str, *, root: Path | None = None) -> tuple["VoiceProfile", str]:
    """Parse voice.md and return (profile, prose_body).

    The prose body is the text after the closing ``---`` marker,
    without the trailing newline-strip the regex applies. Falls back
    to the bundled voices shipped with the wheel.
    """
    path = _resolve_voice_path(name, root)
    if path is None:
        raise VoiceProfileNotFound(
            f"voice profile {name!r} not found at {voice_path(name, root=root)}"
        )
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise VoiceProfileNotFound(f"voice profile {name!r} has no front-matter at {path}")
    front_matter = yaml.safe_load(match.group(1)) or {}
    body = match.group(2)
    # Late import to avoid a circular dependency at module load.
    from prose_craft.voices.model import VoiceProfile

    profile = VoiceProfile.model_validate(front_matter)
    return profile, body


def _resolve_voice_path(name: str, root: Path | None) -> Path | None:
    """Return the first existing ``<root>/<name>/voice.md`` or None.

    Checks the user root first; if the file is missing there and a
    bundled voices root is available, falls back to the bundled copy so
    shipped voices are readable from a fresh install.
    """
    candidate = voice_path(name, root=root)
    if candidate.is_file():
        return candidate
    bundled = get_bundled_voices_root()
    if bundled is not None:
        bundled_candidate = voice_path(name, root=bundled)
        if bundled_candidate.is_file():
            return bundled_candidate
    return None


def _parse_voice_file(path: Path) -> "VoiceProfile":
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise VoiceProfileNotFound(f"voice profile at {path} has no front-matter")
    front_matter = yaml.safe_load(match.group(1)) or {}
    from prose_craft.voices.model import VoiceProfile

    return VoiceProfile.model_validate(front_matter)


def write_voice(
    profile: Any,
    prose_body: str = "",
    *,
    root: Path | None = None,
) -> Path:
    """Serialize the profile + prose body to voice.md.

    Atomic write: write to a temp file in the same directory, fsync,
    rename. Creates parent directories.
    """
    path = voice_path(profile.voice, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)

    from prose_craft.voices.model import VoiceProfile

    if not isinstance(profile, VoiceProfile):
        profile = VoiceProfile.model_validate(profile)
    payload = profile.model_dump(mode="json", exclude_none=False)
    front_matter = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    body = prose_body if prose_body.startswith("\n") else "\n" + prose_body
    full = f"---\n{front_matter}---{body}"

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".voice.", suffix=".md.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(full)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
    return path


def list_voices(*, root: Path | None = None) -> list[VoiceSummary]:
    """Enumerate every voice under the root.

    Returns voices sorted by name. Voices without parseable front-matter
    are skipped silently.

    When the resolved user root (default or ``root=``) yields no
    parseable voices, falls back to the bundled shipped voices so a
    freshly installed tool can show defaults without manual setup. User
    voices always take priority — bundled voices only appear when the
    user root contributes nothing.
    """
    base = root if root is not None else get_voices_root()
    seen: set[str] = set()
    out: list[VoiceSummary] = []

    def _scan(b: Path) -> None:
        if not b.exists():
            return
        for child in sorted(b.iterdir()):
            if not child.is_dir() or child.name in seen:
                continue
            candidate = child / "voice.md"
            if not candidate.is_file():
                continue
            try:
                profile = _parse_voice_file(candidate)
            except Exception:
                continue
            seen.add(profile.voice)
            out.append(VoiceSummary(name=profile.voice, updated=profile.updated))

    _scan(base)
    if not out:
        bundled = get_bundled_voices_root()
        if bundled is not None and bundled != base:
            _scan(bundled)
    return out


def list_voice_errors(*, root: Path | None = None) -> list[VoiceError]:
    """Enumerate voice directories whose front-matter fails to parse.

    Walks the same roots ``list_voices`` scans (user root; falls back
    to bundled when the user root is empty) and returns one
    ``VoiceError`` per directory whose ``voice.md`` does not parse
    against the current ``VoiceProfile`` schema. Bundled voices are not
    re-scanned for errors — only the user root.

    The function exists so callers (``prose voice list``,
    ``prose_craft.mcp``) can surface breakage to the user instead of
    silently undercounting the library.
    """
    base = root if root is not None else get_voices_root()
    out: list[VoiceError] = []
    if not base.exists():
        return out
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        candidate = child / "voice.md"
        if not candidate.is_file():
            continue
        try:
            _parse_voice_file(candidate)
        except Exception as exc:
            summary = f"{child.name}: {exc}".splitlines()[0]
            out.append(VoiceError(name=child.name, error=summary))
    return out
