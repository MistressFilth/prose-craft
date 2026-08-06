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

from prose_craft.voices.location import voice_path

if TYPE_CHECKING:
    from prose_craft.voices.model import VoiceProfile


def _default_root() -> Path:
    """The active voices root.

    Deferred import: ``prose_craft.config`` reaches back into this
    package, so a module-level import would cycle.
    """
    from prose_craft.config import load_settings

    return load_settings().voices_root


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
    callers that need the body can call ``read_voice_raw``.
    """
    path = _resolve_voice_path(name, root)
    if path is None:
        raise VoiceProfileNotFound(
            f"voice profile {name!r} not found at {voice_path(name, root=root)}"
        )
    return _parse_voice_file(path)


def read_voice_file(name: str, *, root: Path | None = None) -> str:
    """Return the raw voice.md contents (front-matter + prose body).

    Raises VoiceProfileNotFound if the file does not exist.
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
    without the trailing newline-strip the regex applies.
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
    """Return ``<root>/<name>/voice.md`` if it exists, else ``None``.

    Resolution is single-root: there is no bundled fallback. Voices
    must live at the user root (or the explicit ``root=`` argument).
    """
    candidate = voice_path(name, root=root)
    return candidate if candidate.is_file() else None


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
    """Enumerate every voice under the user root.

    Returns voices sorted by name. Voices without parseable front-matter
    are skipped silently. No bundled fallback: an empty or missing root
    yields ``[]``.
    """
    base = root if root is not None else _default_root()
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
    return out


def list_voice_errors(*, root: Path | None = None) -> list[VoiceError]:
    """Enumerate voice directories whose front-matter fails to parse.

    Scans the user root only and returns one ``VoiceError`` per directory
    whose ``voice.md`` does not parse against the current ``VoiceProfile``
    schema.

    The function exists so callers (``prose voice list``,
    ``prose_craft.mcp``) can surface breakage to the user instead of
    silently undercounting the library.
    """
    base = root if root is not None else _default_root()
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
