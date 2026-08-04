"""Voice composer agent (Opus)."""

from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai_harness.memory import FileStore, Memory

from prose_craft.agents.base import make_sub_agent
from prose_craft.agents.results import VoiceDelta
from prose_craft.agents.tools import bind_composer_tools
from prose_craft.orchestrator.deps import ComposerDeps
from prose_craft.orchestrator.prompts import VOICE_COMPOSER_SYSTEM_PROMPT, format_audience_block
from prose_craft.voices.audience import ResolvedAudience


def build_voice_composer(
    model: str,
    voices_root: Path,
    *,
    audience: ResolvedAudience | None = None,
) -> Agent[ComposerDeps, list[VoiceDelta]]:
    """Construct the voice-composer agent.

    The composer is the only agent with a harness ``Memory`` capability
    so the wizard can resume across CLI invocations. Memory is backed
    by a persistent ``FileStore`` rooted under ``voices_root`` so the
    resume state survives process exit.

    Per the spec's Agent Contracts table, the composer is the one agent
    that does NOT receive ``read_file``; instead it operates through the
    voice-specific IO tools (``load_voice``, ``read_voice``,
    ``write_voice``, ``list_voices``, ``apply_voice_delta``). The voice
    tools are bound to ``voices_root`` via :func:`bind_composer_tools`
    so a configured root is used instead of the process-wide default.

    Pipeline: ``load_voice`` fetches the profile, the model reasons
    about it, ``apply_voice_delta`` produces a delta against the live
    profile (without round-tripping through ``write_voice``), then
    ``write_voice`` persists. ``read_voice`` exposes the prose body
    separately so the model can surface a writer's literal choices.
    """
    root = Path(voices_root)
    store_path = root / ".composer-state"
    store_path.mkdir(parents=True, exist_ok=True)
    capabilities = [Memory(namespace="prose-craft", store=FileStore(store_path))]

    tools = bind_composer_tools(root)
    rendered = VOICE_COMPOSER_SYSTEM_PROMPT.format(audience_block=format_audience_block(audience))

    return make_sub_agent(
        model=model,
        output_type=list[VoiceDelta],
        system_prompt=rendered,
        tools=[
            tools["load_voice"],
            tools["read_voice"],
            tools["write_voice"],
            tools["list_voices"],
            tools["apply_voice_delta"],
        ],
        capabilities=capabilities,
    )
