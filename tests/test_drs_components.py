import re

from discover_intel.scoring.drs_components import (
    eeat, headline, image, originality, technical, timeliness,
)

CFG_HEADLINE = {
    "min_chars": 40,
    "max_chars": 110,
    "require_entity_and_fact": True,
}
CFG_IMAGE = {"min_width_px": 1200, "reject_square_aspect_ratio": True,
             "check_max_image_preview_large": True}
CFG_EEAT = {"ymyl_lanes": ["personal_finance_benefits"], "require_author_ymyl": True}
CFG_ORIG = {"fuzzy_threshold_max": 0.85}
CFG_TIMELINESS = {"entity_tos_floor": 45.0, "decay_hours_from_peak": 36.0}
CFG_TECH = {"without_url_default": 0.5}


def test_headline_pass_clean_title(spacy_nlp):
    score, reasons = headline(
        title="Fed cuts rates by 25 bps as Powell signals slower path",
        nlp=spacy_nlp, clickbait_regexes=[], config=CFG_HEADLINE,
    )
    assert score >= 0.8


def test_headline_fails_short(spacy_nlp):
    score, reasons = headline(
        title="Fed cut", nlp=spacy_nlp, clickbait_regexes=[], config=CFG_HEADLINE,
    )
    assert score == 0.0
    assert any("chars" in r for r in reasons)


def test_headline_fails_long(spacy_nlp):
    long_title = "Fed cuts rates by " + ("very " * 40) + "much"
    score, reasons = headline(
        title=long_title, nlp=spacy_nlp, clickbait_regexes=[], config=CFG_HEADLINE,
    )
    assert score == 0.0


def test_headline_fails_clickbait(spacy_nlp):
    cb = [re.compile(r"you won'?t believe", re.IGNORECASE)]
    score, reasons = headline(
        title="You won't believe what happened at the Fed meeting today wow",
        nlp=spacy_nlp, clickbait_regexes=cb, config=CFG_HEADLINE,
    )
    assert score == 0.0
    assert any("clickbait" in r.lower() for r in reasons)


def test_image_pass_wide():
    score, reasons = image(image_width=1600, aspect_ratio=16/9,
                           url=None, config=CFG_IMAGE)
    assert score >= 0.8


def test_image_fail_narrow():
    score, reasons = image(image_width=800, aspect_ratio=16/9,
                           url=None, config=CFG_IMAGE)
    assert score == 0.0


def test_image_penalize_square():
    score, reasons = image(image_width=1600, aspect_ratio=1.0,
                           url=None, config=CFG_IMAGE)
    assert score < 1.0


def test_eeat_pass_full():
    score, reasons = eeat(
        author="Jane Doe", published_at="2026-09-24T15:00:00Z",
        body_text="Some body with a link https://source.example.com/x.",
        entity_lanes=["finance_markets"], config=CFG_EEAT,
    )
    assert score >= 0.5


def test_eeat_ymyl_missing_author_fails():
    score, reasons = eeat(
        author="", published_at="2026-09-24T15:00:00Z",
        body_text=None,
        entity_lanes=["personal_finance_benefits"], config=CFG_EEAT,
    )
    assert score == 0.0


def test_originality_no_competitors_returns_one():
    score, reasons = originality(
        title="Some novel headline", entity="X", conn=None, config=CFG_ORIG,
    )
    assert score == 1.0


def test_timeliness_default_when_no_conn():
    score, reasons = timeliness(entity="Fed", conn=None, config=CFG_TIMELINESS)
    assert score == 0.5


def test_technical_default_without_url():
    score, reasons = technical(url=None, config=CFG_TECH)
    assert score == 0.5
