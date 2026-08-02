"""Guarded semantic-release helper for the prose-craft repository.

Pure functions ``classify_bump`` and ``next_version`` drive the bump
decision; ``main`` is the orchestrator that performs the actual
release only when every safeguard passes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
RUNTIME_INIT = REPO_ROOT / "src" / "prose_craft" / "__init__.py"
PLUGIN_PYPROJECT = REPO_ROOT / "claude-code" / "plugin" / "pyproject.toml"
PLUGIN_JSON = REPO_ROOT / "claude-code" / "plugin" / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

VALID_BUMPS = ("major", "minor", "patch", "none")


def classify_bump(messages: Sequence[str]) -> str:
    """Return the highest-impact SemVer bump implied by ``messages``.

    - ``major`` if any commit header carries ``!`` or any message body
      carries a ``BREAKING CHANGE:`` footer.
    - ``minor`` if any commit starts with ``feat``.
    - ``patch`` if any commit starts with ``fix``.
    - ``none`` otherwise.
    """
    has_feat = False
    has_fix = False
    for raw in messages:
        if not raw:
            continue
        lines = raw.splitlines()
        if not lines:
            continue
        header = lines[0]
        body = "\n".join(lines[1:])
        if re.search(r"^BREAKING CHANGE:", raw, re.MULTILINE):
            return "major"
        type_token = header.split(":", 1)[0]
        if "!" in type_token:
            return "major"
        if type_token.startswith("feat"):
            has_feat = True
        elif type_token.startswith("fix"):
            has_fix = True
        # Unused local; keep to document intent and silence linters.
        del body
    if has_feat:
        return "minor"
    if has_fix:
        return "patch"
    return "none"


def next_version(current: str, bump: str) -> str:
    """Apply ``bump`` to SemVer ``current`` and return the next version."""
    if bump not in VALID_BUMPS:
        raise ValueError(f"unknown bump: {bump!r}")
    parts = current.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"invalid version: {current!r}")
    major, minor, patch = (int(p) for p in parts)
    if bump == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump == "minor":
        minor += 1
        patch = 0
    elif bump == "patch":
        patch += 1
    return f"{major}.{minor}.{patch}"


# ---------------------------------------------------------------------------
# CLI safeguards
# ---------------------------------------------------------------------------


def _run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run ``cmd`` and raise ``RuntimeError`` with a concise message on failure."""
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - guard path
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{stderr}") from exc


def _check_clean_worktree() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        check=True,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )
    if result.stdout.strip():
        raise RuntimeError("git worktree is dirty; commit or stash changes before releasing")


def _read_root_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"could not locate version in {PYPROJECT}")
    return match.group(1)


def _latest_tag() -> str | None:
    result = subprocess.run(
        ["git", "tag", "--list", "v*.*.*", "--sort=-v:refname"],
        check=True,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )
    tag = result.stdout.splitlines()[0].strip() if result.stdout.strip() else ""
    return tag or None


def _commits_since(tag: str | None) -> list[str]:
    rng = f"{tag}..HEAD" if tag else "HEAD"
    result = subprocess.run(
        ["git", "log", "--pretty=%s", rng],
        check=True,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )
    return [line for line in result.stdout.splitlines() if line]


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via a sibling temp file + os.replace."""
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        Path(tmp_name).replace(path)
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _set_pyproject_version(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    new_text = re.sub(
        r'^version\s*=\s*"[^"]+"',
        f'version = "{version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    _atomic_write(path, new_text)


def _set_runtime_version(version: str) -> None:
    text = RUNTIME_INIT.read_text(encoding="utf-8")
    new_text = re.sub(
        r'^__version__\s*=\s*"[^"]+"',
        f'__version__ = "{version}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    _atomic_write(RUNTIME_INIT, new_text)


def _set_json_version(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    _atomic_write(path, json.dumps(data, indent=2) + "\n")


def _render_changelog_section(version: str, date: str, bodies: Sequence[str]) -> str:
    bullets = "\n".join(f"- {body}" for body in bodies) if bodies else "- No notable changes."
    return f"## [{version}] - {date}\n\n### Changed\n{bullets}\n\n"


def _update_changelog(version: str, subjects: Sequence[str]) -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    today = subprocess.run(
        ["date", "+%Y-%m-%d"],
        check=True,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    ).stdout.strip()
    new_section = _render_changelog_section(version, today, subjects)
    if "## [Unreleased]" in text:
        head, tail = text.split("## [Unreleased]", 1)
        tail = tail.split("\n", 1)[1] if "\n" in tail else ""
        rebuilt = head + "## [Unreleased]\n\n" + new_section + tail
    else:
        rebuilt = text.rstrip() + "\n\n" + new_section
    _atomic_write(CHANGELOG, rebuilt)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="prose-craft release helper")
    parser.parse_args(list(argv) if argv is not None else None)

    try:
        _check_clean_worktree()
        current = _read_root_version()
        tag = _latest_tag()
        subjects = _commits_since(tag)
        bump = classify_bump(subjects)
        if bump == "none":
            raise RuntimeError(
                "no version-affecting commits since "
                f"{tag or 'beginning of history'}; refusing to release"
            )
        version = next_version(current, bump)
        print(f"release: {current} -> {version} (bump={bump})")

        _set_pyproject_version(PYPROJECT, version)
        _set_pyproject_version(PLUGIN_PYPROJECT, version)
        _set_runtime_version(version)
        _set_json_version(PLUGIN_JSON, version)
        _set_json_version(MARKETPLACE_JSON, version)
        _update_changelog(version, subjects)

        _run(["make", "check"])
        _run(["make", "test"])

        tag_name = f"v{version}"
        _run(["git", "tag", tag_name])
        try:
            _run(["git", "push", "origin", tag_name])
        except Exception:
            _run(["git", "tag", "-d", tag_name])
            raise
    except RuntimeError as exc:
        print(f"release aborted: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
