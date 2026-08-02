from prose_craft.analysis.clause_density import measure_clause_density


def test_empty_text():
    cd = measure_clause_density("", [])
    assert cd.ppc_per_1k == 0.0
    assert cd.agentless_passive_per_1k == 0.0


def test_present_participle_clause_counted():
    text = "Walking home, she saw the dog. Running fast, he caught it."
    words = text.split()
    cd = measure_clause_density(text, words)
    assert cd.ppc_per_1k > 0


def test_agentless_passive_counted():
    text = "The ball was thrown. The cake was eaten."
    words = text.split()
    cd = measure_clause_density(text, words)
    assert cd.agentless_passive_per_1k > 0


def test_no_false_positive_on_simple_sentence():
    text = "She walked home."
    words = text.split()
    cd = measure_clause_density(text, words)
    assert cd.ppc_per_1k == 0.0
    assert cd.agentless_passive_per_1k == 0.0
