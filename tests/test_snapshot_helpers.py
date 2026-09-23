import pytest

from discover_intel.ingest.import_snapshot import parse_hm, parse_kmb


@pytest.mark.parametrize("s,expected", [
    ("547.79K", 547790.0),
    ("1.2M",    1_200_000.0),
    ("2.5B",    2_500_000_000.0),
    ("300",     300.0),
    ("300.0",   300.0),
    ("",        None),
    (None,      None),
])
def test_parse_kmb(s, expected):
    assert parse_kmb(s) == expected


@pytest.mark.parametrize("s,minutes", [
    ("2h 0m", 120.0),
    ("1h 55m", 115.0),
    ("0h 45m", 45.0),
    ("55m", 55.0),
    ("", None),
    (None, None),
])
def test_parse_hm(s, minutes):
    assert parse_hm(s) == minutes
