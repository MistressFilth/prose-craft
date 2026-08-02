"""Voice stylist agent (Sonnet)."""

from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import DraftResult
from prose_craft.agents.tools import read_file
from prose_craft.orchestrator.deps import StylistDeps
from prose_craft.orchestrator.prompts import VOICE_STYLIST_SYSTEM_PROMPT


def build_voice_stylist(model: str) -> Agent[StylistDeps, DraftResult]:
    """Construct the voice-stylist agent."""
    return make_sub_agent(
        model=model,
        output_type=DraftResult,
        system_prompt=VOICE_STYLIST_SYSTEM_PROMPT,
        tools=[read_file],
    )
