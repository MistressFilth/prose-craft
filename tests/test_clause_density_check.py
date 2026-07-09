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
