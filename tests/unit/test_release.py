from __future__ import annotations

import pytest

from scripts import release
from scripts.release import _apply_transaction, classify_bump, next_version


@pytest.mark.parametrize(
    ("messages", "expected"),
    [
        (["fix: correct path"], "patch"),
        (["docs: update README", "feat: add CI"], "minor"),
        (["feat!: relocate plugin"], "major"),
        (["chore: clean metadata"], "none"),
    ],
)
def test_classify_bump(messages: list[str], expected: str) -> None:
    assert classify_bump(messages) == expected


def test_breaking_footer_is_major() -> None:
    assert (
        classify_bump(["feat: change packaging", "BREAKING CHANGE: plugin path changed"]) == "major"
    )


def test_classify_bump_real_commit_block_with_breaking_footer() -> None:
    """A full `git log --pretty=%B` block with BREAKING CHANGE footer is major."""
    block = (
        "feat: change packaging\n"
        "\n"
        "This refactors the plugin entry point.\n"
        "\n"
        "BREAKING CHANGE: plugin path changed\n"
    )
    assert classify_bump([block]) == "major"


def test_classify_bump_real_commit_block_feat_only() -> None:
    """A full `git log --pretty=%B` block with no footer is minor."""
    block = "feat: add new endpoint\n\nThis adds a new endpoint for the user."
    assert classify_bump([block]) == "minor"


def test_classify_bump_real_commit_block_fix_only() -> None:
    """A full `git log --pretty=%B` block for a fix is patch."""
    block = "fix: correct off-by-one\n\nThe index was wrong by one when n=0."
    assert classify_bump([block]) == "patch"


def test_classify_bump_real_commit_block_chore() -> None:
    """A full `git log --pretty=%B` block for a chore is none."""
    block = "chore: clean metadata\n\nNo behavior change."
    assert classify_bump([block]) == "none"


def test_classify_bump_mixed_real_blocks() -> None:
    """Mix of full commit blocks; major overrides minor overrides patch overrides none."""
    blocks = [
        "feat: add endpoint\n\nAdds /v1/foo.",
        "fix: correct bug\n\nOff-by-one fix.",
        "chore: meta\n\nNo behavior change.",
    ]
    assert classify_bump(blocks) == "minor"


def test_classify_bump_scoped_bang_in_full_block() -> None:
    """A `feat(api)!:` header inside a full commit block is still major."""
    block = "feat(api)!: relocate plugin\n\nMoves the adapter under claude-code/plugin/."
    assert classify_bump([block]) == "major"


@pytest.mark.parametrize(
    ("current", "bump", "expected"),
    [("0.1.0", "patch", "0.1.1"), ("0.1.0", "minor", "0.2.0"), ("0.1.0", "major", "1.0.0")],
)
def test_next_version(current: str, bump: str, expected: str) -> None:
    assert next_version(current, bump) == expected


@pytest.mark.parametrize(
    "bad_version",
    [
        "01.2.3",
        "1.02.3",
        "1.2.03",
        "1.2",
        "1.2.3.4",
        "v1.2.3",
        "1.2.3-beta",
        "a.b.c",
        "1.2.-3",
        "",
    ],
)
def test_next_version_rejects_noncanonical(bad_version: str) -> None:
    with pytest.raises(ValueError):
        next_version(bad_version, "patch")


@pytest.mark.parametrize("bad_bump", ["", "MAJOR", "build", "feature", "release"])
def test_next_version_rejects_unknown_bump(bad_bump: str) -> None:
    with pytest.raises(ValueError):
        next_version("1.2.3", bad_bump)


def test_apply_transaction_rolls_back_on_failure(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If any surface write fails, every previously touched file is restored."""
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("original-a", encoding="utf-8")
    b.write_text("original-b", encoding="utf-8")

    real_atomic = release._atomic_write
    calls = {"count": 0}

    def maybe_fail(path, content):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated write failure")
        return real_atomic(path, content)

    monkeypatch.setattr(release, "_atomic_write", maybe_fail)

    surfaces = [
        ("a", a, lambda text: "new-a"),
        ("b", b, lambda text: "new-b"),
        ("a-again", a, lambda text: "new-a-again"),
    ]

    with pytest.raises(OSError, match="simulated"):
        _apply_transaction(surfaces)

    assert a.read_text(encoding="utf-8") == "original-a"
    assert b.read_text(encoding="utf-8") == "original-b"


def test_apply_transaction_succeeds_when_all_writes_pass(
    tmp_path,
) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_text("original-a", encoding="utf-8")
    b.write_text("original-b", encoding="utf-8")
    surfaces = [
        ("a", a, lambda text: "new-a"),
        ("b", b, lambda text: "new-b"),
    ]
    snapshots = _apply_transaction(surfaces)
    assert snapshots == {a: "original-a", b: "original-b"}
    assert a.read_text(encoding="utf-8") == "new-a"
    assert b.read_text(encoding="utf-8") == "new-b"


def test_release_commit_message_format() -> None:
    """Release commit message is a Conventional Commit with body."""
    msg = release._release_commit_message("0.2.1")
    assert msg.startswith("chore(release): 0.2.1 via guarded release helper\n")
    assert "Bump metadata surfaces to 0.2.1" in msg
    assert "CHANGELOG" in msg
    assert "Generated by scripts/release.py" in msg


def test_commit_release_stages_only_listed_paths(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_commit_release`` must stage only the listed paths, not all drift."""
    monkeypatch.setattr(release, "REPO_ROOT", tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('version = "0.2.0"\n', encoding="utf-8")
    drift = tmp_path / "drift.txt"
    drift.write_text("incidental\n", encoding="utf-8")

    class _FakeResult:
        def __init__(self, stdout: str = "") -> None:
            self.stdout = stdout

    seen_adds: list[tuple[str, ...]] = []
    seen_diffs: list[int] = []
    seen_commits: list[tuple[str, ...]] = []
    rev_responses = iter(["deadbeef", "deadbeef"])

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "git" and cmd[1] == "add":
            seen_adds.append(tuple(cmd))
        elif cmd[0] == "git" and cmd[1] == "diff":
            seen_diffs.append(1)
            return _FakeResult(str(pyproject) + "\n")
        elif cmd[0] == "git" and cmd[1] == "commit":
            seen_commits.append(tuple(cmd))
            return _FakeResult("")
        elif cmd[0] == "git" and cmd[1] == "rev-parse":
            return _FakeResult(next(rev_responses))
        return _FakeResult("")

    monkeypatch.setattr(release, "_run", fake_run)
    sha = release._commit_release("0.2.1", [pyproject])
    assert sha == "deadbeef"
    assert seen_adds == [("git", "add", "--", "pyproject.toml")]
    assert len(seen_diffs) == 1
    assert seen_commits and seen_commits[0][:2] == ("git", "commit")
    assert all("drift.txt" not in add for add in seen_adds)


def test_commit_release_raises_when_no_staged_changes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(release, "REPO_ROOT", tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('version = "0.2.0"\n', encoding="utf-8")

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "git" and cmd[1] in ("add", "diff"):
            return type("R", (), {"stdout": ""})()
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(release, "_run", fake_run)
    with pytest.raises(RuntimeError, match="no staged changes"):
        release._commit_release("0.2.1", [pyproject])


def test_commits_since_strips_leading_newlines(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_commits_since`` must lstrip each block; ``%B`` adds a leading ``\\n``.

    The git log format ``%B%x00`` produces ``<body>\\n\\x00<next body>...``.
    When the next body starts with ``\\n`` (which ``%B`` emits as a
    separator), the first ``splitlines()[0]`` is empty, so
    ``classify_bump`` would silently drop the commit. ``_commits_since``
    must ``lstrip`` each block to keep the subject on the first line.
    """
    monkeypatch.setattr(release, "REPO_ROOT", tmp_path)

    fake = "chore: align lock\n\x00\nfix(release): close fd\n\x00feat: new endpoint\n"

    class _FakeResult:
        stdout = fake

    def fake_subprocess_run(cmd, *args, **kwargs):
        return _FakeResult()

    monkeypatch.setattr(release.subprocess, "run", fake_subprocess_run)
    blocks = release._commits_since("v0.0.0")
    assert blocks == [
        "chore: align lock\n",
        "fix(release): close fd\n",
        "feat: new endpoint\n",
    ]
    assert release.classify_bump(blocks) == "minor"


def test_strip_footer_drops_coauthored_and_breaking() -> None:
    block = (
        "fix: close fd\n"
        "\n"
        "Body line one.\n"
        "Body line two.\n"
        "\n"
        "Co-authored-by: Claude <noreply@anthropic.com>\n"
        "Co-Authored-By: v0idbit <>\n"
        "BREAKING CHANGE: behavior changed\n"
    )
    assert release._strip_footer(block) == "fix: close fd\n\nBody line one.\nBody line two."


def test_classify_commit() -> None:
    assert release._classify_commit("feat: add endpoint") == "Added"
    assert release._classify_commit("fix: correct path") == "Fixed"
    assert release._classify_commit("refactor: split module") == "Changed"
    assert release._classify_commit("chore: clean metadata") == "Changed"
    assert release._classify_commit("docs: update readme") == "Changed"
    assert release._classify_commit("perf: cache results") == "Changed"
    assert release._classify_commit("test: add coverage") == "Changed"
    assert release._classify_commit("build: bump deps") == "Changed"
    assert release._classify_commit("ci: add workflow") == "Changed"
    assert release._classify_commit("style: format") == "Changed"
    assert release._classify_commit("unknown: thing") == "Changed"


def test_group_bullets_skips_release_helper_commit() -> None:
    bodies = [
        "feat: new endpoint\n",
        "fix(release): close fd\n",
        "chore(release): 0.2.2 via guarded release helper\n",
        "fix: correct path\n",
    ]
    groups = release._group_bullets(bodies)
    assert groups["Added"] == ["- feat: new endpoint"]
    assert groups["Fixed"] == ["- fix(release): close fd", "- fix: correct path"]
    assert groups["Changed"] == []


def test_group_bullets_strips_trailers_from_subjects() -> None:
    bodies = [
        "feat: new endpoint\n\nCo-authored-by: Claude <noreply@anthropic.com>\n",
    ]
    groups = release._group_bullets(bodies)
    assert groups["Added"] == ["- feat: new endpoint"]


def test_render_changelog_section_groups_and_orders() -> None:
    bodies = [
        "fix: correct path\n",
        "feat: new endpoint\n",
        "chore(release): 0.2.3 via guarded release helper\n",
    ]
    section = release._render_changelog_section("0.2.3", "2026-08-04", bodies)
    assert section.startswith("## [0.2.3] - 2026-08-04\n\n")
    assert "### Added\n- feat: new endpoint" in section
    assert "### Fixed\n- fix: correct path" in section
    assert "chore(release):" not in section
    # Added appears before Fixed (Keep-a-Changelog order)
    assert section.index("### Added") < section.index("### Fixed")


def test_render_changelog_section_falls_back_when_empty() -> None:
    section = release._render_changelog_section("0.2.3", "2026-08-04", ())
    assert "- No notable changes." in section
    assert "### Changed" in section
