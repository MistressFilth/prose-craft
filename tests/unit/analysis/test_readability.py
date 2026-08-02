from prose_craft.analysis.readability import flesch_grade_level, flesch_reading_ease


def test_flesch_simple_text():
    # Mean sentence 10, avg syllables 1.5 -> 206.835 - 10.15 - 126.9 = 69.785
    score = flesch_reading_ease(mean_sentence_length=10.0, avg_syllables_per_word=1.5)
    assert 69.0 <= score <= 71.0


def test_flesch_clamped():
    # Pathological inputs should clamp to [0, 100]
    assert flesch_reading_ease(mean_sentence_length=100.0, avg_syllables_per_word=5.0) == 0.0
    assert flesch_reading_ease(mean_sentence_length=1.0, avg_syllables_per_word=1.0) == 100.0


def test_grade_level_thresholds():
    assert "Graduate" in flesch_grade_level(20.0)
    assert "College" in flesch_grade_level(40.0)
    assert "Standard" in flesch_grade_level(65.0)
    assert "Easy" in flesch_grade_level(75.0)
    assert "Very Easy" in flesch_grade_level(95.0)
