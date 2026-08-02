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
from collections.abc import Callable, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
RUNTIME_INIT = REPO_ROOT / "src" / "prose_craft" / "__init__.py"
PLUGIN_PYPROJECT = REPO_ROOT / "claude-code" / "plugin" / "pyproject.toml"
PLUGIN_JSON = REPO_ROOT / "claude-code" / "plugin" / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

VALID_BUMPS = ("major", "minor", "patch", "none")

# Strict SemVer core: three non-empty numeric segments, each "0" or
# non-zero-leading digits. Rejects "01.2.3", "1.2.3.4", "v1.2.3", etc.
_SEMVER_RE = re.compile(r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")
_PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
_RUNTIME_VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.MULTILINE)
_PYPROJECT_VERSION_LINE_RE = re.compile(r'^version\s*=\s*"[^"]+"', flags=re.MULTILINE)
_RUNTIME_VERSION_LINE_RE = re.compile(r'^__version__\s*=\s*"[^"]+"', flags=re.MULTILINE)


def classify_bump(messages: Sequence[str]) -> str:
    """Return the highest-impact SemVer bump implied by ``messages``.

    - ``major`` if any commit header carries ``!`` or any line of any
      message body begins with ``BREAKING CHANGE:``.
    - ``minor`` if any commit starts with ``feat``.
    - ``patch`` if any commit starts with ``fix``.
    - ``none`` otherwise.
    """
    has_feat = False
    has_fix = False
    for raw in messages:
        if not raw:
            continue
        header = raw.splitlines()[0]
        if re.search(r"^BREAKING CHANGE:", raw, re.MULTILINE):
            return "major"
        type_token = header.split(":", 1)[0]
        if "!" in type_token:
            return "major"
        if type_token.startswith("feat"):
            has_feat = True
        elif type_token.startswith("fix"):
            has_fix = True
    if has_feat:
        return "minor"
    if has_fix:
        return "patch"
    return "none"


def next_version(current: str, bump: str) -> str:
    """Apply ``bump`` to canonical SemVer ``current`` and return the next version.

    ``current`` must match strict ``X.Y.Z`` (each segment ``0`` or a
    non-zero-leading positive integer); ``bump`` must be one of
    ``major``, ``minor``, ``patch``, or ``none``. Anything else raises
    ``ValueError``.
    """
    if bump not in VALID_BUMPS:
        raise ValueError(f"unknown bump: {bump!r}")
    if not _SEMVER_RE.match(current):
        raise ValueError(f"invalid version: {current!r}")
    major, minor, patch = (int(p) for p in current.split("."))
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
    match = _PYPROJECT_VERSION_RE.search(text)
    if not match:
        raise RuntimeError(f"could not locate version in {PYPROJECT}")
    version = match.group(1)
    if not _SEMVER_RE.match(version):
        raise RuntimeError(f"root version {version!r} in {PYPROJECT} is not canonical X.Y.Z")
    return version


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


def _tag_exists(tag: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", tag],
        check=False,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )
    return result.returncode == 0


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


def _set_pyproject_version_text(text: str, version: str) -> str:
    return _PYPROJECT_VERSION_LINE_RE.sub(f'version = "{version}"', text, count=1)


def _set_runtime_version_text(text: str, version: str) -> str:
    return _RUNTIME_VERSION_LINE_RE.sub(f'__version__ = "{version}"', text, count=1)


def _set_json_version_text(text: str, version: str) -> str:
    data = json.loads(text)
    data["version"] = version
    return json.dumps(data, indent=2) + "\n"


def _render_changelog_section(version: str, date: str, bodies: Sequence[str]) -> str:
    bullets = "\n".join(f"- {body}" for body in bodies) if bodies else "- No notable changes."
    return f"## [{version}] - {date}\n\n### Changed\n{bullets}\n\n"


def _update_changelog_text(text: str, version: str, date: str, subjects: Sequence[str]) -> str:
    new_section = _render_changelog_section(version, date, subjects)
    if "## [Unreleased]" in text:
        head, tail = text.split("## [Unreleased]", 1)
        tail = tail.split("\n", 1)[1] if "\n" in tail else ""
        return head + "## [Unreleased]\n\n" + new_section + tail
    return text.rstrip() + "\n\n" + new_section


def _today() -> str:
    return subprocess.run(
        ["date", "+%Y-%m-%d"],
        check=True,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    ).stdout.strip()


def _metadata_surfaces(
    version: str, subjects: Sequence[str]
) -> list[tuple[str, Path, Callable[[str], str]]]:
    today = _today()
    return [
        ("pyproject.toml", PYPROJECT, lambda text: _set_pyproject_version_text(text, version)),
        (
            "claude-code/plugin/pyproject.toml",
            PLUGIN_PYPROJECT,
            lambda text: _set_pyproject_version_text(text, version),
        ),
        (
            "src/prose_craft/__init__.py",
            RUNTIME_INIT,
            lambda text: _set_runtime_version_text(text, version),
        ),
        (
            "claude-code/plugin/.claude-plugin/plugin.json",
            PLUGIN_JSON,
            lambda text: _set_json_version_text(text, version),
        ),
        (
            ".claude-plugin/marketplace.json",
            MARKETPLACE_JSON,
            lambda text: _set_json_version_text(text, version),
        ),
        (
            "CHANGELOG.md",
            CHANGELOG,
            lambda text: _update_changelog_text(text, version, today, subjects),
        ),
    ]


def _apply_transaction(
    surfaces: Sequence[tuple[str, Path, Callable[[str], str]]],
) -> dict[Path, str]:
    """Apply each surface update transactionally.

    Computes all new contents up front, then commits every change with
    sibling-tempfile atomic writes. If anything fails before all writes
    complete, every file already touched is restored from its
    pre-write snapshot and the original exception is re-raised.

    Returns the snapshot dict so the caller can roll back later
    validation failures (e.g. ``make check`` / ``make test``).
    """
    snapshots: dict[Path, str] = {}
    try:
        pending: list[tuple[Path, str]] = []
        for _label, path, mutator in surfaces:
            original = path.read_text(encoding="utf-8")
            snapshots[path] = original
            pending.append((path, mutator(original)))
        for path, new_text in pending:
            _atomic_write(path, new_text)
    except Exception:
        for path, original in snapshots.items():
            try:
                _atomic_write(path, original)
            except Exception:
                pass
        raise
    return snapshots


def _rollback(snapshots: dict[Path, str]) -> None:
    """Restore every path in ``snapshots`` to its pre-write content."""
    for path, original in snapshots.items():
        try:
            _atomic_write(path, original)
        except Exception:
            pass


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="prose-craft release helper")
    parser.parse_args(list(argv) if argv is not None else None)

    snapshots: dict[Path, str] = {}
    try:
        _check_clean_worktree()
        current = _read_root_version()
        tag = _latest_tag()
        if tag is not None and tag[1:] != current:
            raise RuntimeError(
                f"latest tag {tag!r} does not match root version {current!r}; "
                "the repository is mid-release or out of sync"
            )
        subjects = _commits_since(tag)
        bump = classify_bump(subjects)
        if bump == "none":
            raise RuntimeError(
                "no version-affecting commits since "
                f"{tag or 'beginning of history'}; refusing to release"
            )
        version = next_version(current, bump)
        tag_name = f"v{version}"
        if _tag_exists(tag_name):
            raise RuntimeError(f"target tag {tag_name!r} already exists locally or remotely")
        print(f"release: {current} -> {version} (bump={bump})")

        snapshots = _apply_transaction(_metadata_surfaces(version, subjects))
        print(
            f"updated: {', '.join(label for label, _p, _m in _metadata_surfaces(version, subjects))}"
        )

        try:
            _run(["make", "check"])
            _run(["make", "test"])
        except RuntimeError:
            _rollback(snapshots)
            raise

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
