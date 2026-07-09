import json
import os
from pathlib import Path

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
