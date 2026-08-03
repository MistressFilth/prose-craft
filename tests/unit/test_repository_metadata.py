from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]

# Strict SemVer core: three non-empty numeric segments, each "0" or
# non-zero-leading digits. Rejects "01.2.3", "1.2.3.4", "v1.2.3", etc.
# Mirrors the guard used by scripts/release.py so the test enforces the
# same canonical form the release helper accepts without importing it
# (the test stays self-contained under tests/unit).
_SEMVER_RE = re.compile(r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")
_PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def _read_canonical_version() -> str:
    """Return the canonical version declared in ``pyproject.toml``.

    The root ``pyproject.toml`` is the single source of truth; every
    other version surface must match this string. Parsing mirrors the
    approach in ``scripts/release.py`` so the test enforces the same
    contract without importing from ``scripts.release`` (which would
    couple the test to a module not on ``tests/``'s import path).
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = _PYPROJECT_VERSION_RE.search(text)
    assert match is not None, "pyproject.toml does not declare a version"
    version = match.group(1)
    assert _SEMVER_RE.match(version), f"pyproject.toml version {version!r} is not canonical X.Y.Z"
    return version


def test_version_surfaces_match() -> None:
    version = _read_canonical_version()

    runtime = (ROOT / "src/prose_craft/__init__.py").read_text(encoding="utf-8")
    plugin = json.loads(
        (ROOT / "claude-code/plugin/prose-craft/.claude-plugin/plugin.json").read_text(
            encoding="utf-8"
        )
    )
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))

    assert f'__version__ = "{version}"' in runtime, (
        f"src/prose_craft/__init__.py missing __version__ {version!r}"
    )
    assert plugin["version"] == version, (
        f"claude-code/plugin/prose-craft/.claude-plugin/plugin.json version "
        f"{plugin['version']!r} does not match canonical {version!r}"
    )
    assert marketplace["version"] == version, (
        f".claude-plugin/marketplace.json version {marketplace['version']!r} "
        f"does not match canonical {version!r}"
    )


def test_marketplace_points_to_standard_plugin_layout() -> None:
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))

    assert marketplace["plugins"][0]["source"] == "./claude-code/plugin/prose-craft/"
    assert (ROOT / marketplace["plugins"][0]["source"][2:]).is_dir()
