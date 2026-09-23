"""S2-B outcome matcher: link discover_articles to items via a 4-stage cascade."""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3

from discover_intel.util.url import strip_tracking

log = logging.getLogger(__name__)


def _normalise_title(s: str | None) -> str:
    if not s:
        return ""
    return " ".join(s.lower().split())


def _stripped_url_equals(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return strip_tracking(a) == strip_tracking(b)


def _since_iso(since_hours: int) -> str:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=since_hours)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def match_url(conn: sqlite3.Connection, since_hours: int) -> list[tuple[str, str]]:
    """Stage 1: exact URL match after tracking-strip."""
    cutoff = _since_iso(since_hours)
    rows = conn.execute(
        "SELECT i.item_id, i.url, o.obs_id, o.url "
        "FROM items i JOIN discover_articles o "
        "ON i.host = o.host "
        "WHERE o.observed_at >= ? AND o.url IS NOT NULL",
        (cutoff,),
    ).fetchall()
    pairs: list[tuple[str, str]] = []
    for item_id, item_url, obs_id, obs_url in rows:
        if _stripped_url_equals(item_url, obs_url):
            pairs.append((item_id, obs_id))
    return pairs


def match_canonical(conn: sqlite3.Connection, since_hours: int) -> list[tuple[str, str]]:
    """Stage 2: exact canonical-URL match after tracking-strip."""
    cutoff = _since_iso(since_hours)
    rows = conn.execute(
        "SELECT i.item_id, i.canonical_url, o.obs_id, o.url "
        "FROM items i JOIN discover_articles o "
        "ON i.host = o.host "
        "WHERE o.observed_at >= ? AND o.url IS NOT NULL "
        "AND i.canonical_url IS NOT NULL",
        (cutoff,),
    ).fetchall()
    pairs: list[tuple[str, str]] = []
    for item_id, canonical, obs_id, obs_url in rows:
        if _stripped_url_equals(canonical, obs_url):
            pairs.append((item_id, obs_id))
    return pairs
