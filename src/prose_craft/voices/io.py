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

from prose_craft.voices.location import get_voices_root, voice_path

if TYPE_CHECKING:
    from prose_craft.voices.model import VoiceProfile


class VoiceProfileNotFound(FileNotFoundError):
    """Raised when a voice profile does not exist on disk."""


class VoiceSummary(BaseModel):
    name: str
    updated: date


_FRONTMATTER_RE = re.compile(
    r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL
)


def read_voice(name: str, *, root: Path | None = None) -> "VoiceProfile":
    """Parse <root>/<name>/voice.md and return a VoiceProfile.

    The prose body is dropped here (VoiceProfile has no body field);
    callers that need the body can call ``read_voice_raw``.
    """
    path = voice_path(name, root=root)
    if not path.exists():
        raise VoiceProfileNotFound(f"voice profile {name!r} not found at {path}")
    return _parse_voice_file(path)


def read_voice_raw(name: str, *, root: Path | None = None) -> tuple["VoiceProfile", str]:
    """Parse voice.md and return (profile, prose_body).

    The prose body is the text after the closing ``---`` marker,
    without the trailing newline-strip the regex applies.
    """
    path = voice_path(name, root=root)
    if not path.exists():
        raise VoiceProfileNotFound(f"voice profile {name!r} not found at {path}")
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

    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=".voice.", suffix=".md.tmp"
    )
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
    """
    base = root or get_voices_root()
    if not base.exists():
        return []
    out: list[VoiceSummary] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        candidate = child / "voice.md"
        if not candidate.is_file():
            continue
        try:
            profile = _parse_voice_file(candidate)
        except Exception:
            continue
        out.append(VoiceSummary(name=profile.voice, updated=profile.updated))
    return out
