"""Static package data: the voice template, bundled reference YAML."""

from pathlib import Path

DATA_DIR = Path(__file__).parent


def load_template() -> str:
    """Return the contents of voice_template.md."""
    return (DATA_DIR / "voice_template.md").read_text(encoding="utf-8")
