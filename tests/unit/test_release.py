from __future__ import annotations

import pytest

from scripts.release import classify_bump, next_version


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


@pytest.mark.parametrize(
    ("current", "bump", "expected"),
    [("0.1.0", "patch", "0.1.1"), ("0.1.0", "minor", "0.2.0"), ("0.1.0", "major", "1.0.0")],
)
def test_next_version(current: str, bump: str, expected: str) -> None:
    assert next_version(current, bump) == expected
