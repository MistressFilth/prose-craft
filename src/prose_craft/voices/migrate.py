"""Copy voice profiles from a legacy plugin-data location to the XDG root."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from pydantic import BaseModel

from prose_craft.voices.location import (
    VoiceNameError,
    get_voices_root,
    voice_path,
)


def default_legacy_root() -> Path:
    """Return the legacy plugin-data location, if any.

    Reads CLAUDE_PLUGIN_DATA env var; falls back to the prose plugin's
    default. Always returns a Path (may not exist).
    """
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if base:
        return Path(base) / "voices"
    return Path.home() / ".claude" / "plugins" / "data" / "prose" / "voices"


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
    dst_path = (dst or get_voices_root()).resolve()
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
