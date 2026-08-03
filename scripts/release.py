"""Guarded semantic-release helper for the prose-craft repository.

Pure functions ``classify_bump`` and ``next_version`` drive the bump
decision; ``main`` is the orchestrator that performs the actual
release only when every safeguard passes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
RUNTIME_INIT = REPO_ROOT / "src" / "prose_craft" / "__init__.py"
PLUGIN_JSON = REPO_ROOT / "claude-code" / "plugin" / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

VALID_BUMPS = ("major", "minor", "patch", "none")

# Strict SemVer core: three non-empty numeric segments, each "0" or
# non-zero-leading digits. Rejects "01.2.3", "1.2.3.4", "v1.2.3", etc.
_SEMVER_RE = re.compile(r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")
_PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
_PYPROJECT_VERSION_LINE_RE = re.compile(r'^version\s*=\s*"[^"]+"', flags=re.MULTILINE)
_RUNTIME_VERSION_LINE_RE = re.compile(r'^__version__\s*=\s*"[^"]+"', flags=re.MULTILINE)

# Format spec for git log that emits the full commit block (subject +
# blank line + body) so BREAKING CHANGE footers reach classify_bump.
_GIT_LOG_PRETTY = "%B%x00"


def classify_bump(messages: Sequence[str]) -> str:
    """Return the highest-impact SemVer bump implied by ``messages``.

    Each entry in ``messages`` may be either a single-line subject or a
    full commit block (``subject\\n\\nbody``). The function:

    - returns ``major`` if any commit header carries ``!`` or any line of
      any message begins with ``BREAKING CHANGE:``;
    - returns ``minor`` when any commit starts with ``feat``;
    - returns ``patch`` when any commit starts with ``fix``;
    - returns ``none`` otherwise.
    """
    has_feat = False
    has_fix = False
    for raw in messages:
        if not raw:
            continue
        if re.search(r"^BREAKING CHANGE:", raw, re.MULTILINE):
            return "major"
        header = raw.splitlines()[0]
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


def _read_json_version(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    version = data.get("version")
    if not isinstance(version, str) or not _SEMVER_RE.match(version):
        raise RuntimeError(f"version {version!r} in {path} is not canonical X.Y.Z")
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
    """Return commit blocks (``subject\\n\\nbody``) since ``tag``.

    Each entry is one commit's full message text so that BREAKING CHANGE
    footers reach ``classify_bump``. ``%x00`` (NUL) is appended to
    preserve trailing newlines that ``%B`` would otherwise strip; we
    strip the sentinel before returning.
    """
    rng = f"{tag}..HEAD" if tag else "HEAD"
    result = subprocess.run(
        ["git", "log", f"--pretty={_GIT_LOG_PRETTY}", rng],
        check=True,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
    )
    return [block.lstrip() for block in result.stdout.split("\x00") if block.strip()]


def _tag_exists_locally(tag: str) -> bool:
    """Return True if ``tag`` resolves to a local ref."""
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
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
    except Exception:
        os.close(fd)
        Path(tmp_name).unlink(missing_ok=True)
        raise
    Path(tmp_name).replace(path)


def _set_pyproject_version_text(text: str, version: str) -> str:
    return _PYPROJECT_VERSION_LINE_RE.sub(f'version = "{version}"', text, count=1)


def _set_runtime_version_text(text: str, version: str) -> str:
    return _RUNTIME_VERSION_LINE_RE.sub(f'__version__ = "{version}"', text, count=1)


def _set_json_version_text(text: str, version: str) -> str:
    data = json.loads(text)
    data["version"] = version
    return json.dumps(data, indent=2) + "\n"


def _strip_footer(block: str) -> str:
    """Strip ``Co-authored-by`` and ``BREAKING CHANGE:`` footers from a commit block.

    Git's commit body treats the first paragraph as the description and
    any subsequent paragraph as a footer block. ``Co-authored-by`` and
    ``BREAKING CHANGE:`` are the only Conventional Commit footers the
    release helper cares about; everything below the description should
    not appear in a changelog bullet.

    Returns the message with the trailing newline trimmed.
    """
    lines = block.splitlines()
    if not lines:
        return ""
    # First line is always the subject.
    subject = lines[0]
    # Walk forward until the first blank line; everything from that blank
    # line onwards is the body. Footers (Co-authored-by / BREAKING CHANGE)
    # can sit at the end of the body; everything after the *last* blank
    # line that is followed by a footer line is footer, and we drop it.
    # In practice, the simplest correct rule: drop any trailing line that
    # starts with a known footer marker.
    body_lines: list[str] = []
    for line in lines[1:]:
        if line.startswith("Co-authored-by:") or line.startswith("Co-Authored-By:"):
            continue
        if line.startswith("BREAKING CHANGE:"):
            continue
        if line == "---------":
            # Squash-merge separator left over from a GitHub PR body.
            continue
        body_lines.append(line)
    # Strip leading and trailing blank lines from the body.
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()
    if not body_lines:
        return subject
    return subject + "\n\n" + "\n".join(body_lines)


def _first_line(message: str) -> str:
    """Return the first non-empty line of a (possibly multi-paragraph) message."""
    for line in message.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _classify_commit(subject: str) -> str:
    """Map a Conventional Commit subject to a Keep-a-Changelog group.

    Returns ``"Added"`` for ``feat``-typed subjects, ``"Fixed"`` for
    ``fix``-typed subjects, and ``"Changed"`` for everything else.
    """
    if not subject:
        return "Changed"
    type_token = subject.split(":", 1)[0]
    if type_token.startswith("feat"):
        return "Added"
    if type_token.startswith("fix"):
        return "Fixed"
    return "Changed"


# Commits that the release helper itself produced (``chore(release):
# <version> via guarded release helper``) are excluded from the changelog
# bullets because they describe the helper's own output, not a user-facing
# change.
_RELEASE_COMMIT_PREFIX = "chore(release):"


def _group_bullets(blocks: Sequence[str]) -> dict[str, list[str]]:
    """Group commit subjects into ``Added``/``Fixed``/``Changed`` buckets.

    Each block is the full commit message as returned by
    ``git log --pretty=%B``; the helper strips footers, takes the first
    line as the subject, classifies by Conventional Commit type, and
    returns a dict with keys ``"Added"``, ``"Fixed"``, ``"Changed"``.
    Values are pre-formatted bullet strings (``- subject``).
    """
    groups: dict[str, list[str]] = {"Added": [], "Fixed": [], "Changed": []}
    for block in blocks:
        message = _strip_footer(block)
        subject = _first_line(message)
        if not subject:
            continue
        if subject.startswith(_RELEASE_COMMIT_PREFIX):
            continue
        groups[_classify_commit(subject)].append(f"- {subject}")
    return groups


def _render_changelog_section(version: str, date: str, bodies: Sequence[str]) -> str:
    """Render a release section from raw commit blocks.

    Subjects are grouped by Conventional Commit type into ``### Added``
    (feat), ``### Fixed`` (fix), and ``### Changed`` (everything else)
    subsections. Empty groups are omitted from the output. When every
    bucket is empty, a single ``### Changed`` subsection with a
    ``- No notable changes.`` bullet is rendered so the section is
    never empty.
    """
    groups = _group_bullets(bodies)
    has_any = any(groups[k] for k in ("Added", "Fixed", "Changed"))
    if not has_any:
        return f"## [{version}] - {date}\n\n### Changed\n- No notable changes.\n\n"
    parts: list[str] = [f"## [{version}] - {date}", ""]
    for heading in ("Added", "Fixed", "Changed"):
        if not groups[heading]:
            continue
        parts.append(f"### {heading}")
        parts.extend(groups[heading])
        parts.append("")
    return "\n".join(parts)


def _update_changelog_text(text: str, version: str, date: str, subjects: Sequence[str]) -> str:
    new_section = _render_changelog_section(version, date, subjects)
    if "## [Unreleased]" in text:
        head, tail = text.split("## [Unreleased]", 1)
        tail = tail.split("\n", 1)[1] if "\n" in tail else ""
        return head + "## [Unreleased]\n\n" + new_section + tail
    return text.rstrip() + "\n\n" + new_section


def _today_utc() -> str:
    """Return today's UTC date as ``YYYY-MM-DD`` (portable, no POSIX `date`)."""
    return datetime.now(timezone.utc).date().isoformat()


def _metadata_surfaces(
    version: str, subjects: Sequence[str]
) -> list[tuple[str, Path, Callable[[str], str]]]:
    today = _today_utc()
    marketplace_version = next_version(_read_json_version(MARKETPLACE_JSON), "patch")
    return [
        ("pyproject.toml", PYPROJECT, lambda text: _set_pyproject_version_text(text, version)),
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
            lambda text: _set_json_version_text(text, marketplace_version),
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
        _rollback(snapshots)
        raise
    return snapshots


def _rollback(snapshots: dict[Path, str]) -> None:
    """Restore every path in ``snapshots`` to its pre-write content.

    Any per-file restore failure is logged to stderr but does not abort
    the rollback — best-effort cleanup, then the original failure is
    re-raised by the caller.
    """
    for path, original in snapshots.items():
        try:
            _atomic_write(path, original)
        except Exception as exc:
            print(
                f"release rollback: failed to restore {path}: {exc}",
                file=sys.stderr,
            )


def _delete_tag(tag: str) -> None:
    """Best-effort local tag deletion; logs but does not raise on failure."""
    try:
        _run(["git", "tag", "-d", tag])
    except RuntimeError as exc:
        print(f"release cleanup: failed to delete local tag {tag!r}: {exc}", file=sys.stderr)


def _release_commit_message(version: str) -> str:
    """Conventional Commit subject + body for the release commit."""
    return (
        f"chore(release): {version} via guarded release helper\n\n"
        f"- Bump metadata surfaces to {version}.\n"
        f"- Update CHANGELOG with dated release section.\n\n"
        f"Generated by scripts/release.py.\n"
    )


def _commit_release(version: str, paths: Sequence[Path]) -> str:
    """Stage ``paths`` and create a single release commit. Return its SHA.

    Raises ``RuntimeError`` if no staged changes remain or git fails.
    Only the listed paths are staged — incidental worktree drift (e.g.
    an ``uv.lock`` rewritten by ``make init``) is left alone.
    """
    for path in paths:
        rel = path.relative_to(REPO_ROOT)
        _run(["git", "add", "--", str(rel)])
    staged = _run(["git", "diff", "--cached", "--name-only"]).stdout.strip()
    if not staged:
        raise RuntimeError("no staged changes for release commit")
    _run(["git", "commit", "-m", _release_commit_message(version)])
    return _run(["git", "rev-parse", "HEAD"]).stdout.strip()


def _reset_release_commit() -> None:
    """Best-effort ``git reset --hard HEAD~1`` to undo a release commit.

    Used when a downstream step (tag, push) fails after the commit was
    made. Logs but does not raise on failure.
    """
    try:
        _run(["git", "reset", "--hard", "HEAD~1"])
    except RuntimeError as exc:
        print(
            f"release cleanup: failed to reset release commit: {exc}",
            file=sys.stderr,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="prose-craft release helper")
    parser.parse_args(list(argv) if argv is not None else None)

    snapshots: dict[Path, str] = {}
    tag_created = False
    commit_made = False
    tag_name = ""
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
        if _tag_exists_locally(tag_name):
            raise RuntimeError(f"target tag {tag_name!r} already exists locally")
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
            snapshots = {}
            raise

        try:
            _commit_release(version, list(snapshots.keys()))
            commit_made = True
        except RuntimeError:
            _rollback(snapshots)
            snapshots = {}
            raise

        try:
            _run(["git", "tag", tag_name])
            tag_created = True
            _run(["git", "push", "origin", tag_name])
        except RuntimeError:
            if tag_created:
                _delete_tag(tag_name)
                tag_created = False
            if commit_made:
                _reset_release_commit()
                commit_made = False
            _rollback(snapshots)
            snapshots = {}
            raise
    except RuntimeError as exc:
        print(f"release aborted: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
