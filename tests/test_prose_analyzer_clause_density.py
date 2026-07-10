import prose_analyzer as PA


def test_render_clause_density_empty_when_no_result_and_no_error():
    assert PA.render_clause_density(None, None) == ""


def test_render_clause_density_shows_error():
    section = PA.render_clause_density(None, "clause_density_check.py timed out")
    assert "Clause density" in section
    assert "timed out" in section


def test_render_clause_density_no_surface_shows_raw_rate_only():
    result = {
        "draft": {
            "word_count": 300,
            "ppc_count": 3,
            "ppc_per_1k": 10.0,
            "agentless_passive_count": 1,
            "agentless_passive_per_1k": 3.3,
        },
        "reference": None,
    }
    section = PA.render_clause_density(result, None)
    assert "10.0/1k" in section
    assert "no surface declared" in section.lower()
    assert "not a target" in section.lower()
    for banned_word in ("collapsed", "flagged", "warning", "threshold"):
        assert banned_word not in section.lower()


def test_render_clause_density_n_zero_shows_no_history_yet():
    result = {
        "draft": {
            "word_count": 300,
            "ppc_count": 3,
            "ppc_per_1k": 10.0,
            "agentless_passive_count": 1,
            "agentless_passive_per_1k": 3.3,
        },
        "reference": {"n": 0, "mean_ppc_per_1k": None, "mean_agentless_passive_per_1k": None},
    }
    section = PA.render_clause_density(result, None)
    assert "no comparison history yet" in section.lower()
    assert "not a target" in section.lower()


def test_render_clause_density_with_history_shows_mean_and_n():
    result = {
        "draft": {
            "word_count": 300,
            "ppc_count": 3,
            "ppc_per_1k": 10.0,
            "agentless_passive_count": 1,
            "agentless_passive_per_1k": 3.3,
        },
        "reference": {
            "n": 4,
            "mean_ppc_per_1k": 8.5,
            "mean_agentless_passive_per_1k": 2.0,
        },
    }
    section = PA.render_clause_density(result, None)
    assert "10.0/1k" in section
    assert "8.5/1k" in section
    assert "n=4" in section
    assert "not a target" in section.lower()


def test_run_clause_density_check_end_to_end_no_surface(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugin_data"))
    draft = tmp_path / "draft.md"
    draft.write_text("She walked through the door and paused.")
    result, error = PA.run_clause_density_check(str(draft), "kuudere", None)
    assert error is None
    assert result["reference"] is None


def test_run_clause_density_check_end_to_end_with_surface(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugin_data"))
    draft = tmp_path / "draft.md"
    draft.write_text("She walked through the door and paused.")
    result, error = PA.run_clause_density_check(str(draft), "kuudere", "verification_log")
    assert error is None
    assert result["reference"]["n"] == 0
