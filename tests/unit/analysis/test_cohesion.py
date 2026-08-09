from prose_craft.analysis.cohesion import (
    ConnectiveCounts,
    connectives_per_100,
    count_connectives,
)


def test_count_connectives_basic():
    text = "Because it rained, we stayed inside. Then we ate."
    counts = count_connectives(text)
    assert counts.causal >= 1
    assert counts.temporal >= 1


def test_count_connectives_empty():
    counts = count_connectives("")
    assert counts.causal == 0
    assert counts.temporal == 0
    assert counts.additive == 0
    assert counts.adversative == 0


def test_connectives_per_100():
    counts = ConnectiveCounts(causal=2, temporal=2, additive=0, adversative=0)
    assert connectives_per_100(counts, 100) == 4.0
    assert connectives_per_100(counts, 0) == 0.0
