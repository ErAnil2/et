"""UTC helpers and filename → timestamp parsers."""
from __future__ import annotations

import datetime as dt
import os
import re

_DT_FN_RE = re.compile(r"DiscoverTrends_(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})\.csv$")


def utc_now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def parse_discovertrends_filename(path_or_name: str) -> dt.datetime:
    """DiscoverTrends_2026-09-23_1547.csv  →  2026-09-23T15:47:00Z"""
    name = os.path.basename(path_or_name)
    m = _DT_FN_RE.search(name)
    if not m:
        raise ValueError(
            f"Filename does not match DiscoverTrends_YYYY-MM-DD_HHMM.csv: {name!r}"
        )
    date_s, hh, mm = m.group(1), m.group(2), m.group(3)
    return dt.datetime.strptime(
        f"{date_s}T{hh}:{mm}:00+0000", "%Y-%m-%dT%H:%M:%S%z"
    )


def iso_utc(t: dt.datetime) -> str:
    """Datetime → 2026-09-23T15:47:00Z (Z suffix, second precision)."""
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
