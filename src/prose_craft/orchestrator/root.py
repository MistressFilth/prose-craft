"""ProseCraft composition root.

Constructed once per CLI invocation or MCP request. Owns model
selection, voice location, and the log level. Lazy-builds agents on
first access so that an importer pays only for the agents it actually
exercises.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic_ai import Agent

from prose_craft.config import get_model, get_voices_root

__all__ = ["ProseCraft"]

# Per-line `# type: ignore[import-untyped]` comments on the seven
# `from prose_craft.agents.<x> import build_<x>` statements below are
# TEMPORARY: the `prose_craft.agents.*` package and its factories do not
# exist yet on this branch (Tasks 22-29 land them). Remove every
# `# type: ignore[import-untyped]` in this file as part of the PR that
# introduces the matching agent module. Until then, the inline imports
# remain correct, the cache key still works, and the test injects the
# factory via `sys.modules` so we can exercise the lazy path.


class ProseCraft:
    """Single composition root for CLI + MCP + plugin-adapter callers."""

    def __init__(
        self,
        *,
        model: str | None = None,
        voices_root: Path | None = None,
        log_level: str = "INFO",
    ) -> None:
        self.model = model or get_model()
        self.voices_root = (voices_root or get_voices_root()).resolve()
        self.log_level = log_level
        self._agents: dict[str, Agent] = {}

    def _lazy(self, key: str, factory: Callable[[], Agent]) -> Agent:
        if key not in self._agents:
            self._agents[key] = factory()
        return self._agents[key]

    def analyst(self) -> Agent:
        from prose_craft.agents.analyst import build_analyst  # type: ignore[import-untyped]

        return self._lazy("analyst", lambda: build_analyst(self.model))

    def editor(self) -> Agent:
        from prose_craft.agents.editor import build_editor  # type: ignore[import-untyped]

        return self._lazy("editor", lambda: build_editor(self.model))

    def architect(self) -> Agent:
        from prose_craft.agents.architect import build_architect  # type: ignore[import-untyped]

        return self._lazy("architect", lambda: build_architect(self.model))

    def tune_diction(self) -> Agent:
        from prose_craft.agents.tune_diction import build_tune_diction  # type: ignore[import-untyped]

        return self._lazy("tune_diction", lambda: build_tune_diction(self.model))

    def voice_checker(self) -> Agent:
        from prose_craft.agents.voice_checker import build_voice_checker  # type: ignore[import-untyped]

        return self._lazy("voice_checker", lambda: build_voice_checker(self.model))

    def voice_stylist(self) -> Agent:
        from prose_craft.agents.voice_stylist import build_voice_stylist  # type: ignore[import-untyped]

        return self._lazy("voice_stylist", lambda: build_voice_stylist(self.model))

    def voice_composer(self) -> Agent:
        from prose_craft.agents.voice_composer import build_voice_composer  # type: ignore[import-untyped]

        return self._lazy(
            "voice_composer",
            lambda: build_voice_composer(self.model, self.voices_root),
        )
