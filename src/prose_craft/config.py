"""Runtime configuration: env vars, defaults.

Path resolution lives in :mod:`prose_craft.paths`.
"""

from __future__ import annotations

import os

DEFAULT_MODEL = "anthropic:claude-opus-4-5"

__all__ = ["DEFAULT_MODEL", "get_model"]


def get_model() -> str:
    """Return the configured model identifier.

    Reads ``PROSE_CRAFT_MODEL`` from the environment; falls back to
    ``DEFAULT_MODEL``.
    """
    return os.environ.get("PROSE_CRAFT_MODEL", DEFAULT_MODEL)
