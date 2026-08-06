"""Tests for prose_craft.voices.io public surface added in Task 4.

Covers:
- Multi-root scan via ``list_voices`` / ``list_voice_errors``.
- ``import_voice`` copies a shared voice into the user root.
- :class:`VoiceImportError` for collision and missing-name cases
  (:class:`VoiceDeleteError` is exercised by the future delete
  command's tests).
"""

from __future__ import annotations

import pytest

from prose_craft.voices.io import (
    VoiceImportError,
    import_voice,
    list_voice_errors,
    list_voices,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run tests against the roots they declare via monkeypatch.setenv.

    The shared :file:`tests/conftest.py` autouse fixture only resets
    ``XDG_*_HOME`` style variables; ``XDG_DATA_DIRS`` defaults to unset
    unless the test opts in. This fixture keeps the behavior explicit
    at the top of the file so a future reader does not get surprised
    by an inherited ``XDG_DATA_DIRS`` leaking across tests.
    """
    for var in (
        "PROSE_CRAFT_VOICES_ROOT",
        "XDG_DATA_DIRS",
        "XDG_DATA_HOME",
        "PROSE_CRAFT_XDG_DATA_HOME",
    ):
        monkeypatch.delenv(var, raising=False)


# A minimal-but-valid VoiceProfile front-matter template. The voice
# schema requires created/updated dates plus the six config blocks;
# ``.format(name=...)`` substitutes the voice name only.
_VALID_FRONTMATTER = (
    "---\n"
    "voice: {name}\n"
    "version: 1\n"
    "created: 2026-08-01\n"
    "updated: 2026-08-01\n"
    "register: {{}}\n"
    "diction: {{}}\n"
    "rhythm: {{}}\n"
    "syntax: {{}}\n"
    "lexicon: {{}}\n"
    "structure: {{}}\n"
    "---\n"
)


def test_list_voices_includes_shared(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    (user / "local").mkdir(parents=True)
    (user / "local" / "voice.md").write_text(_VALID_FRONTMATTER.format(name="local"))
    (shared / "prose-craft" / "voices" / "system").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "system" / "voice.md").write_text(
        _VALID_FRONTMATTER.format(name="system")
    )
    names = {v.name for v in list_voices()}
    assert names == {"local", "system"}


def test_list_voice_errors_includes_shared(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    (shared / "prose-craft" / "voices" / "broken").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "broken" / "voice.md").write_text("not yaml")
    errs = list_voice_errors()
    assert any(e.name == "broken" for e in errs)


def test_import_voice_copies_shared_to_user(monkeypatch, tmp_path):
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    src = shared / "prose-craft" / "voices" / "shipped"
    src.mkdir(parents=True)
    (src / "voice.md").write_text(_VALID_FRONTMATTER.format(name="shipped") + "\n# body\n")
    target = import_voice("shipped")
    assert target == user / "shipped" / "voice.md"
    assert target.read_text() == _VALID_FRONTMATTER.format(name="shipped") + "\n# body\n"


def test_import_voice_already_local_errors(monkeypatch, tmp_path):
    user = tmp_path / "user"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    (user / "alpha" / "voice.md").parent.mkdir(parents=True)
    (user / "alpha" / "voice.md").write_text(_VALID_FRONTMATTER.format(name="alpha"))
    with pytest.raises(VoiceImportError, match="already in user root"):
        import_voice("alpha")


def test_import_voice_missing_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path / "user"))
    monkeypatch.delenv("XDG_DATA_DIRS", raising=False)
    with pytest.raises(VoiceImportError, match="not found"):
        import_voice("ghost")
