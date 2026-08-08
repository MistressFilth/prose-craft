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

from prose_craft.voices.location import VoiceNameError, voice_path

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


class VoiceDeleteError(RuntimeError):
    """Raised when an operation would mutate a shared-only voice."""


class VoiceImportError(RuntimeError):
    """Raised by :func:`import_voice` for collision or missing-name cases."""


class VoiceSummary(BaseModel):
    name: str
    updated: date


class VoiceError(BaseModel):
    """One broken voice in a listing: the directory name + the parse error."""

    name: str
    error: str


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.DOTALL)
_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*$")


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
    payload = profile.model_dump(mode="json", exclude_none=True, exclude_unset=True)
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
    """Enumerate every visible voice under user + shared roots.

    When ``root`` is None, walks :func:`prose_craft.voices.location.voice_roots`
    in precedence order with the same dedupe behavior the original
    single-root scanner used. When ``root`` is given, scans only that
    root (escape hatch for tests and explicit overrides).
    """
    roots: list[Path]
    if root is not None:
        roots = [root]
    else:
        from prose_craft.voices.location import voice_roots

        roots = voice_roots()
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
            # Mark the directory name as seen the moment ``voice.md``
            # exists, *before* parsing. A malformed user voice then
            # blocks the shared fallback of the same name — the user
            # directory is authoritative for its name even when its
            # contents are broken. Parse failures surface through
            # :func:`list_voice_errors`, not here.
            seen.add(child.name)
            try:
                profile = _parse_voice_file(candidate)
            except Exception:
                continue
            out.append(VoiceSummary(name=profile.voice, updated=profile.updated))

    for r in roots:
        _scan(r)
    return out


def list_voice_errors(*, root: Path | None = None) -> list[VoiceError]:
    """Enumerate voice directories whose front-matter fails to parse.

    Walks user + shared roots when ``root=None``. The single-root
    escape hatch (passing ``root=``) is preserved for tests.
    """
    roots: list[Path]
    if root is not None:
        roots = [root]
    else:
        from prose_craft.voices.location import voice_roots

        roots = voice_roots()
    out: list[VoiceError] = []
    seen: set[str] = set()
    for base in roots:
        if not base.exists():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name in seen:
                continue
            candidate = child / "voice.md"
            if not candidate.is_file():
                continue
            # Mark the name seen *after* ``voice.md`` is confirmed
            # present, so an empty user directory does not block a
            # shared voice directory with the same name from being
            # reported when it has a malformed ``voice.md``.
            seen.add(child.name)
            try:
                _parse_voice_file(candidate)
            except Exception as exc:
                summary = f"{child.name}: {exc}".splitlines()[0]
                out.append(VoiceError(name=child.name, error=summary))
    return out


def import_voice(name: str, *, root: Path | None = None) -> Path:
    """Copy a shared voice into the user root.

    Returns the user-root target path. Raises :class:`VoiceImportError`
    if the voice is not visible anywhere, or already present in the
    user root. The ``root`` kwarg is preserved for symmetry with the
    other IO helpers; pass it to redirect the destination.
    """
    import shutil

    from prose_craft.config import load_settings
    from prose_craft.voices.location import voice_path

    user_root = load_settings().voices_root if root is None else root
    user_target = user_root / name / "voice.md"
    if user_target.is_file():
        raise VoiceImportError(f"voice {name!r} already in user root at {user_target}")
    source = voice_path(name)
    if not source.is_file():
        raise VoiceImportError(f"voice {name!r} not found")
    user_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, user_target)
    return user_target


def delete_voice(name: str, *, root: Path | None = None) -> Path:
    """Remove ``<root>/<name>/`` from disk. Returns the deleted directory path.

    When ``root=None``, walks :func:`prose_craft.voices.location.voice_roots`
    (user first, then shared roots). If only a shared root holds the voice,
    raises :class:`VoiceDeleteError` — shared voices are read-only by
    convention and ``--force`` cannot override. When both a user and a shared
    copy exist, only the user copy is removed; the caller is expected to
    surface the surviving shared path to the operator.

    Raises:
        VoiceNameError: invalid name format.
        VoiceProfileNotFound: name is valid but no root contains the voice.
        VoiceDeleteError: voice is shared-only (no user copy to delete).
    """
    import shutil

    from prose_craft.config import load_settings
    from prose_craft.voices.location import voice_path as _voice_path
    from prose_craft.voices.location import voice_roots

    # Validate the name first — the not-found path below only checks
    # `_NAME_RE` indirectly via `voice_path()`, and `Path` arithmetic on
    # a name with traversal segments (e.g. ``../escape``) would happily
    # resolve outside ``user_root`` if a sibling directory exists with a
    # matching ``voice.md``. Reject up front so we never reach the
    # filesystem arithmetic with an invalid name.
    if _NAME_RE.fullmatch(name) is None:
        raise VoiceNameError(f"invalid voice name {name!r}: must match [a-zA-Z][a-zA-Z0-9-]*")

    user_root = root if root is not None else load_settings().voices_root
    user_target = user_root / name

    # Find every root that actually contains the voice.
    roots_with_voice: list[Path] = []
    if root is not None:
        if (root / name / "voice.md").is_file():
            roots_with_voice.append(root)
    else:
        for r in voice_roots():
            if (r / name / "voice.md").is_file():
                roots_with_voice.append(r)

    if not roots_with_voice:
        # No root had it — surface as not-found using the same wording as
        # read_voice() so error messages stay consistent.
        raise VoiceProfileNotFound(
            f"voice profile {name!r} not found at {_voice_path(name, root=root)}"
        )

    # "Shared-only" means the user root is not among the roots that
    # contain the voice. voice_roots() always lists the user root first,
    # but we check membership rather than position so this stays correct
    # if the ordering invariant ever changes.
    if user_root not in roots_with_voice:
        raise VoiceDeleteError(
            f"voice {name!r} is shared-only; refusing to delete (root {roots_with_voice[0]})"
        )

    shutil.rmtree(user_target)
    return user_target


def init_from_template(name: str, *, root: Path | None = None) -> tuple["VoiceProfile", str]:
    """Scaffold a new voice from the bundled template.

    Replaces ``<name>``, ``<voice-name>``, and ``<YYYY-MM-DD>`` in the
    template's front-matter and prose body, parses the substituted
    front-matter through :class:`VoiceProfile` (so template drift
    fails loudly), and returns ``(profile, prose_body)``.

    Does NOT write to disk — the caller invokes :func:`write_voice`
    after any extra mutation. Does NOT check for existing voices —
    the caller does so via :func:`prose_craft.voices.location.voice_path`.

    The ``root`` argument is reserved for future template lookup
    (e.g. per-project overrides); it is currently unused because the
    template is bundled with the engine.

    Raises:
        pydantic.ValidationError: the substituted front-matter
            doesn't match ``VoiceProfile`` (forbidden extras, wrong
            types, missing required keys).
        ValueError: a placeholder survives substitution — the
            template references an unknown token, or the helper's
            substitution set is incomplete.
    """
    from prose_craft.data import load_template

    text = load_template()
    today = date.today().isoformat()
    text = text.replace("<name>", name).replace("<voice-name>", name)
    text = text.replace("<YYYY-MM-DD>", today)

    # Catch template drift in the other direction: an unknown <...>
    # placeholder would silently survive into the written file. Scan
    # the whole substituted text — both front-matter and prose body —
    # before splitting, so a stray placeholder in front-matter fails
    # the same way as one in the body.
    #
    # Token shape: only flag angle brackets whose content has no
    # whitespace. Real substitution placeholders (``<name>``,
    # ``<voice-name>``, ``<YYYY-MM-DD>``, ``<bogus-token>``) are
    # single-word tokens; the intentional user-prompt placeholder
    # in ``audiences.rationale`` (e.g. ``<why this voice has
    # separate ceilings per audience>``) is multi-word and is meant
    # to survive substitution for the composer to fill in.
    _PLACEHOLDER_TOKEN = re.compile(r"<[^<>\s]+>")
    for line in text.splitlines():
        match = _PLACEHOLDER_TOKEN.search(line)
        if match is not None:
            raise ValueError(f"unsurrogated placeholder in template: {line!r}")

    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("voice template has no front-matter; check data/voice_template.md")
    front_matter_str, prose_body = match.group(1), match.group(2)

    front_matter = yaml.safe_load(front_matter_str) or {}
    from prose_craft.voices.model import VoiceProfile

    profile = VoiceProfile.model_validate(front_matter)
    return profile, prose_body


def invalidate_index_cache() -> None:
    """Delete the persistent on-disk voice index cache.

    Called by every write path (``voice init``, ``voice delete``,
    ``voice import``, ``voice compose`` fresh-init). Next read
    rebuilds. Module-level in-memory caches in MCP and any other
    long-lived caller should be invalidated by the caller alongside
    this call.
    """
    from prose_craft.voices.index import VoiceIndex

    VoiceIndex.invalidate_cache()
