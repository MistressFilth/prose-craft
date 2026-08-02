from prose_craft.analysis.dispersion import measure_set


def test_single_draft_no_siblings():
    profile = measure_set("one two three four", [])
    assert profile.n == 1
    assert profile.altitude_1.dispersion_index == 0.0
    assert profile.altitude_2.distinct_opener_frames_fraction == 0.0


def test_identical_drafts_have_zero_dispersion():
    text = "The cat sat on the mat. The dog ran in the park."
    profile = measure_set(text, [text, text])
    assert profile.n == 3
    assert profile.altitude_1.dispersion_index == 0.0


def test_distinct_drafts_have_positive_dispersion():
    new = "She walked home slowly through the rain."
    sib_a = "The cat sat on the mat and purred."
    sib_b = "Birds sang in the bright morning sky."
    profile = measure_set(new, [sib_a, sib_b])
    assert profile.n == 3
    assert profile.altitude_1.dispersion_index > 0.0
