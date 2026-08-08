"""Behavioral tests for the voice check and voice init subcommands."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from typer.testing import CliRunner

from prose_craft.cli import app

runner = CliRunner()


def _write_voice(root: Path, name: str) -> Path:
    vdir = root / name
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "voice.md").write_text(
        f"---\nvoice: {name}\nversion: 1\ncreated: 2026-08-01\nupdated: 2026-08-01\n"
        "register:\n  funny_serious: null\ndiction:\n  banned: [utilize]\nrhythm: {}\n"
        "syntax: {}\nlexicon: {}\nstructure: {}\n---\n",
        encoding="utf-8",
    )
    return vdir / "voice.md"


def test_voice_check_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    _write_voice(tmp_path, "MistressFilth")
    draft = tmp_path / "p.md"
    draft.write_text("We will utilize this.", encoding="utf-8")
    result = runner.invoke(
        app, ["voice", "check", str(draft), "--voice", "MistressFilth", "--json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "mechanical" in data


def test_voice_init_creates_template(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    result = runner.invoke(app, ["voice", "init", "newv"])
    assert result.exit_code == 0
    assert (tmp_path / "newv" / "voice.md").exists()


def test_compose_repl_fresh_init_uses_template(monkeypatch, tmp_path: Path) -> None:
    """Running the compose REPL on a missing voice scaffolds from the
    template, including the audiences block.

    Deviations from the brief (full rationale in the task report):
    - ``model="test"`` (pydantic-ai TestModel) replaces ``"test-model"``:
      pydantic-ai raises ``UserError`` on any model name it does not
      recognise, including ``"test-model"``.
    - ``typer.prompt`` is stubbed via ``monkeypatch.setattr`` because
      the bare REPL call hangs on stdin without a CliRunner.
    - ``ProseCraft.voice_composer`` is stubbed to return a fake agent
      that emits a deterministic ``VoiceDelta`` so the loop completes
      one cycle (driving a ``write_voice`` call). Before the refactor
      the write uses the empty ``VoiceProfile(...)`` constructor (no
      ``audiences:`` block); after the refactor it uses
      ``init_from_template`` (which carries the ``audiences:`` block).
    """
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(tmp_path))
    from prose_craft import cli as cli_mod
    from prose_craft.cli import _voice_compose_repl
    from prose_craft.agents.results import VoiceDelta
    from prose_craft.orchestrator.root import ProseCraft

    # Stub interactive prompts so the REPL doesn't block on stdin:
    # - "(answer)" prompt returns "" (default) so the loop advances and
    #   the agent runs.
    # - "(accept / modify ...)" prompt returns "accept" so the cycle
    #   writes the profile before moving to the next field.
    def _fake_prompt(*args, **kwargs):
        text = args[0] if args else ""
        return "accept" if text.startswith("(accept") else ""

    monkeypatch.setattr(cli_mod.typer, "prompt", _fake_prompt)

    # Stub the LLM-backed composer so the test doesn't need a real model.
    class _StubResult:
        def __init__(self) -> None:
            self.output = [VoiceDelta(field="purpose", value="stub", prompt="stub")]

    class _StubAgent:
        def run_sync(self, *_args, **_kwargs):
            return _StubResult()

    monkeypatch.setattr(ProseCraft, "voice_composer", lambda self, audience=None: _StubAgent())

    _voice_compose_repl(name="newv", root=tmp_path, model="test")

    voice_md = tmp_path / "newv" / "voice.md"
    assert voice_md.exists()
    text = voice_md.read_text(encoding="utf-8")
    assert "audiences:" in text
    assert "private:" in text
    assert "team:" in text
    assert "external:" in text

    # The brief's text-substring assertions above incidentally pass even
    # when the profile carries an empty ``audiences: {}`` block, because
    # the old fresh-init branch also embeds the full template (with its
    # own front-matter) as the prose body. Parse the *first* YAML
    # front-matter so we are verifying the profile, not the body.
    match = re.match(r"^---\n(.+?)\n---\n", text, re.DOTALL)
    assert match is not None, "voice.md is missing a YAML front-matter"
    front_matter = yaml.safe_load(match.group(1))
    audiences = front_matter.get("audiences") or {}
    assert "private" in audiences, audiences
    assert "team" in audiences, audiences
    assert "external" in audiences, audiences
