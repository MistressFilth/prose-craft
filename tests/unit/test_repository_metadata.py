from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_version_surfaces_match() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    runtime = (ROOT / "src/prose_craft/__init__.py").read_text(encoding="utf-8")
    plugin_project = (ROOT / "claude-code/plugin/pyproject.toml").read_text(encoding="utf-8")
    plugin = json.loads(
        (ROOT / "claude-code/plugin/.claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))

    assert 'version = "0.2.0"' in pyproject
    assert '__version__ = "0.2.0"' in runtime
    assert 'version = "0.2.0"' in plugin_project
    assert plugin["version"] == "0.2.0"
    assert marketplace["version"] == "0.2.0"


def test_marketplace_points_to_standard_plugin_layout() -> None:
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))

    assert marketplace["plugins"][0]["source"] == "./claude-code/plugin/"
    assert (ROOT / marketplace["plugins"][0]["source"][2:]).is_dir()
