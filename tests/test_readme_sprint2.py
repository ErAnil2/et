from pathlib import Path

README = Path(__file__).parent.parent / "README.md"


def test_readme_mentions_toi_ga_setup():
    text = README.read_text(encoding="utf-8")
    assert "TOI_GA_SA_JSON" in text
    assert "TOI_GA_PROPERTY_ID" in text
    assert "230487101" in text


def test_readme_mentions_spacy_model_download():
    text = README.read_text(encoding="utf-8")
    assert "python -m spacy download en_core_web_md" in text


def test_readme_mentions_llm_extra():
    text = README.read_text(encoding="utf-8")
    assert 'pip install -e ".[llm]"' in text or "pip install -e '.[llm]'" in text


def test_readme_has_sprint2_acceptance_checklist():
    text = README.read_text(encoding="utf-8")
    assert "resolve-urls" in text
    assert "match-outcomes" in text
    assert "tag-entities" in text
    assert "toi-ga" in text
