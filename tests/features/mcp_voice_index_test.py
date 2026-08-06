"""MCP voice index cache behavior."""
from __future__ import annotations

from pathlib import Path

import pytest

from prose_craft import mcp


@pytest.fixture
def user_only(monkeypatch, tmp_path):
    user = tmp_path / "user"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    return user


def test_index_built_on_first_call(user_only):
    idx1 = mcp._get_index()
    idx2 = mcp._get_index()
    assert idx1 is idx2  # cached


def test_invalidate_rebuilds(user_only):
    idx1 = mcp._get_index()
    mcp._invalidate_index()
    idx2 = mcp._get_index()
    assert idx1 is not idx2
