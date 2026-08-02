"""Tools shared by every agent.

These are thin pydantic-ai-compatible wrappers over the deterministic
primitives in ``prose_craft.analysis`` and ``prose_craft.voices``.
The spec's Agent Contracts table (lines 70-79 of
``docs/superpowers/specs/2026-08-01-prose-craft-pydantic-ai-design.md``)
assigns a specific subset of these tools to each agent.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from pydantic_ai import RunContext

from prose_craft.analysis.clause_density import measure_clause_density
from prose_craft.analysis.dispersion import measure_set
from prose_craft.analysis.sentences import tokenize_words
from prose_craft.voices.check import check_voice
from prose_craft.voices.io import (
    list_voices as _io_list_voices,
    read_voice as _io_read_voice,
    read_voice_raw,
    write_voice as _io_write_voice,
)
from prose_craft.voices.model import DictionConfig, VoiceProfile


def read_file(ctx: RunContext[Any], file_path: str) -> str:
    """Read a UTF-8 file and return its contents.

    Resolves the path; raises FileNotFoundError for missing files. The
    agent surface always passes a string for portability.
    """
    path = Path(file_path)
    return path.read_text(encoding="utf-8")


def run_voice_check_tool(
    ctx: RunContext[Any],
    text: str,
    voice_name: str,
) -> str:
    """Run the deterministic voice checker against ``text``.

    Loads the named ``VoiceProfile`` from the standard voice root
    (``PROSE_CRAFT_VOICES_ROOT`` env var or platform default) and
    returns the JSON-serialized ``VoiceVerdict``.

    The agent decides whether to layer model-judged entries on top; this
    primitive returns only the deterministic mechanical + statistical
    findings plus the agent-required prompts surfaced for the model.
    """
    profile = _io_read_voice(voice_name)
    verdict = check_voice(text, profile)
    return verdict.model_dump_json()


def run_dispersion_tool(
    ctx: RunContext[Any],
    new_draft: str,
    sibling_paths: list[str],
) -> str:
    """Measure cross-draft dispersion for ``new_draft`` against siblings.

    Reads each path under ``sibling_paths`` as UTF-8 text and computes
    the lexical + structural dispersion profile against the new draft.
    Returns the JSON-serialized ``DispersionProfile``.

    Pass an empty ``sibling_paths`` list to measure the draft in
    isolation (``n=1`` profile with all-zero altitudes).
    """
    siblings = [Path(p).read_text(encoding="utf-8") for p in sibling_paths]
    profile = measure_set(new_draft, siblings)
    return profile.model_dump_json()


def run_clause_density_tool(
    ctx: RunContext[Any],
    text: str,
    voice_name: str | None = None,
) -> str:
    """Measure present participial clauses + agentless passives per 1k words.

    Returns the JSON-serialized ``ClauseDensity``. The ``voice_name``
    argument is reserved for future voice-aware measurement; today it
    is accepted but unused.
    """
    del voice_name  # Reserved for future voice-aware measurement.
    words = tokenize_words(text)
    density = measure_clause_density(text, words)
    return density.model_dump_json()


def load_voice_diction(
    ctx: RunContext[Any],
    voice_name: str,
) -> str:
    """Load the ``DictionConfig`` for ``voice_name`` and return it as JSON.

    Loads the full profile (cheap: one parse, no IO beyond the file)
    and returns only the ``diction`` sub-model. Useful for tune-diction
    weighting without handing the model the entire profile.
    """
    profile = _io_read_voice(voice_name)
    diction = DictionConfig.model_validate(profile.diction.model_dump())
    return diction.model_dump_json()


def load_voice(
    ctx: RunContext[Any],
    voice_name: str,
) -> str:
    """Load the full ``VoiceProfile`` for ``voice_name`` and return it as JSON.

    The prose body is not included — ``_io_read_voice`` discards it
    during parse. Use the ``read_voice`` tool if the body is needed.
    """
    profile = _io_read_voice(voice_name)
    return profile.model_dump_json()


def read_voice(ctx: RunContext[Any], voice_name: str) -> str:
    """Return the prose body of ``voice_name``'s voice.md (no front-matter).

    The body is the text after the closing ``---`` marker, preserved
    verbatim by ``read_voice_raw``. Useful for surfacing the
    voice-composer's literal prose choices to a follow-up step.
    """
    _profile, body = read_voice_raw(voice_name)
    return body


def write_voice(
    ctx: RunContext[Any],
    voice_name: str,
    profile_json: str,
) -> str:
    """Validate ``profile_json`` and persist the profile to voice.md.

    Round-trips through ``VoiceProfile.model_validate_json`` so the
    stored file always reflects the schema. The prose body is empty;
    the ``read_voice`` tool will yield an empty string. Returns a
    status line describing the write.
    """
    profile = VoiceProfile.model_validate_json(profile_json)
    path = _io_write_voice(profile, prose_body="")
    return f"wrote {path}"


def list_voices(ctx: RunContext[Any]) -> str:
    """List every voice under the voices root as JSON-serialized summaries.

    Each summary carries the voice's name and ``updated`` date.
    """
    summaries = _io_list_voices()
    if not summaries:
        return "[]"
    return "[" + ",".join(s.model_dump_json() for s in summaries) + "]"


def apply_voice_delta(
    ctx: RunContext[Any],
    voice_name: str,
    current_profile_json: str,
    delta_json: str,
) -> str:
    """Apply a ``VoiceDelta`` to a profile and return the updated profile JSON.

    The ``voice_name`` argument is currently accepted for interface
    symmetry but is not used to look up the profile — the caller
    supplies ``current_profile_json`` directly. The merge applies the
    delta's ``field`` -> ``value`` mapping onto the profile payload,
    then revalidates against the strict ``VoiceProfile`` schema. The
    ``updated`` date is set to today.

    Returns the updated profile as JSON so the caller can round-trip
    it back through ``write_voice``.
    """
    del voice_name  # Accepted for interface symmetry; not used here.
    profile = VoiceProfile.model_validate_json(current_profile_json)
    payload = profile.model_dump(mode="json")
    delta = _load_delta(delta_json)
    payload[delta.field] = delta.value
    payload["updated"] = date.today().isoformat()
    updated = VoiceProfile.model_validate(payload)
    return updated.model_dump_json()


def _load_delta(delta_json: str) -> Any:
    """Validate a VoiceDelta JSON document and return the typed delta.

    Importing ``VoiceDelta`` lazily avoids a top-level cycle between
    ``agents.results`` and ``agents.tools`` at import time.
    """
    from prose_craft.agents.results import VoiceDelta

    return VoiceDelta.model_validate_json(delta_json)
