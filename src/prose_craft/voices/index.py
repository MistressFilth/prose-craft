"""In-memory voice index across user and shared roots."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from prose_craft.voices.location import voice_roots


class Origin(Enum):
    USER = "user"
    SHARED = "shared"


@dataclass(frozen=True)
class VoiceEntry:
    origin: Origin
    path: Path
    mtime_ns: int


class VoiceIndex:
    """Name → :class:`VoiceEntry` mapping built by walking roots once."""

    INDEX_VERSION = 1

    def __init__(self, entries: Mapping[str, VoiceEntry]) -> None:
        self._entries = dict(entries)

    @classmethod
    def build(cls) -> "VoiceIndex":
        entries: dict[str, VoiceEntry] = {}
        user_root = voice_roots()[0]
        for i, root in enumerate(voice_roots()):
            # Project-root voices intentionally tag as Origin.SHARED until
            # Origin.PROJECT lands — deferred per the per-project voice roots
            # design (spec 2026-08-08-per-project-voice-roots-design.md
            # "Out of scope").
            origin = Origin.USER if root == user_root else Origin.SHARED
            if not root.exists():
                continue
            for child in sorted(root.iterdir()):
                if not child.is_dir() or child.name in entries:
                    continue
                candidate = child / "voice.md"
                if not candidate.is_file():
                    continue
                entries[child.name] = VoiceEntry(
                    origin=origin,
                    path=candidate,
                    mtime_ns=candidate.stat().st_mtime_ns,
                )
        return cls(entries)

    def get(self, name: str) -> VoiceEntry | None:
        return self._entries.get(name)

    def __iter__(self) -> Iterator[tuple[str, VoiceEntry]]:
        return iter(self._entries.items())

    def __len__(self) -> int:
        return len(self._entries)

    def invalidate(self) -> "VoiceIndex":
        """Drop the cache and rebuild from disk."""
        return VoiceIndex.build()

    @classmethod
    def load_or_build(cls, *, cache: Path | None = None) -> "VoiceIndex":
        """Return a fresh index, using the on-disk cache if fresh.

        ``cache`` defaults to :func:`prose_craft.xdg.voices_index_path`.
        Cache load failures (missing, wrong version, corrupt JSON,
        schema mismatch) are silent — fall through to a fresh build.
        Cache write failures are also silent — reads never fail
        because the cache failed.
        """
        from prose_craft.xdg import voices_index_path

        cache_path = cache if cache is not None else voices_index_path()
        if cache_path.is_file():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                if payload.get("version") == cls.INDEX_VERSION:
                    cached = cls._from_payload(payload)
                    if not cls._any_root_advanced(cached, payload):
                        return cached
            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                pass  # fall through to rebuild
        return cls._build_and_persist(cache_path)

    @classmethod
    def invalidate_cache(cls, *, cache: Path | None = None) -> None:
        """Delete the on-disk cache file if present.

        Next ``load_or_build()`` call rebuilds. Module-level caches
        in MCP and any in-process callers should run their own
        invalidation alongside this.
        """
        from prose_craft.xdg import voices_index_path

        cache_path = cache if cache is not None else voices_index_path()
        cache_path.unlink(missing_ok=True)

    @classmethod
    def _from_payload(cls, payload: dict) -> "VoiceIndex":
        entries: dict[str, VoiceEntry] = {}
        for entry in payload.get("entries", []):
            name = entry["name"]
            origin = Origin(entry["origin"])
            entries[name] = VoiceEntry(
                origin=origin,
                path=Path(entry["path"]),
                mtime_ns=entry["mtime_ns"],
            )
        return cls(entries)

    @classmethod
    def _any_root_advanced(cls, index: "VoiceIndex", payload: dict) -> bool:
        """True if any current root's mtime is later than the cached snapshot."""
        cached_mtimes = payload.get("roots_mtime_ns", {})
        for root in voice_roots():
            try:
                current = root.stat().st_mtime_ns
            except OSError:
                continue
            if current > cached_mtimes.get(str(root), 0):
                return True
        # Also: per-entry staleness check (handles in-place edits).
        for name, entry in index._entries.items():
            try:
                if entry.path.stat().st_mtime_ns > entry.mtime_ns:
                    return True
            except OSError:
                return True  # file disappeared
        return False

    @classmethod
    def _build_and_persist(cls, cache_path: Path) -> "VoiceIndex":
        index = cls.build()
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = cls._to_payload(index)
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{cache_path.name}.",
                suffix=".tmp",
                dir=cache_path.parent,
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(json.dumps(payload, indent=2))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp_name, cache_path)
            except Exception:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)
                raise
        except OSError:
            pass  # cache write failure is silent; the in-memory index is the source of truth
        return index

    @classmethod
    def _to_payload(cls, index: "VoiceIndex") -> dict:
        roots_mtime_ns: dict[str, int] = {}
        for root in voice_roots():
            try:
                roots_mtime_ns[str(root)] = root.stat().st_mtime_ns
            except OSError:
                continue
        entries = [
            {
                "name": name,
                "origin": entry.origin.value,
                "path": str(entry.path),
                "mtime_ns": entry.mtime_ns,
            }
            for name, entry in index._entries.items()
        ]
        return {
            "version": cls.INDEX_VERSION,
            "roots_mtime_ns": roots_mtime_ns,
            "entries": entries,
        }
