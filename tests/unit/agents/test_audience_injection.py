"""Verify agent factories substitute the audience_block placeholder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prose_craft.agents.voice_stylist import build_voice_stylist
from prose_craft.orchestrator.root import ProseCraft
from prose_craft.voices.audience import ResolvedAudience


def test_voice_stylist_prompt_substitutes_audience_block():
    audience = ResolvedAudience(name="team", voice_name="v")
    captured: dict[str, str] = {}

    def fake_make_sub_agent(model, output_type, system_prompt, tools, **kwargs):
        captured["prompt"] = system_prompt
        return object()

    with patch("prose_craft.agents.voice_stylist.make_sub_agent", side_effect=fake_make_sub_agent):
        build_voice_stylist("test:model", audience=audience)

    assert "Audience: team" in captured["prompt"]
    assert "{audience_block}" not in captured["prompt"]


def test_voice_stylist_prompt_with_no_audience_renders_empty_block():
    captured: dict[str, str] = {}

    def fake_make_sub_agent(model, output_type, system_prompt, tools, **kwargs):
        captured["prompt"] = system_prompt
        return object()

    with patch("prose_craft.agents.voice_stylist.make_sub_agent", side_effect=fake_make_sub_agent):
        build_voice_stylist("test:model")

    assert "Audience context (may be empty):" in captured["prompt"]
    assert "{audience_block}" not in captured["prompt"]


def test_prose_craft_voice_stylist_threads_audience(tmp_path: Path) -> None:
    """`ProseCraft.voice_stylist(audience=...)` must forward audience to the agent factory."""
    audience = ResolvedAudience(name="team", voice_name="v")
    captured: dict[str, str] = {}

    def fake_make_sub_agent(model, output_type, system_prompt, tools, **kwargs):
        captured["prompt"] = system_prompt
        return object()

    craft = ProseCraft(voices_root=tmp_path)
    with patch(
        "prose_craft.agents.voice_stylist.make_sub_agent",
        side_effect=fake_make_sub_agent,
    ):
        craft.voice_stylist(audience=audience)

    assert "Audience: team" in captured["prompt"]
