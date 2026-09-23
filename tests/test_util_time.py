import datetime as dt

import pytest

from discover_intel.util import time as timeutil


def test_utc_now_is_utc_aware():
    now = timeutil.utc_now()
    assert now.tzinfo is dt.timezone.utc


def test_parse_discovertrends_filename_ok():
    p = timeutil.parse_discovertrends_filename("DiscoverTrends_2026-09-23_1547.csv")
    assert p == dt.datetime(2026, 9, 23, 15, 47, 0, tzinfo=dt.timezone.utc)


def test_parse_discovertrends_filename_with_path():
    p = timeutil.parse_discovertrends_filename(
        "/tmp/DiscoverTrends_2026-09-23_1547.csv"
    )
    assert p.hour == 15 and p.minute == 47


def test_parse_discovertrends_filename_bad():
    with pytest.raises(ValueError):
        timeutil.parse_discovertrends_filename("something_else.csv")


def test_iso_utc_roundtrip():
    d = dt.datetime(2026, 9, 23, 15, 47, 0, tzinfo=dt.timezone.utc)
    assert timeutil.iso_utc(d) == "2026-09-23T15:47:00Z"
