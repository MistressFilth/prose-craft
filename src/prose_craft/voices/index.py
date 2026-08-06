"""In-memory voice index across user and shared roots."""
from __future__ import annotations

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

    def __init__(self, entries: Mapping[str, VoiceEntry]) -> None:
        self._entries = dict(entries)

    @classmethod
    def build(cls) -> "VoiceIndex":
        entries: dict[str, VoiceEntry] = {}
        user_root = voice_roots()[0]
        for i, root in enumerate(voice_roots()):
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
