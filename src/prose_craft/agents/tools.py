"""Tools shared by every agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai import RunContext


def read_file(ctx: RunContext[Any], file_path: str) -> str:
    """Read a UTF-8 file and return its contents.

    Resolves the path; raises FileNotFoundError for missing files. The
    agent surface always passes a string for portability.
    """
    path = Path(file_path)
    return path.read_text(encoding="utf-8")
