"""Tests for prose_craft.agents.voice_composer.build_voice_composer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelMessage, ModelResponse, RunContext, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from prose_craft.agents.tools import (
    apply_voice_delta,
    list_voices,
    read_voice,
    write_voice,
)
from prose_craft.agents.voice_composer import build_voice_composer
from prose_craft.orchestrator.deps import ComposerDeps


def _function_model_returning_json(payload: list[dict[str, Any]]):
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # pydantic-ai 2.22.0 wraps non-model output types in a TypedDict
        # keyed by "response"; for list[VoiceDelta] the FunctionModel
        # must therefore return {"response": [...]} for the validator
        # to unpack the list.
        wrapped = {"response": payload}
        return ModelResponse(parts=[TextPart(json.dumps(wrapped))])

    return FunctionModel(fn)


def _make_ctx(deps: Any) -> RunContext[Any]:
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def test_voice_composer_returns_deltas(tmp_path: Path):
    # Use pydantic-ai's "test" sentinel so the agent constructs without a
    # real provider; the FunctionModel override below drives the run.
    agent = build_voice_composer("test", tmp_path)
    deps = ComposerDeps(name="dnova", current_field="purpose")
    payload = [
        {"field": "purpose", "value": "formal memos", "prompt": "What is this voice for?"},
    ]
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Compose step.", deps=deps)
    assert len(result.output) == 1
    assert result.output[0].field == "purpose"
    assert result.output[0].value == "formal memos"


def test_voice_composer_toolset_matches_spec():
    """Per spec: composer is the one agent WITHOUT read_file; uses voice IO tools."""
    agent = build_voice_composer("test", Path("/tmp/voices"))
    toolset = agent.toolsets[0]
    assert set(toolset.tools) == {
        read_voice.__name__,
        write_voice.__name__,
        list_voices.__name__,
        apply_voice_delta.__name__,
    }
    # Composer must not have read_file (per spec).
    assert "read_file" not in toolset.tools


def test_voice_composer_apply_voice_delta_round_trip(tmp_path: Path, monkeypatch):
    """apply_voice_delta + write_voice + re-read yields the updated profile.

    Builds a real voice.md, applies a delta, writes the result, and
    reads it back through ``load_voice`` semantics (the same path
    ``read_voice`` uses internally).
    """
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "dnova"
    voice_dir.mkdir(parents=True)
    voice_md = voice_dir / "voice.md"
    voice_md.write_text(
        "---\n"
        "voice: dnova\n"
        "version: 1\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "register:\n"
        "  funny_serious: 0.5\n"
        "diction:\n"
        "  default_balance: 'germanic-leaning'\n"
        "  banned: []\n"
        "  preferred: []\n"
        "  germanic_for: []\n"
        "  latinate_for: []\n"
        "  inherit_lexicons: []\n"
        "rhythm:\n"
        "  target_mean_sentence: null\n"
        "  target_variation: null\n"
        "  paragraph_shape: null\n"
        "  one_sentence_paragraphs: null\n"
        "  forbidden_patterns: []\n"
        "syntax:\n"
        "  em_dashes: null\n"
        "  colons: null\n"
        "  semicolons: null\n"
        "  parentheticals: null\n"
        "  fragments: null\n"
        "  bullets: null\n"
        "  questions: null\n"
        "lexicon:\n"
        "  pet_phrases: []\n"
        "  characteristic_openers: []\n"
        "  characteristic_closers: []\n"
        "  taboo_phrases: []\n"
        "structure:\n"
        "  opening: null\n"
        "  closing: null\n"
        "  transitions: null\n"
        "  emphasis: null\n"
        "  citations: null\n"
        "purpose: 'old purpose'\n"
        "---\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voices_root))

    agent = build_voice_composer("test", voices_root)
    toolset = agent.toolsets[0]

    # Load the current profile via prose_craft.voices.io directly; the
    # agent's read_voice tool returns the prose body, not the profile.
    from prose_craft.voices.io import read_voice as _io_read_voice

    profile = _io_read_voice("dnova")
    current_json = profile.model_dump_json()
    ctx = _make_ctx(ComposerDeps(name="dnova"))

    # Apply a delta that updates the purpose field.
    apply_tool = toolset.tools[apply_voice_delta.__name__]
    delta_json = json.dumps(
        {"field": "purpose", "value": "new purpose", "prompt": "Why this voice?"}
    )
    updated_json = apply_tool.function(ctx, "dnova", current_json, delta_json)
    assert "new purpose" in updated_json

    # Write the updated profile back to disk.
    write_tool = toolset.tools[write_voice.__name__]
    status = write_tool.function(ctx, "dnova", updated_json)
    assert status.startswith("wrote ")

    # Re-read and verify the delta was persisted.
    reloaded = _io_read_voice("dnova")
    assert reloaded.purpose == "new purpose"


def test_voice_composer_list_voices_tool_runs(tmp_path: Path, monkeypatch):
    """list_voices returns JSON-serialized VoiceSummary entries."""
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "dnova"
    voice_dir.mkdir(parents=True)
    (voice_dir / "voice.md").write_text(
        "---\n"
        "voice: dnova\n"
        "version: 1\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "register:\n"
        "  funny_serious: 0.5\n"
        "diction:\n"
        "  default_balance: 'germanic-leaning'\n"
        "  banned: []\n"
        "  preferred: []\n"
        "  germanic_for: []\n"
        "  latinate_for: []\n"
        "  inherit_lexicons: []\n"
        "rhythm:\n"
        "  target_mean_sentence: null\n"
        "  target_variation: null\n"
        "  paragraph_shape: null\n"
        "  one_sentence_paragraphs: null\n"
        "  forbidden_patterns: []\n"
        "syntax:\n"
        "  em_dashes: null\n"
        "  colons: null\n"
        "  semicolons: null\n"
        "  parentheticals: null\n"
        "  fragments: null\n"
        "  bullets: null\n"
        "  questions: null\n"
        "lexicon:\n"
        "  pet_phrases: []\n"
        "  characteristic_openers: []\n"
        "  characteristic_closers: []\n"
        "  taboo_phrases: []\n"
        "structure:\n"
        "  opening: null\n"
        "  closing: null\n"
        "  transitions: null\n"
        "  emphasis: null\n"
        "  citations: null\n"
        "---\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PROSE_CRAFT_VOICES_ROOT", str(voices_root))
    agent = build_voice_composer("test", voices_root)
    toolset = agent.toolsets[0]
    tool = toolset.tools[list_voices.__name__]
    ctx = _make_ctx(ComposerDeps(name="dnova"))
    payload = json.loads(tool.function(ctx))
    assert any(item["name"] == "dnova" for item in payload)
