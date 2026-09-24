import re
from pathlib import Path

CFG = Path(__file__).parent.parent / "config" / "clickbait_patterns.txt"


def _load_regexes() -> list[re.Pattern[str]]:
    lines = [ln.strip() for ln in CFG.read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    return [re.compile(ln, re.IGNORECASE) for ln in lines]


def test_all_patterns_compile():
    regexes = _load_regexes()
    assert len(regexes) >= 10


CLICKBAIT_TITLES = [
    "You won't believe what happened next",
    "This one weird trick doctors hate",
    "Guess what these celebrities look like now",
    "You'll never guess who won this year",
    "Number 5 will shock you completely",
]

CLEAN_TITLES = [
    "Fed cuts rates by 25 bps as Powell signals slower path",
    "JCPenney to close 20 more stores in Q4",
    "Robin Williams' Napa estate sells for $18 million",
    "New bill proposes 32-hour work week",
]


def test_clickbait_titles_match():
    regexes = _load_regexes()
    for title in CLICKBAIT_TITLES:
        matches = [rx.pattern for rx in regexes if rx.search(title)]
        assert matches, f"no clickbait pattern hit: {title!r}"


def test_clean_titles_do_not_match():
    regexes = _load_regexes()
    for title in CLEAN_TITLES:
        matches = [rx.pattern for rx in regexes if rx.search(title)]
        assert not matches, f"clean title flagged: {title!r} by {matches}"
