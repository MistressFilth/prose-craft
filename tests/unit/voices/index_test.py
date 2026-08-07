"""Tests for prose_craft.voices.index."""

from __future__ import annotations

from pathlib import Path

import pytest

from prose_craft.voices.index import Origin, VoiceIndex


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "PROSE_CRAFT_VOICES_ROOT",
        "XDG_DATA_DIRS",
    ):
        monkeypatch.delenv(var, raising=False)


def _make_voice(root: Path, name: str) -> Path:
    d = root / "prose-craft" / "voices" / name
    d.mkdir(parents=True)
    (d / "voice.md").write_text("---\nvoice: {}\n---\n".format(name))
    return d / "voice.md"


def test_build_walks_user_first(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    # User root is the raw PROSE_CRAFT_VOICES_ROOT path — no
    # /prose-craft/voices suffix. Shared roots get the suffix
    # appended by voice_roots().
    (user / "alpha").mkdir(parents=True)
    (user / "alpha" / "voice.md").write_text("user")
    _make_voice(shared, "alpha")
    _make_voice(shared, "beta")
    idx = VoiceIndex.build()
    alpha = idx.get("alpha")
    assert alpha is not None and alpha.origin is Origin.USER
    assert idx.get("beta").origin is Origin.SHARED


def test_build_no_user_root_mtime_attr(tmp_path):
    # Path.stat() always returns st_mtime_ns on supported platforms.
    idx = VoiceIndex.build()
    for entry in idx:
        assert isinstance(entry[1].mtime_ns, int)
        assert entry[1].mtime_ns >= 0


def test_build_skips_missing_roots(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "missing"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "also_missing"))
    idx = VoiceIndex.build()
    assert list(idx) == []


def test_get_returns_none_for_unknown():
    idx = VoiceIndex.build()
    assert idx.get("nope") is None


def test_iter_yields_pairs():
    idx = VoiceIndex.build()
    pairs = list(idx)
    for name, entry in pairs:
        assert isinstance(name, str)
        assert entry.origin in (Origin.USER, Origin.SHARED)
