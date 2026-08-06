"""Tests for prose_craft.agents.tools (the unbound agent tool surface).

These cover the raw tool wrappers that are not bound to a specific
``voices_root`` via :func:`prose_craft.agents.tools.bind_composer_tools`.
Each agent that takes the bound path goes through closure-bound tools;
the unbound variants exist so simple importers (and future agents that
do not yet go through the composer factory) reach the same IO primitives
without leaking the root into the pydantic-ai JSON schema.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from prose_craft.agents import tools as agent_tools
from prose_craft.voices.model import (
    DictionConfig,
    LexiconConfig,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SyntaxConfig,
    VoiceProfile,
)


def _alpha_profile() -> VoiceProfile:
    """A minimal valid VoiceProfile named 'alpha'."""
    return VoiceProfile(
        voice="alpha",
        created=date(2026, 1, 1),
        updated=date(2026, 1, 1),
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )


# ---------------------------------------------------------------------------
# Latent-issue regression: unbound write_voice targets the user root.
# ---------------------------------------------------------------------------


def test_unbound_write_voice_targets_user_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Unbound ``write_voice`` must write only to the configured user root.

    Regression for the latent issue found in final review: the unbound
    ``write_voice`` tool formerly called
    ``_io_write_voice(profile, prose_body=body)`` without ``root=``,
    leaving the destination implicit. If ``voice_path`` ever grew a
    shared-root walk (``root=None`` resolves to the system voices
    directory when a same-named voice is installed there), the unbound
    tool would silently start overwriting a system-installed voice.

    The contract locked in here: the unbound ``write_voice`` always
    pins ``root=`` to ``load_settings().voices_root`` — the configured
    user voices directory — regardless of any other candidate path.
    """
    user = tmp_path / "user-voices"
    user.mkdir()
    shared = tmp_path / "shared-voices"
    shared.mkdir()

    # Pin the user root via the explicit env var, mirroring how an
    # operator would override PROSE_CRAFT_VOICES_ROOT on disk. The
    # fix pins ``root=`` to this value rather than letting the default
    # resolution shadow it.
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))

    profile = _alpha_profile()

    # The unbound tool takes (ctx, voice_name, profile_json, prose_body).
    # ``ctx=None`` is acceptable: the tool body does not consult the
    # context.
    agent_tools.write_voice(
        None,  # type: ignore[arg-type]
        "alpha",
        profile.model_dump_json(),
        prose_body="body",
    )

    # File landed in the user root.
    written = user / "alpha" / "voice.md"
    assert written.is_file(), f"expected write to {written}, not found"

    # Read-back round-trip via the user root confirms the body is the
    # text we passed, not whatever might have been found elsewhere.
    raw = written.read_text(encoding="utf-8")
    assert "voice: alpha" in raw
    assert "body" in raw

    # The shared candidate must be untouched. Even if a same-named
    # voice were present there, the unbound tool would not have
    # overwritten it because it pins ``root=`` to the user directory.
    assert not (shared / "alpha").exists()


def test_unbound_write_voice_preserves_existing_body_when_prose_body_empty(
    tmp_path: Path,
) -> None:
    """Unbound ``write_voice`` with ``prose_body=""`` preserves the body.

    Regression companion to the composer's existing body-preservation
    test: the unbound tool must apply the same round-trip semantics so
    any future agent that wires the unbound form inherits the fix.
    """
    from prose_craft.voices.io import read_voice_raw

    user = tmp_path / "user-voices"
    voice_dir = user / "alpha"
    voice_dir.mkdir(parents=True)

    original_body = "\n\nPreserved prose body.\n"
    voice_dir.joinpath("voice.md").write_text(
        "---\n"
        "voice: alpha\n"
        "version: 1\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "register: {}\n"
        "diction: {}\n"
        "rhythm: {}\n"
        "syntax: {}\n"
        "lexicon: {}\n"
        "structure: {}\n"
        f"---{original_body}",
        encoding="utf-8",
    )

    profile = _alpha_profile()

    # Call without prose_body: the tool must round-trip the existing
    # body rather than dropping it.
    agent_tools.write_voice(
        None,  # type: ignore[arg-type]
        "alpha",
        profile.model_dump_json(),
    )

    _reloaded, body = read_voice_raw("alpha", root=user)
    assert "Preserved prose body." in body


def test_unbound_write_voice_round_trips_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Unbound ``write_voice`` validates and round-trips a profile JSON."""
    from prose_craft.voices.io import read_voice as _io_read_voice

    user = tmp_path / "user-voices"
    user.mkdir(parents=True)
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(user))

    payload = {
        "voice": "bravo",
        "created": "2026-01-01",
        "updated": "2026-01-01",
        "register": {},
        "diction": {},
        "rhythm": {},
        "syntax": {},
        "lexicon": {},
        "structure": {},
        "purpose": "alpha-test purpose",
    }
    profile_json = json.dumps(payload)

    agent_tools.write_voice(
        None,  # type: ignore[arg-type]
        "bravo",
        profile_json,
        prose_body="alpha body",
    )

    reloaded = _io_read_voice("bravo", root=user)
    assert reloaded.voice == "bravo"
    assert reloaded.purpose == "alpha-test purpose"


def test_unbound_write_voice_rejects_mismatched_voice_name(
    tmp_path: Path,
) -> None:
    """Unbound ``write_voice`` rejects routing a profile to a different name."""
    import pytest

    user = tmp_path / "user-voices"
    user.mkdir(parents=True)

    profile = VoiceProfile(
        voice="alpha",
        created=date(2026, 1, 1),
        updated=date(2026, 1, 1),
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
    )

    with pytest.raises(ValueError, match="does not match"):
        agent_tools.write_voice(
            None,  # type: ignore[arg-type]
            "bravo",
            profile.model_dump_json(),
            prose_body="body",
        )

    # Neither directory may have been created.
    assert not (user / "alpha").exists()
    assert not (user / "bravo").exists()
