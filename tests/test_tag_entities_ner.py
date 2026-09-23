from discover_intel.analysis.tag_entities import run_ner


def test_run_ner_extracts_person_and_org(spacy_nlp):
    title = "Elon Musk announced Tesla layoffs today"
    ents = run_ner(spacy_nlp, title)
    kinds = {e_type for _, e_type in ents}
    assert "PERSON" in kinds or "ORG" in kinds


def test_run_ner_filters_by_type(spacy_nlp):
    """Only PERSON/ORG/GPE/PRODUCT/EVENT are returned; DATE/CARDINAL are dropped."""
    title = "In 2026 the FDA approved a new drug"
    ents = run_ner(spacy_nlp, title)
    allowed = {"PERSON", "ORG", "GPE", "PRODUCT", "EVENT"}
    for _, t in ents:
        assert t in allowed


def test_run_ner_on_empty_string(spacy_nlp):
    assert run_ner(spacy_nlp, "") == []
