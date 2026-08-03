"""Tune-diction agent (Haiku)."""

from __future__ import annotations

from prose_craft.voices.audience import ResolvedAudience

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import SubstitutionPlan
from prose_craft.agents.tools import load_voice_diction, read_file
from prose_craft.orchestrator.deps import TuneDeps
from prose_craft.orchestrator.prompts import TUNE_DICTION_SYSTEM_PROMPT, format_audience_block


def build_tune_diction(model: str, *, audience: ResolvedAudience | None = None) -> Agent[TuneDeps, SubstitutionPlan]:
    """Construct the tune-diction agent."""
    rendered = TUNE_DICTION_SYSTEM_PROMPT.format(audience_block=format_audience_block(audience))
    return make_sub_agent(
        model=model,
        output_type=SubstitutionPlan,
        system_prompt=rendered,
        tools=[read_file, load_voice_diction],
    )
