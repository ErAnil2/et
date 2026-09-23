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


def test_match_title_exact(conn):
    """Same host + title_hash match → stage 3."""
    from discover_intel.analysis.match_outcomes import match_title_exact

    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed",
        "host": "example.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    import hashlib
    title = "fed cuts rates by 25 bps"
    thash = hashlib.sha1(title.encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-2', 'web:example.com', 'https://a/1', 'example.com', ?, "
        "'2026-09-23T12:00:00Z', '2026-09-23T12:00:00Z', 1, ?)",
        (title, thash),
    )
    conn.execute(
        "INSERT INTO discover_articles (obs_id, tool, market, observed_at, "
        "source_file, imported_at, title, url, host, visibility, rank, "
        "time_on_feed_min, format, author, raw_json) VALUES "
        "('obs-2', 'discovertrends', 'US', '2026-09-23T13:00:00Z', "
        "'x.csv', '2026-09-23T13:05:00Z', 'Fed cuts rates by 25 bps', "
        "'https://a/2', 'example.com', 100, 1, NULL, NULL, NULL, '{}')"
    )
    conn.commit()
    pairs = match_title_exact(conn, since_hours=72)
    assert ("itm-2", "obs-2") in pairs


def test_match_title_fuzzy(conn):
    """Same host + fuzzy title (>= 0.85) + within ±48h → stage 4."""
    from discover_intel.analysis.match_outcomes import match_title_fuzzy

    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed",
        "host": "example.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-3', 'web:example.com', 'https://a/3', 'example.com', "
        "'Fed cuts interest rates by 25 basis points', "
        "'2026-09-23T12:00:00Z', '2026-09-23T12:00:00Z', 1, 'h3')"
    )
    conn.execute(
        "INSERT INTO discover_articles (obs_id, tool, market, observed_at, "
        "source_file, imported_at, title, url, host, visibility, rank, "
        "time_on_feed_min, format, author, raw_json) VALUES "
        "('obs-3', 'discovertrends', 'US', '2026-09-23T13:00:00Z', "
        "'x.csv', '2026-09-23T13:05:00Z', 'Fed cuts rates by 25 basis points', "
        "'https://different/url', 'example.com', 100, 1, "
        "NULL, NULL, NULL, '{}')"
    )
    conn.commit()
    pairs = match_title_fuzzy(conn, since_hours=72)
    assert any(p[0] == "itm-3" and p[1] == "obs-3" for p in pairs)


def test_match_title_fuzzy_rejects_outside_48h_window(conn):
    from discover_intel.analysis.match_outcomes import match_title_fuzzy

    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed",
        "host": "example.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-old', 'web:example.com', 'https://a/old', 'example.com', "
        "'Fed cuts rates', '2026-09-15T00:00:00Z', '2026-09-15T00:00:00Z', "
        "1, 'hold')"
    )
    conn.execute(
        "INSERT INTO discover_articles (obs_id, tool, market, observed_at, "
        "source_file, imported_at, title, url, host, visibility, rank, "
        "time_on_feed_min, format, author, raw_json) VALUES "
        "('obs-old', 'discovertrends', 'US', '2026-09-23T13:00:00Z', "
        "'x.csv', '2026-09-23T13:05:00Z', 'Fed cuts rates', "
        "'https://elsewhere', 'example.com', 100, 1, "
        "NULL, NULL, NULL, '{}')"
    )
    conn.commit()
    pairs = match_title_fuzzy(conn, since_hours=200)
    assert not any(p[0] == "itm-old" and p[1] == "obs-old" for p in pairs)


def test_orchestrate_writes_item_outcomes(conn):
    """End-to-end: cascade fires, INSERT OR IGNORE keeps best stage."""
    from discover_intel.analysis.match_outcomes import orchestrate

    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed",
        "host": "example.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")

    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-A', 'web:example.com', 'https://example.com/a', 'example.com', "
        "'story a', '2026-09-23T12:00:00Z', '2026-09-23T12:00:00Z', 1, 'ha')"
    )
    conn.execute(
        "INSERT INTO discover_articles (obs_id, tool, market, observed_at, "
        "source_file, imported_at, title, url, host, visibility, rank, "
        "time_on_feed_min, format, author, raw_json) VALUES "
        "('obs-A', 'discovertrends', 'US', '2026-09-23T13:00:00Z', "
        "'x.csv', '2026-09-23T13:05:00Z', 'story a', "
        "'https://example.com/a?utm_source=x', 'example.com', 100, 1, "
        "NULL, NULL, NULL, '{}')"
    )
    conn.commit()

    stats = orchestrate(conn, since_hours=72)
    (n,) = conn.execute("SELECT count(*) FROM item_outcomes").fetchone()
    assert n == 1
    (mt,) = conn.execute(
        "SELECT match_type FROM item_outcomes WHERE item_id='itm-A'"
    ).fetchone()
    assert mt == "url"
    assert stats["matched"] >= 1


def test_orchestrate_is_idempotent(conn):
    """Re-running orchestrate doesn't create duplicate item_outcomes."""
    from discover_intel.analysis.match_outcomes import orchestrate

    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed",
        "host": "example.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-B', 'web:example.com', 'https://example.com/b', 'example.com', "
        "'t', '2026-09-23T12:00:00Z', '2026-09-23T12:00:00Z', 1, 'hb')"
    )
    conn.execute(
        "INSERT INTO discover_articles (obs_id, tool, market, observed_at, "
        "source_file, imported_at, title, url, host, visibility, rank, "
        "time_on_feed_min, format, author, raw_json) VALUES "
        "('obs-B', 'discovertrends', 'US', '2026-09-23T13:00:00Z', "
        "'x.csv', '2026-09-23T13:05:00Z', 't', 'https://example.com/b', "
        "'example.com', 100, 1, NULL, NULL, NULL, '{}')"
    )
    conn.commit()

    orchestrate(conn, since_hours=72)
    orchestrate(conn, since_hours=72)
    (n,) = conn.execute("SELECT count(*) FROM item_outcomes").fetchone()
    assert n == 1
