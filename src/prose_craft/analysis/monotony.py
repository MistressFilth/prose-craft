"""Detect consecutive same-length sentence zones."""

from __future__ import annotations


def monotony_zones(
    sent_lengths: list[int],
    tolerance: int = 3,
    min_streak: int = 4,
) -> list[tuple[int, int]]:
    """Return zones of 4+ consecutive sentences within +/-tolerance words.

    A zone is a (start_index, end_index_inclusive) pair. Empty input
    returns empty list.
    """
    if len(sent_lengths) < min_streak:
        return []
    zones: list[tuple[int, int]] = []
    streak_start = 0
    for i in range(1, len(sent_lengths)):
        if abs(sent_lengths[i] - sent_lengths[i - 1]) <= tolerance:
            continue
        if i - streak_start >= min_streak:
            zones.append((streak_start, i - 1))
        streak_start = i
    if len(sent_lengths) - streak_start >= min_streak:
        zones.append((streak_start, len(sent_lengths) - 1))
    return zones
