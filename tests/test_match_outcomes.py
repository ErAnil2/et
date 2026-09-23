import sqlite3

from discover_intel.analysis.match_outcomes import (
    _normalise_title, _stripped_url_equals, match_canonical, match_url,
)
from discover_intel.db import upsert


def _seed(conn: sqlite3.Connection, item_url: str, canonical: str | None,
          obs_url: str, host: str = "example.com") -> None:
    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed",
        "host": host, "tier": None, "category": None, "enabled": 1, "notes": None,
    }, key="source_id")
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, canonical_url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-1', 'web:example.com', ?, ?, ?, 'title one', "
        "'2026-09-23T12:00:00Z', '2026-09-23T12:00:00Z', 1, 'hash1')",
        (item_url, canonical, host),
    )
    conn.execute(
        "INSERT INTO discover_articles (obs_id, tool, market, observed_at, "
        "source_file, imported_at, title, url, host, visibility, rank, "
        "time_on_feed_min, format, author, raw_json) VALUES "
        "('obs-1', 'discovertrends', 'US', '2026-09-23T13:00:00Z', "
        "'x.csv', '2026-09-23T13:05:00Z', 'title one', ?, ?, 100, 1, "
        "NULL, NULL, NULL, '{}')",
        (obs_url, host),
    )
    conn.commit()


def test_normalise_title_lowercases_and_collapses():
    assert _normalise_title("  Foo   BAR baz  ") == "foo bar baz"


def test_stripped_url_equals_handles_utm():
    assert _stripped_url_equals(
        "https://x.com/a?utm_source=news",
        "https://x.com/a",
    )


def test_stripped_url_equals_false_for_different_paths():
    assert not _stripped_url_equals(
        "https://x.com/a", "https://x.com/b",
    )


def test_match_url_finds_exact_pair(conn):
    _seed(conn, "https://example.com/story", None, "https://example.com/story?utm_source=x")
    pairs = match_url(conn, since_hours=72)
    assert pairs == [("itm-1", "obs-1")]


def test_match_canonical_finds_via_canonical_url(conn):
    _seed(conn,
          item_url="https://news.google.com/rss/articles/CBMi...",
          canonical="https://example.com/story",
          obs_url="https://example.com/story")
    pairs = match_canonical(conn, since_hours=72)
    assert pairs == [("itm-1", "obs-1")]
