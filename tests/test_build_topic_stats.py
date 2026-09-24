import sqlite3

from discover_intel.analysis.build_topic_stats import compute_stats
from discover_intel.db import upsert


def _seed(conn: sqlite3.Connection) -> None:
    upsert(conn, "sources", {
        "source_id": "web:nj.com", "kind": "web", "market": "US",
        "name": "nj.com", "url": "https://nj.com/feed", "host": "www.nj.com",
        "tier": None, "category": None, "enabled": 1, "notes": None,
    }, key="source_id")
    upsert(conn, "sources", {
        "source_id": "gnews:query:fed", "kind": "gnews_query", "market": "US",
        "name": "fed", "url": "https://news.google.com/rss/search?q=fed",
        "host": None, "tier": None, "category": None, "enabled": 1, "notes": None,
    }, key="source_id")

    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-1', 'web:nj.com', 'https://nj.com/a', 'www.nj.com', 'Fed cuts rates', "
        "'2026-09-24T12:00:00Z', '2026-09-24T12:00:00Z', 1, 'h1'),"
        "('itm-2', 'gnews:query:fed', 'https://news.google.com/x', 'news.google.com', "
        "'Fed hints', '2026-09-24T13:00:00Z', '2026-09-24T13:00:00Z', 1, 'h2')"
    )
    conn.execute(
        "INSERT INTO item_entities (entry_id, source_key, entity, entity_type, "
        "taxonomy_id, confidence, tagged_at) VALUES "
        "('e1', 'item:itm-1', 'Federal Reserve', 'ORG', NULL, 1.0, '2026-09-24T12:00:00Z'),"
        "('e2', 'item:itm-2', 'Federal Reserve', 'ORG', NULL, 1.0, '2026-09-24T13:00:00Z')"
    )
    conn.execute(
        "INSERT INTO discover_articles (obs_id, tool, market, observed_at, "
        "source_file, imported_at, title, url, host, visibility, rank, "
        "time_on_feed_min, format, author, raw_json) VALUES "
        "('obs-1', 'discovertrends', 'US', '2026-09-24T14:00:00Z', 'x.csv', "
        "'2026-09-24T14:05:00Z', 'Federal Reserve rate cut', 'https://nj.com/a', "
        "'www.nj.com', 100.0, 1, NULL, 'news', NULL, '{}')"
    )
    conn.execute(
        "INSERT INTO item_outcomes (item_id, obs_id, match_type, match_score, matched_at) "
        "VALUES ('itm-1', 'obs-1', 'url', 1.0, '2026-09-24T14:10:00Z')"
    )
    conn.commit()


def test_compute_stats_produces_rows_for_entity(conn):
    _seed(conn)
    rows = compute_stats(conn, market="US", window_hours=72,
                         now="2026-09-24T15:00:00Z")
    entity_rows = [r for r in rows if r["entity"] == "Federal Reserve"]
    assert len(entity_rows) >= 1
    total_new = sum(r["new_items"] for r in entity_rows)
    assert total_new == 2


def test_compute_stats_captures_discover_visibility(conn):
    _seed(conn)
    rows = compute_stats(conn, market="US", window_hours=72,
                         now="2026-09-24T15:00:00Z")
    entity_rows = [r for r in rows if r["entity"] == "Federal Reserve"]
    # discover_visibility is a rolling 24h snapshot — same value on every bucket.
    assert all(r["discover_visibility"] == 100.0 for r in entity_rows)


def test_compute_stats_gnews_query_hits(conn):
    _seed(conn)
    rows = compute_stats(conn, market="US", window_hours=72,
                         now="2026-09-24T15:00:00Z")
    entity_rows = [r for r in rows if r["entity"] == "Federal Reserve"]
    total_gq = sum(r["gnews_query_hits"] for r in entity_rows)
    assert total_gq >= 1


def test_compute_stats_empty_warehouse_returns_empty(conn):
    rows = compute_stats(conn, market="US", window_hours=72,
                         now="2026-09-24T15:00:00Z")
    assert rows == []
