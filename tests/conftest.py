"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_voices_root(tmp_path: Path) -> Path:
    """An isolated voices root for the duration of one test."""
    root = tmp_path / "voices"
    root.mkdir()
    return root
