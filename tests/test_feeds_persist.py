import sqlite3

from discover_intel.config import Source
from discover_intel.db import upsert
from discover_intel.ingest.feeds import (
    ParsedItem, item_id_for, persist_items, persist_poll,
)


def _seed_source(conn: sqlite3.Connection, source_id: str = "web:example.com") -> Source:
    src = Source(
        source_id=source_id, kind="web", market="US", name="example.com",
        url="https://example.com/feed", host="example.com", tier=None,
        category=None, enabled=1, notes=None,
    )
    upsert(conn, "sources", {
        "source_id": src.source_id, "kind": src.kind, "market": src.market,
        "name": src.name, "url": src.url, "host": src.host, "tier": src.tier,
        "category": src.category, "enabled": src.enabled, "notes": src.notes,
    }, key="source_id")
    return src


def _mk_item(url: str, title: str = "T") -> ParsedItem:
    return ParsedItem(url=url, title=title, host="example.com",
                      description=None, author=None, published_at=None)


def test_item_id_is_deterministic():
    a = item_id_for("web:x.com", "https://x.com/a")
    b = item_id_for("web:x.com", "https://x.com/a")
    assert a == b
    assert a != item_id_for("web:x.com", "https://x.com/b")


def test_persist_items_inserts_new(conn):
    src = _seed_source(conn)
    items = [_mk_item("https://example.com/a"), _mk_item("https://example.com/b")]
    result = persist_items(conn, src, items)
    assert result == {"seen": 2, "new": 2}
    (n,) = conn.execute("SELECT count(*) FROM items").fetchone()
    assert n == 2


def test_persist_items_bumps_seen_count_on_duplicate(conn):
    src = _seed_source(conn)
    it = _mk_item("https://example.com/a")
    persist_items(conn, src, [it])
    r2 = persist_items(conn, src, [it])
    assert r2 == {"seen": 1, "new": 0}
    (fs, ls, sc) = conn.execute(
        "SELECT first_seen_at, last_seen_at, seen_count FROM items"
    ).fetchone()
    assert sc == 2
    assert ls >= fs


def test_persist_poll_writes_row(conn):
    src = _seed_source(conn)
    persist_poll(conn, src, http_status=200, items_seen=5, items_new=3,
                 duration_ms=123, error=None)
    (n,) = conn.execute("SELECT count(*) FROM feed_polls").fetchone()
    assert n == 1
    (status, seen, new, dur) = conn.execute(
        "SELECT http_status, items_seen, items_new, duration_ms FROM feed_polls"
    ).fetchone()
    assert (status, seen, new, dur) == (200, 5, 3, 123)


def test_persist_poll_with_error(conn):
    src = _seed_source(conn)
    persist_poll(conn, src, http_status=None, items_seen=0, items_new=0,
                 duration_ms=42, error="ConnectionError: bang")
    (err,) = conn.execute("SELECT error FROM feed_polls").fetchone()
    assert "bang" in err
