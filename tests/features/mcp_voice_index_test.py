"""MCP voice index cache behavior."""

from __future__ import annotations

import pytest

from prose_craft import mcp


@pytest.fixture(autouse=True)
def invalidate_index():
    mcp._invalidate_index()
    yield
    mcp._invalidate_index()


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


@pytest.mark.asyncio
async def test_list_voices_resource_includes_shared(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    (user / "local").mkdir(parents=True)
    (user / "local" / "voice.md").write_text(
        "---\nvoice: local\nversion: 1\ncreated: '2026-01-01'\n"
        "updated: '2026-01-01'\nregister: {}\ndiction: {}\nrhythm: {}\n"
        "syntax: {}\nlexicon: {}\nstructure: {}\n---\n"
    )
    (shared / "prose-craft" / "voices" / "shipped").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "shipped" / "voice.md").write_text(
        "---\nvoice: shipped\nversion: 1\ncreated: '2026-01-01'\n"
        "updated: '2026-01-01'\nregister: {}\ndiction: {}\nrhythm: {}\n"
        "syntax: {}\nlexicon: {}\nstructure: {}\n---\n"
    )
    mcp._invalidate_index()
    body = await mcp.list_voices_resource()
    assert "local" in body
    assert "[user]" in body
    assert "shipped" in body
    assert "[shared]" in body
