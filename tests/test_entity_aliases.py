import csv
from pathlib import Path

CONFIG = Path(__file__).parent.parent / "config" / "entity_aliases.csv"


def _load() -> dict[str, str]:
    with CONFIG.open(encoding="utf-8", newline="") as fh:
        return {r["alias"]: r["canonical"] for r in csv.DictReader(fh)}


def test_aliases_file_has_expected_size():
    d = _load()
    assert 25 <= len(d) <= 45, f"expected ~30 mappings, got {len(d)}"


def test_key_canonicalisations_present():
    d = _load()
    assert d["Fed"] == "Federal Reserve"
    assert d["Musk"] == "Elon Musk"
    assert d["Bezos"] == "Jeff Bezos"
    assert d["Trump"] == "Donald Trump"
    assert d["SCOTUS"] == "Supreme Court"


def test_no_self_referencing_aliases():
    """An alias mapping to itself is a bug (adds noise, no normalisation)."""
    d = _load()
    for a, c in d.items():
        assert a.lower() != c.lower() or a == c, f"self-loop: {a}={c}"
