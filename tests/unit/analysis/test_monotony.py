from prose_craft.analysis.monotony import monotony_zones


def test_no_zones_when_lengths_vary():
    lengths = [10, 20, 8, 25, 12, 30]
    assert monotony_zones(lengths) == []


def test_detects_long_streak():
    # Five consecutive lengths within +/-3 of each other
    lengths = [10, 11, 12, 11, 13, 10, 25]
    zones = monotony_zones(lengths)
    assert len(zones) == 1
    start, end = zones[0]
    assert start == 0
    assert end == 5


def test_does_not_flag_short_streaks():
    # Three consecutive within tolerance is not monotony
    lengths = [10, 11, 12, 30, 10, 11, 12, 30]
    assert monotony_zones(lengths) == []


def test_zone_at_end_of_text():
    lengths = [25, 10, 11, 12, 11, 13]
    zones = monotony_zones(lengths)
    assert len(zones) == 1
    assert zones[0] == (1, 5)
