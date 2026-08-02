"""Tests for prose_craft.voices.migrate."""

from pathlib import Path

from prose_craft.voices.migrate import migrate_voices


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
