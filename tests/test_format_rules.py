import re
from pathlib import Path

import yaml

CONFIG = Path(__file__).parent.parent / "config" / "format_rules.yaml"


def test_rules_is_ordered_list():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 5


def test_first_rule_is_trivia():
    """Trivia's 'In YYYY...' is distinctive; checking it first avoids
    false-positive news matches."""
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert data[0]["format"] == "trivia"


def test_last_rule_is_news_catchall():
    """News must be the default (pattern '.*') so every item gets a label."""
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert data[-1]["format"] == "news"
    assert data[-1]["pattern"] == ".*"


def test_all_patterns_compile():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    for rule in data:
        re.compile(rule["pattern"], re.IGNORECASE | re.VERBOSE)


def test_trivia_matches_real_title():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    rx = re.compile(data[0]["pattern"], re.IGNORECASE | re.VERBOSE)
    assert rx.search("in 1957 elvis presley bought graceland")


def test_service_matches_how_to():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    service = next(r for r in data if r["format"] == "service")
    rx = re.compile(service["pattern"], re.IGNORECASE | re.VERBOSE)
    assert rx.search("how to file for social security cola in 2027")
    assert rx.search("when should you stop mowing your lawn")


def test_expected_formats_present():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    formats = {r["format"] for r in data}
    assert {"trivia", "service", "opinion", "analysis", "atmosphere", "news"} <= formats
