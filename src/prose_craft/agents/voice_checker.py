"""Voice checker agent (Haiku, read-only)."""

from __future__ import annotations

from pydantic_ai import Agent

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.tools import load_voice, read_file
from prose_craft.orchestrator.deps import VoiceDeps
from prose_craft.orchestrator.prompts import VOICE_CHECKER_SYSTEM_PROMPT
from prose_craft.voices.check import VoiceVerdict


def build_voice_checker(model: str) -> Agent[VoiceDeps, VoiceVerdict]:
    """Construct the voice-checker agent."""
    return make_sub_agent(
        model=model,
        output_type=VoiceVerdict,
        system_prompt=VOICE_CHECKER_SYSTEM_PROMPT,
        tools=[read_file, load_voice],
    )
