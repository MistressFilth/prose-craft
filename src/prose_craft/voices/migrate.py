"""Copy voice profiles from a legacy plugin-data location to the XDG root."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from pydantic import BaseModel

from prose_craft.voices.location import (
    VoiceNameError,
    voice_path,
)


# Order matters: the newer prose-voicecraft plugin renames the data
# directory (``prose-voicecraft-prose-voicecraft``) so a user who has it
# populated has a richer library than the bare ``prose/`` directory the
# very first plugin used. Discovery walks newest → oldest.
_LEGACY_PLUGIN_DATA_CANDIDATES: tuple[str, ...] = (
    "prose-voicecraft-prose-voicecraft",
    "prose",
)


def default_legacy_root() -> Path:
    """Return the legacy plugin-data location, if any.

    Resolution order:
      1. ``CLAUDE_PLUGIN_DATA`` env var, if set, returns its ``voices/``
         child unconditionally.
      2. The first existing ``voices/`` directory under any of the known
         legacy plugin-data names (``prose-voicecraft-prose-voicecraft``,
         then ``prose``), so a user who has the newer prose-voicecraft
         install populated finds their 17 voices rather than the empty
         bare ``prose/`` stub.

    Always returns a Path (may not exist on disk).
    """
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if base:
        return Path(base) / "voices"

    plugins_data = Path.home() / ".claude" / "plugins" / "data"
    for name in _LEGACY_PLUGIN_DATA_CANDIDATES:
        candidate = plugins_data / name / "voices"
        if candidate.is_dir():
            return candidate
    return plugins_data / _LEGACY_PLUGIN_DATA_CANDIDATES[-1] / "voices"


class MigrationReport(BaseModel):
    copied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []


def migrate_voices(
    *,
    src: Path | None = None,
    dst: Path | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> MigrationReport:
    """Copy every <src>/<name>/voice.md to <dst>/<name>/voice.md.

    Source is never modified. Skips names that exist at dst unless
    overwrite=True. Returns a MigrationReport enumerating outcomes.
    """
    src_path = (src or default_legacy_root()).resolve()
    if dst is None:
        from prose_craft.config import load_settings

        dst_path = load_settings().voices_root
    else:
        dst_path = dst
    dst_path = dst_path.resolve()
    report = MigrationReport()

    if not src_path.exists():
        report.errors.append(f"source not found: {src_path}")
        return report

    dst_path.mkdir(parents=True, exist_ok=True)

    for child in sorted(src_path.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        try:
            target = voice_path(name, root=dst_path)
        except VoiceNameError as exc:
            report.errors.append(f"{name}: {exc}")
            continue
        if target.exists() and not overwrite:
            report.skipped.append(name)
            continue
        try:
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child / "voice.md", target)
            report.copied.append(name)
        except OSError as exc:
            report.errors.append(f"{name}: {exc}")
    return report
