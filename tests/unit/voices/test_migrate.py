"""Tests for prose_craft.voices.migrate."""

from pathlib import Path

from prose_craft.voices.migrate import default_legacy_root, migrate_voices


def _write_voice(root: Path, name: str) -> Path:
    vdir = root / name
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "voice.md").write_text(
        f"---\nvoice: {name}\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
        "register: {}\ndiction: {}\nrhythm: {}\nsyntax: {}\nlexicon: {}\nstructure: {}\n",
        encoding="utf-8",
    )
    return vdir / "voice.md"


def test_migrate_copies_all(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_voice(src, "alpha")
    _write_voice(src, "beta")
    report = migrate_voices(src=src, dst=dst)
    assert sorted(report.copied) == ["alpha", "beta"]
    assert (dst / "alpha" / "voice.md").exists()
    assert (dst / "beta" / "voice.md").exists()
    # Source untouched.
    assert (src / "alpha" / "voice.md").exists()
    assert (src / "beta" / "voice.md").exists()


def test_migrate_skips_existing(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_voice(src, "alpha")
    _write_voice(dst, "alpha")
    report = migrate_voices(src=src, dst=dst)
    assert report.copied == []
    assert "alpha" in report.skipped


def test_migrate_overwrite(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_voice(src, "alpha")
    _write_voice(dst, "alpha")
    report = migrate_voices(src=src, dst=dst, overwrite=True)
    assert "alpha" in report.copied


def test_migrate_dry_run(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    _write_voice(src, "alpha")
    report = migrate_voices(src=src, dst=dst, dry_run=True)
    assert "alpha" in report.copied
    assert not (dst / "alpha" / "voice.md").exists()


def test_migrate_missing_source(tmp_path):
    report = migrate_voices(src=tmp_path / "absent", dst=tmp_path / "dst")
    assert report.copied == []
    assert report.errors != []


def test_default_legacy_root_discovers_prose_voicecraft(monkeypatch, tmp_path):
    """When the prose-voicecraft plugin-data dir exists, it wins over
    the bare ``prose/`` fallback that the original plugin used.

    The user installed prose-voicecraft-prose-voicecraft and accumulated
    17 voices there. ``default_legacy_root`` must return that path so
    ``migrate voices`` actually finds them.
    """
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    home = tmp_path / "home"
    # Both candidate legacy roots exist; the prose-voicecraft one has
    # actual content, the bare ``prose/`` one is empty.
    voice_craft_root = (
        home / ".claude" / "plugins" / "data" / "prose-voicecraft-prose-voicecraft" / "voices"
    )
    voice_craft_root.mkdir(parents=True)
    (voice_craft_root / "discordian-base").mkdir()
    (voice_craft_root / "discordian-base" / "voice.md").write_text(
        "voice: discordian-base\n", encoding="utf-8"
    )
    (home / ".claude" / "plugins" / "data" / "prose" / "voices").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Path.home() reads this on Windows
    result = default_legacy_root()
    assert result == voice_craft_root
    assert result.exists()
    assert (result / "discordian-base" / "voice.md").is_file()


def test_default_legacy_root_falls_back_to_bare_prose(monkeypatch, tmp_path):
    """If only the bare ``prose/`` dir exists, use that."""
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    home = tmp_path / "home"
    bare = home / ".claude" / "plugins" / "data" / "prose" / "voices"
    bare.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Path.home() reads this on Windows
    result = default_legacy_root()
    assert result == bare
