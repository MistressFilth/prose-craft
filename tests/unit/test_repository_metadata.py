from __future__ import annotations

import json
import re
import subprocess
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
    """Return the canonical engine version declared in ``pyproject.toml``.

    Runtime and installed-plugin surfaces match this value. Marketplace
    development metadata carries an independent SemVer version.
    """
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = _PYPROJECT_VERSION_RE.search(text)
    assert match is not None, "pyproject.toml does not declare a version"
    version = match.group(1)
    assert _SEMVER_RE.match(version), f"pyproject.toml version {version!r} is not canonical X.Y.Z"
    return version


def test_engine_and_plugin_version_surfaces_match() -> None:
    version = _read_canonical_version()
    runtime = (ROOT / "src/prose_craft/__init__.py").read_text(encoding="utf-8")
    plugin = json.loads(
        (ROOT / "claude-code/plugin/.claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    assert f'__version__ = "{version}"' in runtime
    assert plugin["version"] == version


def test_marketplace_version_is_independent_semver() -> None:
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    assert _SEMVER_RE.match(marketplace["version"]), (
        f"marketplace version {marketplace['version']!r} is not canonical X.Y.Z"
    )


def test_marketplace_points_to_standard_plugin_layout() -> None:
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    assert marketplace["plugins"][0]["source"] == "./claude-code/plugin/"
    assert (ROOT / marketplace["plugins"][0]["source"][2:]).is_dir()


def test_checked_out_history_has_no_coauthor_trailers() -> None:
    messages = subprocess.run(
        ["git", "log", "--all", "--format=%B"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert re.search(r"^\s*Co-Authored-By:", messages, re.IGNORECASE | re.MULTILINE) is None
