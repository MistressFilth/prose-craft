import io
import json
import os
import sys
from pathlib import Path

import pytest

import prose_analyzer as PA


def _write(path: Path, voice: str, body: str, mtime: float | None = None) -> None:
    path.write_text(f"---\nvoice: {voice}\n---\n{body}")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


# Explicit, deterministic mtimes rather than time.sleep() between writes --
# some filesystems (notably WSL mounts) have coarser mtime resolution than
# a short sleep guarantees, which would make ordering-dependent tests flaky.
_OLDER_MTIME = 1_700_000_000.0
_NEWER_MTIME = 1_700_000_100.0


def test_find_dispersion_siblings_matches_voice_and_earlier_mtime(tmp_path):
    older = tmp_path / "b1_draft1.md"
    _write(older, "kuudere", "Status: three items remain.", mtime=_OLDER_MTIME)
    newer = tmp_path / "b1_draft2.md"
    _write(newer, "kuudere", "Status: two items remain.", mtime=_NEWER_MTIME)

    siblings = PA.find_dispersion_siblings(str(newer), "kuudere")
    assert siblings == [str(older.resolve())]


def test_find_dispersion_siblings_excludes_different_voice(tmp_path):
    older = tmp_path / "b1_draft1.md"
    _write(older, "classic", "An old memo, retro register.", mtime=_OLDER_MTIME)
    newer = tmp_path / "b1_draft2.md"
    _write(newer, "kuudere", "Status: two items remain.", mtime=_NEWER_MTIME)

    siblings = PA.find_dispersion_siblings(str(newer), "kuudere")
    assert siblings == []


def test_find_dispersion_siblings_empty_when_first_draft(tmp_path):
    only = tmp_path / "b1_draft1.md"
    _write(only, "kuudere", "Status: three items remain.")
    assert PA.find_dispersion_siblings(str(only), "kuudere") == []


def test_render_dispersion_empty_when_no_profile_and_no_error():
    assert PA.render_dispersion(None, None) == ""


def test_render_dispersion_shows_error():
    section = PA.render_dispersion(None, "dispersion_check.py timed out")
    assert "Dispersion" in section
    assert "timed out" in section


def test_render_dispersion_reports_raw_signals_no_verdict():
    profile = {
        "n": 2,
        "altitude_1": {
            "content_jaccard": 0.5,
            "trigram_jaccard": 0.4,
            "shared_mass": 0.6,
            "dispersion_index": 0.5,
        },
        "altitude_2": {
            "distinct_opener_frames_fraction": 0.5,
            "mean_opener_similarity": 0.8,
            "distinct_structure_sigs_fraction": 0.5,
            "mean_structural_similarity": 0.9,
            "dispersion_index": 0.5,
        },
        "_raw": {"opener_frames": [], "structure_sigs": []},
    }
    section = PA.render_dispersion(profile, None)
    assert "content_jaccard: 0.500" in section
    assert "dispersion_index: 0.500" in section
    # Hard rule: no verdict/threshold language anywhere in the rendering.
    for banned_word in ("collapsed", "converged", "flagged", "warning"):
        assert banned_word not in section.lower()


def test_run_dispersion_check_end_to_end(tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("Status: three items remain in the queue.")
    b.write_text("Status: two items remain in the queue.")
    profile, error = PA.run_dispersion_check(str(a), [str(b)])
    assert error is None
    assert profile is not None
    assert profile["n"] == 2


_DISPERSION_PROFILE = {
    "n": 2,
    "altitude_1": {
        "content_jaccard": 0.5,
        "trigram_jaccard": 0.4,
        "shared_mass": 0.6,
        "dispersion_index": 0.5,
    },
    "altitude_2": {
        "distinct_opener_frames_fraction": 0.5,
        "mean_opener_similarity": 0.8,
        "distinct_structure_sigs_fraction": 0.5,
        "mean_structural_similarity": 0.9,
        "dispersion_index": 0.5,
    },
}


def _run_main_with_payload(monkeypatch, file_path):
    payload = json.dumps(
        {"agent_type": "voice-checker", "tool_input": {"file_path": str(file_path)}}
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))


def test_main_emits_message_when_voice_clean_but_dispersion_nonempty(
    tmp_path, monkeypatch, capsys
):
    """Clean voice check (empty voice section) + real siblings (non-empty
    dispersion section) must still surface a systemMessage -- the hook
    should not exit silently just because the voice section alone is
    empty. Regression guard for the combined dual early-exit added
    alongside the dispersion pipeline."""
    draft = tmp_path / "draft.md"
    _write(draft, "kuudere", "Status: two items remain.")

    monkeypatch.setattr(PA, "run_voice_check", lambda file_path, voice_name: (None, None))
    monkeypatch.setattr(
        PA,
        "find_dispersion_siblings",
        lambda file_path, voice_name: [str(tmp_path / "sibling.md")],
    )
    monkeypatch.setattr(
        PA,
        "run_dispersion_check",
        lambda new_draft_path, sibling_paths: (_DISPERSION_PROFILE, None),
    )
    _run_main_with_payload(monkeypatch, draft)

    PA.main()

    captured = capsys.readouterr()
    assert captured.out.strip(), "expected a systemMessage, got silent exit"
    message = json.loads(captured.out)["systemMessage"]
    assert "# Dispersion" in message
    assert "# Voice" not in message


def test_main_exits_silently_when_both_sections_empty(tmp_path, monkeypatch, capsys):
    """Clean voice check and no siblings to compare against: both sections
    are empty, so the hook must still exit silently (pre-existing
    behavior, guarded against regressing)."""
    draft = tmp_path / "draft.md"
    _write(draft, "kuudere", "Status: two items remain.")

    monkeypatch.setattr(PA, "run_voice_check", lambda file_path, voice_name: (None, None))
    monkeypatch.setattr(PA, "find_dispersion_siblings", lambda file_path, voice_name: [])
    _run_main_with_payload(monkeypatch, draft)

    with pytest.raises(SystemExit) as excinfo:
        PA.main()

    assert excinfo.value.code == 0
    assert capsys.readouterr().out == ""
