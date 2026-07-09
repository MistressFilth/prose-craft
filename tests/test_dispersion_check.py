import pytest

import dispersion_check as D

# Fixture texts and their expected signal values below were computed by
# running the validated research algorithm (workbench/reinhart/instrument/
# dispersion.py's measure_set) directly against these exact strings -- not
# guessed. See docs/superpowers/plans/2026-07-09-dispersion-checker.md
# Task 1 for the calibration run.

CONVERGED_DRAFTS = [
    "Status: three items remain in the queue. Review each before Friday. Escalate anything blocked.",
    "Status: two items remain in the queue. Review each before Friday. Escalate anything blocked.",
    "Status: four items remain in the queue. Review each before Friday. Escalate anything blocked.",
]

VARIED_DRAFTS = [
    "Status: three items remain in the queue. Review each before Friday. Escalate anything blocked.",
    "Hey team, quick update -- we're down to a handful of open items this week, and I want eyes on the two that keep stalling in review.\n\nIf you have bandwidth today, take a pass at the blocked ones first; everything else can wait until next sprint.",
    "## Weekly queue check\n\n- 6 items open\n- 2 blocked on legal\n- 1 needs a design decision before Thursday\n\nPing me if you're free to unblock any of these.",
]


def test_measure_set_requires_at_least_two_drafts():
    with pytest.raises(ValueError):
        D.measure_set(["only one draft here."])


def test_converged_set_scores_low_dispersion():
    profile = D.measure_set(CONVERGED_DRAFTS)
    assert profile["n"] == 3
    assert profile["altitude_1"]["dispersion_index"] == pytest.approx(0.189, abs=0.01)
    assert profile["altitude_2"]["distinct_opener_frames_fraction"] == pytest.approx(0.333, abs=0.01)
    assert profile["altitude_2"]["mean_opener_similarity"] == pytest.approx(1.0, abs=0.01)


def test_varied_set_scores_high_dispersion():
    profile = D.measure_set(VARIED_DRAFTS)
    assert profile["n"] == 3
    assert profile["altitude_1"]["dispersion_index"] == pytest.approx(0.908, abs=0.01)
    assert profile["altitude_2"]["distinct_opener_frames_fraction"] == pytest.approx(1.0, abs=0.01)


def test_converged_scores_lower_than_varied():
    converged = D.measure_set(CONVERGED_DRAFTS)
    varied = D.measure_set(VARIED_DRAFTS)
    assert converged["altitude_1"]["dispersion_index"] < varied["altitude_1"]["dispersion_index"]
    assert converged["altitude_2"]["dispersion_index"] < varied["altitude_2"]["dispersion_index"]


def test_strip_front_matter_removes_leading_yaml_block():
    text = "---\nvoice: kuudere\naudience: private\n---\nThe body starts here."
    assert D.strip_front_matter(text) == "The body starts here."


def test_strip_front_matter_leaves_text_without_front_matter_unchanged():
    text = "No front matter here at all."
    assert D.strip_front_matter(text) == text


def test_main_cli_requires_at_least_two_paths(tmp_path, capsys):
    only_file = tmp_path / "a.md"
    only_file.write_text("Just one draft.")
    rc = D.main([str(only_file)])
    assert rc == 2
    assert "at least 2" in capsys.readouterr().err


def test_main_cli_reports_missing_file(tmp_path, capsys):
    real_file = tmp_path / "a.md"
    real_file.write_text("Draft one. Draft one continues.")
    missing = tmp_path / "does-not-exist.md"
    rc = D.main([str(real_file), str(missing)])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_cli_json_output(tmp_path, capsys):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text(CONVERGED_DRAFTS[0])
    b.write_text(CONVERGED_DRAFTS[1])
    rc = D.main([str(a), str(b), "--json"])
    assert rc == 0
    import json

    out = json.loads(capsys.readouterr().out)
    assert out["n"] == 2
    assert "altitude_1" in out
    assert "altitude_2" in out
    assert out["files"] == [str(a), str(b)]
