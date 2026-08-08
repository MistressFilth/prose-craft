"""Unit tests for the persistent voice index."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock


def test_load_or_build_creates_cache_when_missing(tmp_path, monkeypatch):
    """First call writes the cache file."""
    from prose_craft.voices.index import VoiceIndex

    user = tmp_path / "user" / "prose-craft" / "voices"
    user.mkdir(parents=True)
    (user / "alpha").mkdir()
    (user / "alpha" / "voice.md").write_text(
        "voice: alpha\nversion: 1\ncreated: 2026-08-08\nupdated: 2026-08-08\n"
        "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "user_cfg"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_DIRS", "")

    cache = tmp_path / "cache" / "prose-craft" / "voices-index.json"
    assert not cache.exists()
    VoiceIndex.load_or_build(cache=cache)
    assert cache.exists()


def test_load_or_build_reuses_cache_when_fresh(tmp_path, monkeypatch):
    """Second call does NOT re-walk the filesystem."""
    from prose_craft.voices.index import VoiceIndex

    user = tmp_path / "user" / "prose-craft" / "voices"
    user.mkdir(parents=True)
    (user / "alpha").mkdir()
    (user / "alpha" / "voice.md").write_text(
        "voice: alpha\nversion: 1\ncreated: 2026-08-08\nupdated: 2026-08-08\n"
        "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user"))
    monkeypatch.setenv("XDG_DATA_DIRS", "")
    cache = tmp_path / "cache.json"
    first = VoiceIndex.load_or_build(cache=cache)
    assert any(name == "alpha" for name, _ in first)

    # Second call: iterdir is monkeypatched to raise if called; if the
    # cache is reused, iterdir is never called.
    real_iterdir = Path.iterdir
    with mock.patch.object(Path, "iterdir", side_effect=AssertionError("iterdir called")):
        second = VoiceIndex.load_or_build(cache=cache)
    assert any(name == "alpha" for name, _ in second)
    # Sanity: real iterdir still works outside the patch.
    assert list(real_iterdir(user))


def test_load_or_build_rebuilds_when_root_mtime_advances(tmp_path, monkeypatch):
    """Touching a root directory triggers a rebuild."""
    from prose_craft.voices.index import VoiceIndex

    user = tmp_path / "user" / "prose-craft" / "voices"
    user.mkdir(parents=True)
    (user / "alpha").mkdir()
    (user / "alpha" / "voice.md").write_text("voice: alpha\n", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user"))
    monkeypatch.setenv("XDG_DATA_DIRS", "")
    cache = tmp_path / "cache.json"
    VoiceIndex.load_or_build(cache=cache)

    # Touch the user root to advance its mtime.
    import os

    new_mtime = (user.stat().st_mtime_ns // 1_000_000_000 + 5) * 1_000_000_000
    os.utime(user, ns=(new_mtime, new_mtime))

    # Add a second voice after the rebuild triggers.
    (user / "beta").mkdir()
    (user / "beta" / "voice.md").write_text("voice: beta\n", encoding="utf-8")

    second = VoiceIndex.load_or_build(cache=cache)
    names = {name for name, _ in second}
    assert names == {"alpha", "beta"}


def test_load_or_build_rebuilds_on_corrupt_cache(tmp_path):
    """Garbage in the cache file triggers a silent rebuild."""
    from prose_craft.voices.index import VoiceIndex

    cache = tmp_path / "cache.json"
    cache.write_text("not valid json {", encoding="utf-8")
    index = VoiceIndex.load_or_build(cache=cache)
    # No exception; index is empty (no roots configured in this test).
    assert len(index) == 0


def test_load_or_build_rebuilds_on_wrong_version(tmp_path):
    """A cache file with a different version triggers a silent rebuild."""
    from prose_craft.voices.index import VoiceIndex

    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps({"version": 99, "roots_mtime_ns": {}, "entries": []}),
        encoding="utf-8",
    )
    index = VoiceIndex.load_or_build(cache=cache)
    assert len(index) == 0


def test_invalidate_cache_removes_file(tmp_path):
    """invalidate_cache() deletes the cache file; next call rebuilds."""
    from prose_craft.voices.index import VoiceIndex

    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps({"version": 1, "roots_mtime_ns": {}, "entries": []}),
        encoding="utf-8",
    )
    assert cache.exists()
    VoiceIndex.invalidate_cache(cache=cache)
    assert not cache.exists()


def test_invalidate_cache_noop_when_missing(tmp_path):
    """invalidate_cache() on a missing file is a no-op."""
    from prose_craft.voices.index import VoiceIndex

    cache = tmp_path / "does-not-exist.json"
    VoiceIndex.invalidate_cache(cache=cache)  # must not raise


def test_atomic_write_under_simulated_crash(tmp_path, monkeypatch):
    """If fsync raises, the old cache file is unchanged."""
    from prose_craft.voices.index import VoiceIndex

    cache = tmp_path / "cache.json"
    pre_existing = json.dumps({"version": 1, "roots_mtime_ns": {}, "entries": [{"name": "pre"}]})
    cache.write_text(pre_existing, encoding="utf-8")

    # Trigger a real build that will try to write the cache; mock fsync to raise.
    real_fsync = Path.open  # keep ref to avoid GC  # noqa: F841

    def _raise_fsync(self):
        # Open the file via Path.open for the actual write call; raise on fsync.
        raise OSError("simulated crash")

    # We patch os.fsync, which tempfile-based writers call.
    import os as _os

    monkeypatch.setattr(_os, "fsync", _raise_fsync)

    VoiceIndex.load_or_build(cache=cache)

    # Old contents survive because os.replace was never reached.
    assert cache.read_text(encoding="utf-8") == pre_existing


def test_cache_write_failure_does_not_break_read(tmp_path, monkeypatch):
    """If the cache write raises, the read still returns the fresh index."""
    from prose_craft.voices.index import VoiceIndex

    user = tmp_path / "user" / "prose-craft" / "voices"
    user.mkdir(parents=True)
    (user / "alpha").mkdir()
    (user / "alpha" / "voice.md").write_text("voice: alpha\n", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user"))
    monkeypatch.setenv("XDG_DATA_DIRS", "")
    cache = tmp_path / "cache.json"

    # Force the atomic-write's tempfile creation to raise.
    import tempfile

    real_mkstemp = tempfile.mkstemp  # noqa: F841

    def _raise_mkstemp(*args, **kwargs):
        raise OSError("simulated cache write failure")

    monkeypatch.setattr(tempfile, "mkstemp", _raise_mkstemp)

    index = VoiceIndex.load_or_build(cache=cache)  # must not raise
    names = {name for name, _ in index}
    assert names == {"alpha"}
    assert not cache.exists()


def test_load_or_build_rebuilds_on_in_place_file_edit(tmp_path, monkeypatch):
    """A cached entry whose voice.md mtime has advanced triggers a rebuild."""
    from prose_craft.voices.index import VoiceIndex

    user = tmp_path / "user" / "prose-craft" / "voices"
    user.mkdir(parents=True)
    voice_dir = user / "alpha"
    voice_dir.mkdir()
    voice_md = voice_dir / "voice.md"
    voice_md.write_text("voice: alpha\n", encoding="utf-8")

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "user"))
    monkeypatch.setenv("XDG_DATA_DIRS", "")
    cache = tmp_path / "cache.json"

    # First call: build and persist.
    first = VoiceIndex.load_or_build(cache=cache)
    assert any(name == "alpha" for name, _ in first)

    # Advance only the voice.md file's mtime (root directory mtime unchanged).
    import os

    new_mtime = (voice_md.stat().st_mtime_ns // 1_000_000_000 + 5) * 1_000_000_000
    os.utime(voice_md, ns=(new_mtime, new_mtime))

    # Also add a new voice file (still under the unchanged root).
    (user / "beta").mkdir()
    (user / "beta" / "voice.md").write_text("voice: beta\n", encoding="utf-8")

    second = VoiceIndex.load_or_build(cache=cache)
    names = {name for name, _ in second}
    assert names == {"alpha", "beta"}
