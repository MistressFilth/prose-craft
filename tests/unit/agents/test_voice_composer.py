"""Tests for prose_craft.agents.voice_composer.build_voice_composer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai import ModelMessage, ModelResponse, RunContext, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from prose_craft.agents.results import VoiceDelta
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


def _seed_voice_md(voice_dir: Path, body_text: str = "", name: str = "MistressFilth") -> None:
    """Write a baseline voice.md into ``voice_dir`` with the given prose body."""
    voice_dir.mkdir(parents=True, exist_ok=True)
    (voice_dir / "voice.md").write_text(
        "---\n"
        f"voice: {name}\n"
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
        f"---{body_text}",
        encoding="utf-8",
    )


def test_voice_composer_returns_deltas(tmp_path: Path):
    # Use pydantic-ai's "test" sentinel so the agent constructs without a
    # real provider; the FunctionModel override below drives the run.
    agent = build_voice_composer("test", tmp_path)
    deps = ComposerDeps(name="MistressFilth", current_field="purpose")
    payload = [
        {"field": "purpose", "value": "formal memos", "prompt": "What is this voice for?"},
    ]
    with agent.override(model=_function_model_returning_json(payload)):
        result = agent.run_sync("Compose step.", deps=deps)
    assert len(result.output) == 1
    assert result.output[0].field == "purpose"
    assert result.output[0].value == "formal memos"


def test_voice_composer_toolset_matches_spec(tmp_path: Path):
    """Per spec: composer is the one agent WITHOUT read_file; uses voice IO tools.

    Voice-composer's toolset now includes ``load_voice`` so the agent
    can fetch the full profile for ``apply_voice_delta`` to mutate
    without round-tripping through ``write_voice``.
    """
    agent = build_voice_composer("test", tmp_path)
    toolset = agent.toolsets[0]
    assert set(toolset.tools) == {
        "load_voice",
        "read_voice",
        "write_voice",
        "list_voices",
        "apply_voice_delta",
    }
    # Composer must not have read_file (per spec).
    assert "read_file" not in toolset.tools


def test_voice_composer_apply_voice_delta_round_trip(tmp_path: Path):
    """load_voice -> apply_voice_delta -> write_voice persists the delta.

    Exercises the canonical composer pipeline through the bound tools
    exposed on the agent's toolset. Re-reading the voice after the
    round-trip yields the updated profile.
    """
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "MistressFilth"
    _seed_voice_md(voice_dir)

    agent = build_voice_composer("test", voices_root)
    toolset = agent.toolsets[0]
    ctx = _make_ctx(ComposerDeps(name="MistressFilth"))

    # 1. load_voice fetches the current profile.
    load_tool = toolset.tools["load_voice"]
    current_json = load_tool.function(ctx, "MistressFilth")
    current = json.loads(current_json)
    assert current["voice"] == "MistressFilth"
    assert current["purpose"] == "old purpose"

    # 2. apply_voice_delta produces an updated profile JSON.
    apply_tool = toolset.tools["apply_voice_delta"]
    delta_json = json.dumps(
        {"field": "purpose", "value": "new purpose", "prompt": "Why this voice?"}
    )
    updated_json = apply_tool.function(ctx, "MistressFilth", current_json, delta_json)
    assert "new purpose" in updated_json

    # 3. write_voice persists the updated profile.
    write_tool = toolset.tools["write_voice"]
    status = write_tool.function(ctx, "MistressFilth", updated_json)
    assert status.startswith("wrote ")

    # 4. Re-read the voice and verify the delta persisted.
    from prose_craft.voices.io import read_voice as _io_read_voice

    reloaded = _io_read_voice("MistressFilth", root=voices_root)
    assert reloaded.purpose == "new purpose"


def test_voice_composer_list_voices_tool_runs(tmp_path: Path):
    """list_voices returns JSON-serialized VoiceSummary entries."""
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "MistressFilth"
    _seed_voice_md(voice_dir)

    agent = build_voice_composer("test", voices_root)
    toolset = agent.toolsets[0]
    tool = toolset.tools["list_voices"]
    ctx = _make_ctx(ComposerDeps(name="MistressFilth"))
    payload = json.loads(tool.function(ctx))
    assert any(item["name"] == "MistressFilth" for item in payload)


# ---------------------------------------------------------------------------
# Critical fix regression: write_voice must preserve the prose body.
# ---------------------------------------------------------------------------


def test_write_voice_preserves_existing_body_when_prose_body_empty(tmp_path: Path):
    """write_voice with prose_body='' must NOT erase the existing body.

    Regression for the per-agent tool wrapping review's Critical
    finding: the tool previously persisted ``prose_body=""``
    unconditionally, destroying the body. The composer's
    ``write_voice`` is supposed to round-trip the profile, not
    destroy the body.
    """
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "MistressFilth"
    original_body = "\n\nThis is the original prose body. With a [bracket].\n"
    _seed_voice_md(voice_dir, body_text=original_body)

    agent = build_voice_composer("test", voices_root)
    toolset = agent.toolsets[0]
    ctx = _make_ctx(ComposerDeps(name="MistressFilth"))

    # Round-trip the profile through load_voice, leave it unchanged,
    # then write_voice without prose_body.
    load_tool = toolset.tools["load_voice"]
    current_json = load_tool.function(ctx, "MistressFilth")
    write_tool = toolset.tools["write_voice"]
    write_tool.function(ctx, "MistressFilth", current_json)

    # Re-read the raw voice.md; the body must still be intact.
    from prose_craft.voices.io import read_voice_raw

    _profile, body = read_voice_raw("MistressFilth", root=voices_root)
    assert "This is the original prose body." in body
    assert "[bracket]" in body


def test_write_voice_with_explicit_prose_body_overwrites(tmp_path: Path):
    """An explicit non-empty prose_body replaces the existing body."""
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "MistressFilth"
    _seed_voice_md(voice_dir, body_text="\nold body\n")

    agent = build_voice_composer("test", voices_root)
    toolset = agent.toolsets[0]
    ctx = _make_ctx(ComposerDeps(name="MistressFilth"))

    load_tool = toolset.tools["load_voice"]
    current_json = load_tool.function(ctx, "MistressFilth")

    write_tool = toolset.tools["write_voice"]
    write_tool.function(ctx, "MistressFilth", current_json, prose_body="\nnew body\n")

    from prose_craft.voices.io import read_voice_raw

    _profile, body = read_voice_raw("MistressFilth", root=voices_root)
    assert "new body" in body
    assert "old body" not in body


def test_write_voice_rejects_mismatched_voice_name(tmp_path: Path):
    """write_voice refuses a profile whose voice field does not match."""
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "alice"
    _seed_voice_md(voice_dir, name="alice")

    agent = build_voice_composer("test", voices_root)
    toolset = agent.toolsets[0]
    ctx = _make_ctx(ComposerDeps(name="alice"))

    load_tool = toolset.tools["load_voice"]
    alice_json = load_tool.function(ctx, "alice")
    # Try to write Alice's profile into the "bob" slot.
    write_tool = toolset.tools["write_voice"]
    with pytest.raises(ValueError, match="does not match"):
        write_tool.function(ctx, "bob", alice_json)

    # Bob's voice.md must not have been created.
    assert not (voice_dir.parent / "bob").exists()


# ---------------------------------------------------------------------------
# Important #3 regression: apply_voice_delta rejects 'voice' field edits.
# ---------------------------------------------------------------------------


def test_apply_voice_delta_rejects_voice_field(tmp_path: Path):
    """apply_voice_delta refuses any delta whose field is 'voice'."""
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "MistressFilth"
    _seed_voice_md(voice_dir)

    agent = build_voice_composer("test", voices_root)
    toolset = agent.toolsets[0]
    ctx = _make_ctx(ComposerDeps(name="MistressFilth"))

    load_tool = toolset.tools["load_voice"]
    current_json = load_tool.function(ctx, "MistressFilth")
    apply_tool = toolset.tools["apply_voice_delta"]
    delta_json = json.dumps({"field": "voice", "value": "bob", "prompt": "Rename"})
    with pytest.raises(ValueError, match="delta.field='voice'"):
        apply_tool.function(ctx, "MistressFilth", current_json, delta_json)


def test_apply_voice_delta_rejects_mismatched_voice_name(tmp_path: Path):
    """apply_voice_delta refuses a profile whose voice field does not match."""
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "alice"
    _seed_voice_md(voice_dir, name="alice")
    (voices_root / "bob").mkdir(exist_ok=True)

    agent = build_voice_composer("test", voices_root)
    toolset = agent.toolsets[0]
    ctx = _make_ctx(ComposerDeps(name="alice"))

    load_tool = toolset.tools["load_voice"]
    alice_json = load_tool.function(ctx, "alice")
    apply_tool = toolset.tools["apply_voice_delta"]
    delta_json = json.dumps({"field": "purpose", "value": "x", "prompt": "Why?"})
    with pytest.raises(ValueError, match="does not match"):
        apply_tool.function(ctx, "bob", alice_json, delta_json)


# ---------------------------------------------------------------------------
# Important #1 regression: composer tools honor configured voices_root.
# ---------------------------------------------------------------------------


def test_voice_composer_uses_configured_voices_root(tmp_path: Path, monkeypatch):
    """The composer's IO tools must read/write the configured voices_root.

    Regression for review Important #1: the voice tools previously
    fell back to the process-wide env default rather than the
    :class:`ProseCraft` instance's configured ``voices_root``. We
    construct a tmp_path root, seed a voice there, and exercise the
    composer's toolset WITHOUT setting ``PROSE_CRAFT_VOICES_ROOT``.
    """
    custom_root = tmp_path / "custom-voices"
    voice_dir = custom_root / "MistressFilth"
    _seed_voice_md(voice_dir)

    # Deliberately do NOT touch PROSE_CRAFT_VOICES_ROOT; the agent's
    # bound tools should use ``custom_root`` regardless.
    monkeypatch.delenv("PROSE_CRAFT_VOICES_ROOT", raising=False)

    agent = build_voice_composer("test", custom_root)
    toolset = agent.toolsets[0]
    ctx = _make_ctx(ComposerDeps(name="MistressFilth"))

    # load_voice finds the voice under the configured custom_root.
    load_tool = toolset.tools["load_voice"]
    profile_json = load_tool.function(ctx, "MistressFilth")
    assert "MistressFilth" in profile_json

    # list_voices returns the voice under the configured custom_root.
    list_tool = toolset.tools["list_voices"]
    payload = json.loads(list_tool.function(ctx))
    assert any(item["name"] == "MistressFilth" for item in payload)

    # write_voice writes to the configured custom_root.
    read_tool = toolset.tools["read_voice"]
    body = read_tool.function(ctx, "MistressFilth")
    write_tool = toolset.tools["write_voice"]
    write_tool.function(ctx, "MistressFilth", profile_json, prose_body=body)

    # Verify the file lives at the configured root, not the env default.
    assert (custom_root / "MistressFilth" / "voice.md").exists()


# ---------------------------------------------------------------------------
# Important #2 regression: end-to-end composer pipeline drives a real agent
# through load_voice -> apply_voice_delta -> write_voice.
# ---------------------------------------------------------------------------


def test_voice_composer_end_to_end_pipeline(tmp_path: Path):
    """Drive the composer via a real FunctionModel run.

    Validates that the model has access to ``load_voice``,
    ``read_voice``, ``write_voice``, ``list_voices``, and
    ``apply_voice_delta`` and that the resulting deltas round-trip
    through ``write_voice`` while preserving the existing prose body.
    """
    voices_root = tmp_path / "voices"
    voice_dir = voices_root / "MistressFilth"
    original_body = "\n\nOriginal prose body [bracket].\n"
    _seed_voice_md(voice_dir, body_text=original_body)

    agent = build_voice_composer("test", voices_root)

    # Drive the agent: it should return a single delta updating
    # ``purpose`` to "new purpose" while preserving the body.
    payload = [
        {
            "field": "purpose",
            "value": "new purpose",
            "prompt": "What is this voice for?",
        }
    ]

    captured: dict[str, Any] = {}

    def driver(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        # Capture which tools were offered to the model so we can
        # assert the full pipeline is available. ``info.function_tools``
        # is a list of ToolDefinition; extract the names.
        captured["tool_names"] = sorted(t.name for t in info.function_tools)
        wrapped = {"response": payload}
        return ModelResponse(parts=[TextPart(json.dumps(wrapped))])

    deps = ComposerDeps(name="MistressFilth", current_field="purpose")
    with agent.override(model=FunctionModel(driver)):
        result = agent.run_sync("Compose step.", deps=deps)

    assert result.output == [
        VoiceDelta(field="purpose", value="new purpose", prompt="What is this voice for?")
    ]

    # The agent's advertised toolset must include the full pipeline
    # (the Memory capability also registers a couple of memory tools;
    # we only assert the voice pipeline).
    expected_pipeline = {
        "load_voice",
        "read_voice",
        "write_voice",
        "list_voices",
        "apply_voice_delta",
    }
    assert expected_pipeline.issubset(set(captured["tool_names"]))

    # And the resulting VoiceDelta, applied + persisted through the
    # toolset, must yield the new purpose AND preserve the original body.
    agent_toolset = agent.toolsets[0]
    ctx = _make_ctx(deps)
    profile_json = agent_toolset.tools["load_voice"].function(ctx, "MistressFilth")
    delta_json = result.output[0].model_dump_json()
    updated_json = agent_toolset.tools["apply_voice_delta"].function(
        ctx, "MistressFilth", profile_json, delta_json
    )
    agent_toolset.tools["write_voice"].function(ctx, "MistressFilth", updated_json)

    from prose_craft.voices.io import read_voice as _io_read_voice
    from prose_craft.voices.io import read_voice_raw

    reloaded_profile = _io_read_voice("MistressFilth", root=voices_root)
    _reloaded_profile, reloaded_body = read_voice_raw("MistressFilth", root=voices_root)
    assert reloaded_profile.purpose == "new purpose"
    assert "Original prose body" in reloaded_body
    assert "[bracket]" in reloaded_body
