"""Voice checker agent (Haiku, read-only)."""

from __future__ import annotations

from prose_craft.voices.audience import ResolvedAudience

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.tools import load_voice, read_file
from prose_craft.orchestrator.deps import VoiceDeps
from prose_craft.orchestrator.prompts import VOICE_CHECKER_SYSTEM_PROMPT, format_audience_block
from prose_craft.voices.check import VoiceVerdict


def build_voice_checker(model: str, *, audience: ResolvedAudience | None = None) -> Agent[VoiceDeps, VoiceVerdict]:
    """Construct the voice-checker agent."""
    rendered = VOICE_CHECKER_SYSTEM_PROMPT.format(audience_block=format_audience_block(audience))
    return make_sub_agent(
        model=model,
        output_type=VoiceVerdict,
        system_prompt=rendered,
        tools=[read_file, load_voice],
    )
