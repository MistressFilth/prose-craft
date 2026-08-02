"""Tune-diction agent (Haiku)."""

from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import SubstitutionPlan
from prose_craft.agents.tools import read_file
from prose_craft.orchestrator.deps import TuneDeps
from prose_craft.orchestrator.prompts import TUNE_DICTION_SYSTEM_PROMPT


def build_tune_diction(model: str) -> Agent[TuneDeps, SubstitutionPlan]:
    """Construct the tune-diction agent."""
    return make_sub_agent(
        model=model,
        output_type=SubstitutionPlan,
        system_prompt=TUNE_DICTION_SYSTEM_PROMPT,
        tools=[read_file],
    )
