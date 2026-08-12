"""Schema spot-check for the shipped lexicon / never-list YAMLs.

These tests lock in the contract advertised by
``claude-code/plugin/skills/voice-craft-reference/SKILL.md``: the
``microsoft`` lexicon and ``microsoft-simple-human`` never-list ship as
real YAML files under ``claude-code/plugin/voices/_lexicons/`` and
``_never_lists/``. Future edits to those files must keep the schema
contract, or these tests will fail loudly.
"""

from __future__ import annotations

from pathlib import Path

from prose_craft.voices.io import load_lexicon, load_never_list


PLUGIN_ROOT = Path(__file__).parent.parent.parent.parent / "claude-code" / "plugin" / "voices"


def test_microsoft_lexicon_parses_and_has_attributions() -> None:
    payload = load_lexicon("microsoft", root=PLUGIN_ROOT)
    assert isinstance(payload, dict)
    assert "attributions" in payload
    assert isinstance(payload["attributions"], list)
    assert payload["attributions"], "lexicon must carry at least one attribution"
    cc_by = [a for a in payload["attributions"] if a.get("license") == "CC BY 4.0"]
    assert cc_by, "lexicon must declare a CC BY 4.0 attribution"


def test_microsoft_simple_human_never_list_parses() -> None:
    payload = load_never_list("microsoft-simple-human", root=PLUGIN_ROOT)
    assert isinstance(payload, dict)
    assert payload.get("rules"), "never-list must carry a non-empty rules list"
    for entry in payload["rules"]:
        assert "id" in entry
        assert "rule" in entry
        assert entry.get("detection") == "agent-required"


def test_microsoft_simple_human_never_list_has_attributions() -> None:
    payload = load_never_list("microsoft-simple-human", root=PLUGIN_ROOT)
    attributions = payload.get("attributions")
    assert isinstance(attributions, list) and attributions
    cc_by = [a for a in attributions if a.get("license") == "CC BY 4.0"]
    assert cc_by, "never-list must declare a CC BY 4.0 attribution"
