"""CLI flag wiring for voice draft / edit / check."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from prose_craft.cli import app
from prose_craft.voices.io import write_voice
from prose_craft.voices.model import (
    AudienceCeiling,
    AudiencesBlock,
    DictionConfig,
    LexiconConfig,
    RegisterAxes,
    RhythmConfig,
    StructureConfig,
    SyntaxConfig,
    VoiceProfile,
)


def _make_voice(
    voice_root: Path,
    name: str,
    *,
    audiences: AudiencesBlock | None = None,
) -> Path:
    """Write a minimal voice profile with the given audiences block."""
    voice_dir = voice_root / name
    voice_dir.mkdir(parents=True, exist_ok=True)
    profile = VoiceProfile(
        voice=name,
        created=date(2026, 8, 1),
        updated=date(2026, 8, 1),
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
        audiences=audiences or AudiencesBlock(),
    )
    return write_voice(profile, root=voice_root)


class FakeAgent:
    """Stub agent that captures deps and returns a DraftResult-shaped object."""

    def __init__(self) -> None:
        self.deps: object | None = None

    def run_sync(self, prompt: str, deps: object):  # noqa: ARG002
        self.deps = deps
        from prose_craft.agents.results import DraftResult

        return type("R", (), {"output": DraftResult(text="x", change_log="")})()


def test_voice_draft_passes_audience_to_stylist(tmp_path: Path, monkeypatch) -> None:
    voice_root = tmp_path / "voices"
    _make_voice(
        voice_root,
        "test",
        audiences=AudiencesBlock(
            private=AudienceCeiling(severity_ceiling=5),
            team=AudienceCeiling(severity_ceiling=3),
        ),
    )

    agent = FakeAgent()

    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voice_root))
    with patch("prose_craft.orchestrator.root.ProseCraft.voice_stylist", return_value=agent):
        result = CliRunner().invoke(
            app,
            ["voice", "draft", "test", "--audience", "team", "brief text"],
        )
    assert result.exit_code == 0, result.output
    audience = getattr(agent.deps, "audience", None)
    assert audience is not None
    assert audience.name == "team"
    assert audience.source == "cli"


def test_voice_edit_passes_audience_to_stylist(tmp_path: Path, monkeypatch) -> None:
    voice_root = tmp_path / "voices"
    _make_voice(
        voice_root,
        "test",
        audiences=AudiencesBlock(external=AudienceCeiling(severity_ceiling=4)),
    )
    target = tmp_path / "draft.md"
    target.write_text("hello", encoding="utf-8")

    agent = FakeAgent()

    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voice_root))
    with patch("prose_craft.orchestrator.root.ProseCraft.voice_stylist", return_value=agent):
        result = CliRunner().invoke(
            app,
            ["voice", "edit", str(target), "--voice", "test", "--audience", "external"],
        )
    assert result.exit_code == 0, result.output
    audience = getattr(agent.deps, "audience", None)
    assert audience is not None
    assert audience.name == "external"


def test_voice_draft_invalid_audience_exits_2(tmp_path: Path, monkeypatch) -> None:
    voice_root = tmp_path / "voices"
    _make_voice(
        voice_root,
        "test",
        audiences=AudiencesBlock(team=AudienceCeiling()),
    )

    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voice_root))
    result = CliRunner().invoke(
        app,
        ["voice", "draft", "test", "--audience", "missing", "brief"],
    )
    assert result.exit_code == 2
    assert "missing" in result.output


def test_voice_edit_invalid_audience_exits_2(tmp_path: Path, monkeypatch) -> None:
    voice_root = tmp_path / "voices"
    _make_voice(
        voice_root,
        "test",
        audiences=AudiencesBlock(team=AudienceCeiling()),
    )
    target = tmp_path / "draft.md"
    target.write_text("hello", encoding="utf-8")

    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voice_root))
    result = CliRunner().invoke(
        app,
        [
            "voice",
            "edit",
            str(target),
            "--voice",
            "test",
            "--audience",
            "missing",
        ],
    )
    assert result.exit_code == 2
    assert "missing" in result.output


def test_voice_draft_closed_audience_warns_but_proceeds(tmp_path: Path, monkeypatch) -> None:
    voice_root = tmp_path / "voices"
    _make_voice(
        voice_root,
        "test",
        audiences=AudiencesBlock(
            external=AudienceCeiling(closed=True, reason="internal only"),
        ),
    )

    agent = FakeAgent()

    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voice_root))
    with patch("prose_craft.orchestrator.root.ProseCraft.voice_stylist", return_value=agent):
        result = CliRunner().invoke(
            app,
            ["voice", "draft", "test", "--audience", "external", "brief"],
        )
    assert result.exit_code == 0
    assert "closed" in (result.stderr or "")


def test_voice_check_uses_audience(tmp_path: Path, monkeypatch) -> None:
    voice_root = tmp_path / "voices"
    _make_voice(
        voice_root,
        "test",
        audiences=AudiencesBlock(
            private=AudienceCeiling(severity_ceiling=5),
            team=AudienceCeiling(severity_ceiling=3),
        ),
    )
    target = tmp_path / "draft.md"
    target.write_text("test prose", encoding="utf-8")
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voice_root))
    result = CliRunner().invoke(
        app,
        ["voice", "check", str(target), "--voice", "test", "--audience", "team"],
    )
    assert result.exit_code == 0, result.output


def test_voice_check_invalid_audience_exits_2(tmp_path: Path, monkeypatch) -> None:
    voice_root = tmp_path / "voices"
    _make_voice(
        voice_root,
        "test",
        audiences=AudiencesBlock(team=AudienceCeiling()),
    )
    target = tmp_path / "draft.md"
    target.write_text("test prose", encoding="utf-8")
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voice_root))
    result = CliRunner().invoke(
        app,
        ["voice", "check", str(target), "--voice", "test", "--audience", "missing"],
    )
    assert result.exit_code == 2
    assert "missing" in result.output


def test_voice_draft_threads_voices_root_to_prose_craft(tmp_path, monkeypatch) -> None:
    """--voices-root flows through ProseCraft() so the agent loads from the right root.

    Two voice roots are arranged so the same voice name resolves to
    different profiles: ``default_root`` has the voice, ``custom_root``
    does not. With ``--voices-root custom_root``, the CLI must call
    ``ProseCraft(voices_root=custom_root)`` so the agent's bound tools
    read from the configured root and find the voice.
    """
    default_root = tmp_path / "default"
    custom_root = tmp_path / "custom"
    default_root.mkdir()
    custom_root.mkdir()

    # Place a voice in custom_root only; the default root has none.
    profile = VoiceProfile(
        voice="custom-only",
        created=date(2026, 8, 1),
        updated=date(2026, 8, 1),
        register=RegisterAxes(),
        diction=DictionConfig(),
        rhythm=RhythmConfig(),
        syntax=SyntaxConfig(),
        lexicon=LexiconConfig(),
        structure=StructureConfig(),
        audiences=AudiencesBlock(team=AudienceCeiling(severity_ceiling=3)),
    )
    write_voice(profile, root=custom_root)

    agent = FakeAgent()

    # PROSE_CRAFT_VOICES_ROOT points at the empty default root;
    # --voices-root must override it.
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(default_root))
    with patch("prose_craft.cli.ProseCraft") as craft_cls:
        craft_cls.return_value.voice_stylist.return_value = agent
        result = CliRunner().invoke(
            app,
            [
                "voice",
                "draft",
                "custom-only",
                "--voices-root",
                str(custom_root),
                "brief text",
            ],
        )

    assert result.exit_code == 0, result.output
    # ``ProseCraft`` was called with the custom root, not the env-default.
    assert craft_cls.call_args.kwargs.get("voices_root") == custom_root
