import sqlite3

import httpx

from discover_intel.analysis.resolve_urls import orchestrate, resolve_one
from discover_intel.db import upsert
from discover_intel.util.http import TokenBucket


def _seed_source(conn: sqlite3.Connection) -> None:
    upsert(conn, "sources", {
        "source_id": "gnews:query:test", "kind": "gnews_query", "market": "US",
        "name": "test", "url": "https://news.google.com/rss/search?q=test",
        "host": None, "tier": None, "category": None, "enabled": 1, "notes": None,
    }, key="source_id")


def _seed_item(conn: sqlite3.Connection, item_id: str, url: str) -> None:
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "(?, 'gnews:query:test', ?, ?, ?, '2026-09-23T12:00:00Z', "
        "'2026-09-23T12:00:00Z', 1, ?)",
        (item_id, url, "news.google.com", "sample title", "hash"),
    )
    conn.commit()


def test_resolve_one_uses_decoder():
    client = httpx.Client()
    url = "https://news.google.com/rss/articles/CBMiXWh0dHBzOi8vd3d3LmV4YW1wbGUuY29tL25ld3MvZmVkLWN1dHM_dXRtX3NvdXJjZT14"
    result = resolve_one(client, url, bucket=None)
    assert result is not None
    assert "example.com" in result


def test_resolve_one_falls_back_to_head(httpx_mock):
    """Non-gnews URL or undecodable blob → HEAD fallback."""
    httpx_mock.add_response(
        method="HEAD",
        url="https://news.google.com/rss/articles/CBMoZGVjb2Rpbmctc2hvdWxkLWZhaWwtdGhpcy1pc250LWEtVVJM",
        status_code=302,
        headers={"Location": "https://publisher.example.com/story"},
    )
    httpx_mock.add_response(
        method="HEAD",
        url="https://publisher.example.com/story",
        status_code=200,
    )
    client = httpx.Client(follow_redirects=True)
    url = "https://news.google.com/rss/articles/CBMoZGVjb2Rpbmctc2hvdWxkLWZhaWwtdGhpcy1pc250LWEtVVJM"
    bucket = TokenBucket(rate_per_sec=100, capacity=100)
    result = resolve_one(client, url, bucket=bucket)
    assert result is not None
    assert "publisher.example.com" in result


def test_resolve_one_head_returns_none_on_4xx(httpx_mock):
    httpx_mock.add_response(
        method="HEAD",
        url="https://news.google.com/rss/articles/CBMoBad4xx",
        status_code=404,
    )
    client = httpx.Client(follow_redirects=True)
    result = resolve_one(client, "https://news.google.com/rss/articles/CBMoBad4xx",
                         bucket=TokenBucket(100, 100))
    assert result is None


def test_orchestrate_fills_canonical_url(conn):
    _seed_source(conn)
    _seed_item(
        conn, "item-1",
        "https://news.google.com/rss/articles/CBMiRGh0dHBzOi8vd3d3Lm5qLmNvbS9uZXdzLzIwMjYvMDkvc29jaWFsLXNlY3VyaXR5LWNvbGEtMjAyN9IBAA==",
    )
    stats = orchestrate(conn, limit=10)
    assert stats["decoded"] == 1
    (canonical,) = conn.execute(
        "SELECT canonical_url FROM items WHERE item_id='item-1'"
    ).fetchone()
    assert canonical is not None
    assert "nj.com" in canonical


def test_orchestrate_only_processes_null_canonical(conn):
    """Idempotency: if canonical_url already set, orchestrate skips it."""
    _seed_source(conn)
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, canonical_url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('done-1', 'gnews:query:test', 'https://news.google.com/rss/articles/CBMi...', "
        "'https://already-set.com/', 'news.google.com', 't', "
        "'2026-09-23T12:00:00Z', '2026-09-23T12:00:00Z', 1, 'h')"
    )
    conn.commit()
    stats = orchestrate(conn, limit=10)
    assert stats["candidates"] == 0
