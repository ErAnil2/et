import re

from discover_intel.analysis.tag_entities import run_format


def _compile_rules(rules: list[dict[str, str]]) -> list[tuple[str, re.Pattern[str]]]:
    return [(r["format"], re.compile(r["pattern"], re.IGNORECASE | re.VERBOSE))
            for r in rules]


def test_run_format_trivia_first():
    rules = _compile_rules([
        {"format": "trivia", "pattern": r"^in\ \d{4}"},
        {"format": "service", "pattern": r"how\ to"},
        {"format": "news", "pattern": r".*"},
    ])
    assert run_format("in 1957 Elvis bought Graceland", rules) == "trivia"


def test_run_format_service_matches_how_to():
    rules = _compile_rules([
        {"format": "trivia", "pattern": r"^in\ \d{4}"},
        {"format": "service", "pattern": r"\bhow\ to\b"},
        {"format": "news", "pattern": r".*"},
    ])
    assert run_format("how to file for COLA in 2027", rules) == "service"


def test_run_format_falls_through_to_news():
    rules = _compile_rules([
        {"format": "trivia", "pattern": r"^in\ \d{4}"},
        {"format": "service", "pattern": r"how\ to"},
        {"format": "news", "pattern": r".*"},
    ])
    assert run_format("Fed cuts rates by 25 bps", rules) == "news"


def test_run_format_empty_returns_news():
    rules = _compile_rules([
        {"format": "trivia", "pattern": r"^in\ \d{4}"},
        {"format": "news", "pattern": r".*"},
    ])
    assert run_format("", rules) == "news"
