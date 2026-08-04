"""Prose analyst agent."""

from __future__ import annotations

from prose_craft.voices.audience import ResolvedAudience

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import ProseDiagnostic
from prose_craft.agents.tools import (
    read_file,
    run_clause_density_tool,
    run_dispersion_tool,
    run_voice_check_tool,
)
from prose_craft.orchestrator.deps import AnalysisDeps
from prose_craft.orchestrator.prompts import ANALYST_SYSTEM_PROMPT, format_audience_block


def build_analyst(
    model: str, *, audience: ResolvedAudience | None = None
) -> Agent[AnalysisDeps, ProseDiagnostic]:
    """Construct the analyst agent."""
    rendered = ANALYST_SYSTEM_PROMPT.format(audience_block=format_audience_block(audience))
    return make_sub_agent(
        model=model,
        output_type=ProseDiagnostic,
        system_prompt=rendered,
        tools=[
            read_file,
            run_voice_check_tool,
            run_dispersion_tool,
            run_clause_density_tool,
        ],
    )
