from pathlib import Path

from discover_intel.analysis.tag_entities import orchestrate
from discover_intel.db import upsert

CONFIG_DIR = Path(__file__).parent.parent / "config"


def _seed_items(conn) -> None:
    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed",
        "host": "example.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    for i, title in enumerate([
        "in 1957 Elvis Presley bought Graceland",
        "Fed cuts rates by 25 basis points",
        "Robin Williams mansion in Napa sells for 18 million",
    ], start=1):
        conn.execute(
            "INSERT INTO items (item_id, source_id, url, host, title, "
            "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
            "(?, 'web:example.com', ?, 'example.com', ?, "
            "'2026-09-23T12:00:00Z', '2026-09-23T12:00:00Z', 1, ?)",
            (f"itm-{i}", f"https://example.com/a{i}", title, f"h{i}"),
        )
    conn.commit()


def test_orchestrate_tags_items(spacy_nlp, conn):
    _seed_items(conn)
    stats = orchestrate(conn, source="items", limit=10,
                       config_dir=CONFIG_DIR, nlp=spacy_nlp)
    assert stats["items_tagged"] == 3
    (n_entries,) = conn.execute("SELECT count(*) FROM item_entities").fetchone()
    assert n_entries > 0
    for i in range(1, 4):
        (n,) = conn.execute(
            "SELECT count(*) FROM item_entities WHERE source_key = ?",
            (f"item:itm-{i}",),
        ).fetchone()
        assert n > 0, f"item {i} got no tags"


def test_orchestrate_is_idempotent(spacy_nlp, conn):
    _seed_items(conn)
    orchestrate(conn, source="items", limit=10, config_dir=CONFIG_DIR, nlp=spacy_nlp)
    (n1,) = conn.execute("SELECT count(*) FROM item_entities").fetchone()
    orchestrate(conn, source="items", limit=10, config_dir=CONFIG_DIR, nlp=spacy_nlp)
    (n2,) = conn.execute("SELECT count(*) FROM item_entities").fetchone()
    assert n2 == n1


def test_orchestrate_trivia_title_gets_trivia_format(spacy_nlp, conn):
    _seed_items(conn)
    orchestrate(conn, source="items", limit=10, config_dir=CONFIG_DIR, nlp=spacy_nlp)
    (fmt,) = conn.execute(
        "SELECT taxonomy_id FROM item_entities "
        "WHERE source_key = 'item:itm-1' AND taxonomy_id LIKE 'format:%'"
    ).fetchone()
    assert fmt == "format:trivia"
