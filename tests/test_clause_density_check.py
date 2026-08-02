import json

import pytest

import clause_density_check as CD

# Fixture texts and their expected counts were computed by running the real,
# validated methodology directly (tell_meter.py's 4 regex patterns UNIONED
# with tag_chunker.py's 2 tag-based match functions, deduplicated by
# substring-containment of overlapping spans within the same sentence — the
# same `_tag_chunker_counts` helper workbench/reinhart/instrument/
# run_r6_h11.py uses for real measurement rounds) against these exact
# strings, using workbench/reinhart's .venv (which has nltk + the tagger
# data already provisioned). See docs/superpowers/plans/
# 2026-07-09-clause-density-diagnostic.md Task 1 for the calibration run.

PPC_DENSE = (
    "Walking through the door, she paused. The report, detailing every "
    "incident, sat heavy on the desk. He left the room, whistling an old "
    "tune. A check flagging the discrepancy arrived that afternoon."
)  # 32 words -> ppc=4, agentless_passive=0

PASSIVE_DENSE = (
    "The report was written last night. The window was quickly broken "
    "during the storm. Mistakes were made across the department. The "
    "proposal gets rejected every quarter."
)  # 26 words -> ppc=0, agentless_passive=4

PLAIN = (
    "She walked through the door and paused. He read the report and left "
    "the office. The team made mistakes. They reject proposals every "
    "quarter."
)  # 24 words -> ppc=0, agentless_passive=0


def test_measure_ppc_dense_fixture():
    result = CD.measure_clause_density(PPC_DENSE)
    assert result["word_count"] == 32
    assert result["ppc_count"] == 4
    assert result["agentless_passive_count"] == 0
    assert result["ppc_per_1k"] == pytest.approx(125.0, abs=0.5)
    assert result["agentless_passive_per_1k"] == pytest.approx(0.0, abs=0.01)


def test_measure_passive_dense_fixture():
    result = CD.measure_clause_density(PASSIVE_DENSE)
    assert result["word_count"] == 26
    assert result["ppc_count"] == 0
    assert result["agentless_passive_count"] == 4
    assert result["ppc_per_1k"] == pytest.approx(0.0, abs=0.01)
    assert result["agentless_passive_per_1k"] == pytest.approx(153.8, abs=1.0)


def test_measure_plain_fixture_has_no_matches():
    result = CD.measure_clause_density(PLAIN)
    assert result["ppc_count"] == 0
    assert result["agentless_passive_count"] == 0


def test_measure_empty_text_does_not_divide_by_zero():
    result = CD.measure_clause_density("")
    assert result["word_count"] == 0
    assert result["ppc_per_1k"] == 0.0
    assert result["agentless_passive_per_1k"] == 0.0


def test_ensure_nltk_ready_succeeds_when_data_present():
    # This dev/CI environment has the tagger data provisioned; this just
    # exercises the real probe path without raising.
    CD._ensure_nltk_ready()


def test_ensure_nltk_ready_raises_clear_error_when_download_fails(monkeypatch):
    def _always_lookup_error(*args, **kwargs):
        raise LookupError("no data")

    monkeypatch.setattr(CD.nltk, "pos_tag", _always_lookup_error)
    monkeypatch.setattr(CD.nltk, "download", lambda *a, **k: None)

    with pytest.raises(RuntimeError) as excinfo:
        CD._ensure_nltk_ready()
    assert "python -m nltk.downloader" in str(excinfo.value)


def test_history_root_uses_claude_plugin_data_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    assert CD.history_root() == tmp_path / "clause_density_history"


def test_read_history_returns_empty_list_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    assert CD.read_history("kuudere", "verification_log") == []


def test_append_then_read_history_round_trips(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    record = {
        "voice": "kuudere",
        "surface": "verification_log",
        "word_count": 300,
        "ppc_count": 3,
        "ppc_per_1k": 10.0,
        "agentless_passive_count": 1,
        "agentless_passive_per_1k": 3.3,
    }
    CD.append_history("kuudere", "verification_log", record)
    records = CD.read_history("kuudere", "verification_log")
    assert records == [record]


def test_read_history_skips_corrupt_lines(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    path = CD.history_root() / "kuudere" / "verification_log.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"ppc_per_1k": 5.0, "agentless_passive_per_1k": 1.0}\n'
        "not valid json at all\n"
        '{"ppc_per_1k": 7.0, "agentless_passive_per_1k": 2.0}\n'
    )
    records = CD.read_history("kuudere", "verification_log")
    assert len(records) == 2


def test_compute_reference_empty_history():
    reference = CD.compute_reference([])
    assert reference == {
        "n": 0,
        "mean_ppc_per_1k": None,
        "mean_agentless_passive_per_1k": None,
    }


def test_compute_reference_averages_prior_records():
    records = [
        {"ppc_per_1k": 4.0, "agentless_passive_per_1k": 2.0},
        {"ppc_per_1k": 6.0, "agentless_passive_per_1k": 4.0},
    ]
    reference = CD.compute_reference(records)
    assert reference["n"] == 2
    assert reference["mean_ppc_per_1k"] == pytest.approx(5.0)
    assert reference["mean_agentless_passive_per_1k"] == pytest.approx(3.0)


def test_compute_reference_skips_records_missing_a_key():
    records = [
        {"ppc_per_1k": 4.0, "agentless_passive_per_1k": 2.0},
        {"ppc_per_1k": 8.0},  # missing agentless_passive_per_1k
    ]
    # A record missing either key is excluded entirely (not just from the
    # mean it lacks), matching read_history's skip-malformed-line tolerance.
    reference = CD.compute_reference(records)
    assert reference["n"] == 1
    assert reference["mean_ppc_per_1k"] == pytest.approx(4.0)
    assert reference["mean_agentless_passive_per_1k"] == pytest.approx(2.0)


def test_main_cli_no_surface_has_null_reference_and_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    draft = tmp_path / "draft.md"
    draft.write_text(PLAIN)
    rc = CD.main([str(draft), "--voice", "kuudere", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["reference"] is None
    assert not (tmp_path / "clause_density_history").exists()


def test_main_cli_with_surface_first_draft_has_n_zero_reference(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    draft = tmp_path / "draft1.md"
    draft.write_text(PPC_DENSE)
    rc = CD.main([str(draft), "--voice", "kuudere", "--surface", "verification_log", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["reference"]["n"] == 0
    records = CD.read_history("kuudere", "verification_log")
    assert len(records) == 1
    assert records[0]["ppc_per_1k"] == pytest.approx(out["draft"]["ppc_per_1k"])


def test_main_cli_second_draft_compares_against_first_not_itself(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
    draft1 = tmp_path / "draft1.md"
    draft1.write_text(PPC_DENSE)
    CD.main([str(draft1), "--voice", "kuudere", "--surface", "verification_log", "--json"])
    capsys.readouterr()

    draft2 = tmp_path / "draft2.md"
    draft2.write_text(PLAIN)
    rc = CD.main([str(draft2), "--voice", "kuudere", "--surface", "verification_log", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["reference"]["n"] == 1
    first_measured = CD.measure_clause_density(PPC_DENSE)
    assert out["reference"]["mean_ppc_per_1k"] == pytest.approx(first_measured["ppc_per_1k"])
    records = CD.read_history("kuudere", "verification_log")
    assert len(records) == 2
