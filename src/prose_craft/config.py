"""Runtime configuration: env vars, defaults."""

from __future__ import annotations

import os
from pathlib import Path

from prose_craft.voices.location import get_voices_root as _get_voices_root

DEFAULT_MODEL = "anthropic:claude-opus-4-5"

__all__ = ["DEFAULT_MODEL", "get_model", "get_voices_root"]


def get_model() -> str:
    """Return the configured model identifier.

    Reads ``PROSE_CRAFT_MODEL`` from the environment; falls back to
    ``DEFAULT_MODEL``.
    """
    return os.environ.get("PROSE_CRAFT_MODEL", DEFAULT_MODEL)


def get_voices_root() -> Path:
    """Re-export of ``prose_craft.voices.location.get_voices_root``."""
    return _get_voices_root()
