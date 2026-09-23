import re

from discover_intel.analysis.tag_entities import run_lanes


def _compile(patterns: dict[str, str]) -> dict[str, re.Pattern[str]]:
    return {slug: re.compile(p, re.IGNORECASE | re.VERBOSE)
            for slug, p in patterns.items()}


def test_run_lanes_returns_matching_slugs():
    patterns = _compile({
        "money": r"\b(fed|federal\ reserve|mortgage)\b",
        "real_estate": r"\b(mansion|acres?)\b",
    })
    hits = run_lanes("Fed cuts rates and Bezos buys a 200 acre ranch", patterns)
    assert "money" in hits
    assert "real_estate" in hits


def test_run_lanes_returns_empty_on_no_match():
    patterns = _compile({"tech": r"\b(gpu|semiconductor)\b"})
    assert run_lanes("the weather is nice today", patterns) == []


def test_run_lanes_deduplicates():
    patterns = _compile({"money": r"\bfed\b"})
    hits = run_lanes("fed announces fed policy shift", patterns)
    assert hits == ["money"]
