"""Tests for prose_craft.references.load_reference."""

from prose_craft.references import REFERENCES_DIR, load_reference


def test_references_dir_is_package_directory():
    assert REFERENCES_DIR.name == "references"
    assert REFERENCES_DIR.is_dir()


def test_load_reference_returns_file_contents():
    text = load_reference("prose_analysis")
    assert text.startswith("# Prose analysis reference")


def test_load_reference_for_each_markdown_file():
    expected = {
        "prose_analysis": "# Prose analysis reference",
        "diction_tuning": "# Diction tuning reference",
        "rhythm_mastery": "# Rhythm mastery reference",
        "cohesion_craft": "# Cohesion craft reference",
        "voice_contract": "# Voice contract reference",
    }
    for name, heading in expected.items():
        text = load_reference(name)
        assert text.startswith(heading), f"{name} did not start with {heading!r}"


def test_load_reference_resolves_to_references_dir():
    expected_path = REFERENCES_DIR / "prose_analysis.md"
    assert (REFERENCES_DIR / "prose_analysis.md").exists()
    assert load_reference("prose_analysis") == expected_path.read_text(encoding="utf-8")


def test_load_reference_missing_file_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        load_reference("does_not_exist")
