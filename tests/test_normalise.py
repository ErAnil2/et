from pathlib import Path

from discover_intel.analysis.normalise import load_aliases, normalise_title

CONFIG = Path(__file__).parent.parent / "config" / "entity_aliases.csv"


def test_load_aliases_returns_case_insensitive_dict():
    d = load_aliases(CONFIG)
    assert d.get("fed") == "Federal Reserve"
    assert d.get("FED") == "Federal Reserve"
    assert d.get("Fed") == "Federal Reserve"


def test_normalise_lowercases():
    aliases = {"Fed": "Federal Reserve"}
    result = normalise_title("Fed CUTS RATES", aliases)
    assert result == "federal reserve cuts rates"


def test_normalise_strips_honorifics():
    aliases = {}
    result = normalise_title("Dr. Musk said Mrs. Bezos gave money", aliases)
    assert "dr." not in result
    assert "mrs." not in result
    assert "musk" in result


def test_normalise_applies_aliases_case_insensitively():
    aliases = {"musk": "elon musk"}
    result = normalise_title("Musk announced X", aliases)
    assert "elon musk" in result


def test_normalise_alias_word_boundary_safe():
    """'Fed' should not match inside 'fedora'."""
    aliases = {"fed": "federal reserve"}
    result = normalise_title("Fedora Linux is old", aliases)
    assert "fedora" in result
    assert "federal reserve" not in result
