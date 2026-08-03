"""Voice stylist agent (Sonnet)."""

from __future__ import annotations

from prose_craft.voices.audience import ResolvedAudience

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import DraftResult
from prose_craft.agents.tools import load_voice, read_file, run_voice_check_tool
from prose_craft.orchestrator.deps import StylistDeps
from prose_craft.orchestrator.prompts import VOICE_STYLIST_SYSTEM_PROMPT, format_audience_block


def build_voice_stylist(model: str, *, audience: ResolvedAudience | None = None) -> Agent[StylistDeps, DraftResult]:
    """Construct the voice-stylist agent."""
    rendered = VOICE_STYLIST_SYSTEM_PROMPT.format(audience_block=format_audience_block(audience))
    return make_sub_agent(
        model=model,
        output_type=DraftResult,
        system_prompt=rendered,
        tools=[read_file, load_voice, run_voice_check_tool],
    )
