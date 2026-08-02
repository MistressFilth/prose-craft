"""Voice composer agent (Opus)."""

from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai_harness.memory import FileStore, Memory

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import VoiceDelta
from prose_craft.agents.tools import (
    apply_voice_delta,
    list_voices,
    read_voice,
    write_voice,
)
from prose_craft.orchestrator.deps import ComposerDeps
from prose_craft.orchestrator.prompts import VOICE_COMPOSER_SYSTEM_PROMPT


def build_voice_composer(
    model: str,
    voices_root: Path,
) -> Agent[ComposerDeps, list[VoiceDelta]]:
    """Construct the voice-composer agent.

    The composer is the only agent with a harness ``Memory`` capability
    so the wizard can resume across CLI invocations. Memory is backed by
    a persistent ``FileStore`` rooted under ``voices_root`` so the
    resume state survives process exit.

    Per the spec's Agent Contracts table, the composer is the one agent
    that does NOT receive ``read_file``; instead it operates through the
    voice-specific IO tools (``read_voice``, ``write_voice``,
    ``list_voices``, ``apply_voice_delta``).
    """
    store_path = voices_root / ".composer-state"
    store_path.mkdir(parents=True, exist_ok=True)
    capabilities = [Memory(namespace="prose-craft", store=FileStore(store_path))]

    return make_sub_agent(
        model=model,
        output_type=list[VoiceDelta],
        system_prompt=VOICE_COMPOSER_SYSTEM_PROMPT,
        tools=[
            read_voice,
            write_voice,
            list_voices,
            apply_voice_delta,
        ],
        capabilities=capabilities,
    )
