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


def test_list_voices_user_broken_blocks_shadow_shared(monkeypatch, tmp_path):
    """A malformed user voice must shadow a valid shared voice of the
    same name.

    Regression: ``list_voices`` previously only added a directory
    name to its dedupe set after a successful parse. A broken user
    ``voice.md`` therefore failed to block the shared fallback, and
    the user saw the shared voice instead of being told their local
    copy is broken. The fix marks the directory as seen the moment
    ``voice.md`` is on disk, regardless of parse outcome.
    """
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    # User directory: malformed front-matter.
    (user / "alpha").mkdir(parents=True)
    (user / "alpha" / "voice.md").write_text("not yaml")
    # Shared directory: valid front-matter under the same name.
    (shared / "prose-craft" / "voices" / "alpha").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "alpha" / "voice.md").write_text(
        _VALID_FRONTMATTER.format(name="alpha")
    )
    summaries = list_voices()
    names = {v.name for v in summaries}
    # Broken user voice blocks the shared fallback — neither appears
    # in the list. The breakage is surfaced through list_voice_errors.
    assert "alpha" not in names


def test_list_voice_errors_user_broken_blocks_shadow_shared(monkeypatch, tmp_path):
    """The malformed user voice above must be reported, not silently
    dropped, so the user knows their local ``voice.md`` is broken.

    Pairs with :func:`test_list_voices_user_broken_blocks_shadow_shared`:
    the user's broken ``voice.md`` is the one we want them to see in
    the error list, not the shared one (which is valid).
    """
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    (user / "alpha").mkdir(parents=True)
    (user / "alpha" / "voice.md").write_text("not yaml")
    (shared / "prose-craft" / "voices" / "alpha").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "alpha" / "voice.md").write_text(
        _VALID_FRONTMATTER.format(name="alpha")
    )
    errs = list_voice_errors()
    assert len(errs) == 1
    assert errs[0].name == "alpha"
    # The error path is the user-side file, not the shared one.
    assert str(user) in errs[0].error


def test_list_voice_errors_empty_user_dir_does_not_block_shared(monkeypatch, tmp_path):
    """An empty user directory must not suppress a shared voice error
    of the same name.

    Regression: ``list_voice_errors`` previously marked every
    directory as seen regardless of whether ``voice.md`` existed.
    An empty user directory then suppressed a shared voice
    directory of the same name even when the shared ``voice.md``
    failed to parse, hiding breakage from the user. The fix only
    marks the name seen after ``voice.md`` is confirmed present.
    """
    user = tmp_path / "user"
    shared = tmp_path / "shared"
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))
    monkeypatch.setenv("XDG_DATA_DIRS", str(shared))
    # User directory: exists, empty (no voice.md).
    (user / "alpha").mkdir(parents=True)
    # Shared directory: malformed voice.md under the same name.
    (shared / "prose-craft" / "voices" / "alpha").mkdir(parents=True)
    (shared / "prose-craft" / "voices" / "alpha" / "voice.md").write_text("not yaml")
    errs = list_voice_errors()
    assert len(errs) == 1
    assert errs[0].name == "alpha"
    assert str(shared) in errs[0].error
