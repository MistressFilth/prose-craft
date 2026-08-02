"""Inlined reference material loaded into agent system prompts."""

from pathlib import Path

REFERENCES_DIR = Path(__file__).parent


def load_reference(name: str) -> str:
    """Return the text of a reference file by basename (no extension)."""
    path = REFERENCES_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")
