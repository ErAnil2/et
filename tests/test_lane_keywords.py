import re
from pathlib import Path

import yaml

CONFIG = Path(__file__).parent.parent / "config" / "lane_keywords.yaml"

EXPECTED_LANES = {
    "real_estate_wealth", "personal_finance_benefits", "retail_business_pulse",
    "politics_policy", "crime_courts", "food_grocery_prices", "weather_climate",
    "celebrity_entertainment", "obituary_memorial", "human_interest",
    "sports_athletics", "religion_faith", "tech_ai", "science_space",
    "health_medicine", "auto_transport", "animals_wildlife",
    "trivia_history_novelty", "oddity_novelty", "local_us", "finance_markets",
    "labor_workforce", "immigration_border",
}


def test_lane_yaml_has_23_lanes():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert len(data) == 23, f"expected 23 lanes, got {len(data)}: {sorted(data)}"


def test_lane_slugs_match_expected():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert set(data.keys()) == EXPECTED_LANES


def test_every_lane_has_label_and_pattern():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    for slug, entry in data.items():
        assert "label" in entry, f"{slug} missing label"
        assert "pattern" in entry, f"{slug} missing pattern"
        assert isinstance(entry["pattern"], str)


def test_every_pattern_compiles_as_regex():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    for slug, entry in data.items():
        try:
            re.compile(entry["pattern"], re.IGNORECASE | re.VERBOSE)
        except re.error as exc:
            raise AssertionError(f"{slug} pattern invalid: {exc}") from exc


def test_real_estate_wealth_matches_real_title():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    rx = re.compile(data["real_estate_wealth"]["pattern"], re.IGNORECASE | re.VERBOSE)
    real = "in 2013 pink paid nearly 9 million for a 200 acre california ranch"
    assert rx.search(real), "should hit acres/ranch keywords"


def test_trivia_history_matches_in_year_pattern():
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    rx = re.compile(data["trivia_history_novelty"]["pattern"], re.IGNORECASE | re.VERBOSE)
    real = "in 1957 elvis presley bought graceland s 13 8 acres for 102 500"
    assert rx.search(real), "should hit 'in YYYY' pattern"
