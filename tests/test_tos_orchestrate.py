import subprocess
import sys
from pathlib import Path

from discover_intel.db import upsert
from discover_intel.scoring.tos import orchestrate, persist_scores


def test_persist_scores_inserts(conn):
    rows = [{
        "scored_at": "2026-09-24T14:00:00Z", "market": "US", "entity": "Fed",
        "tos": 72.0, "momentum": 0.8, "headroom": 1.0, "timing": 0.5,
        "format_match": 1.0, "lane_fit": 1.0,
        "suggested_format": "news", "evidence_json": '{"x":1}',
    }]
    persist_scores(conn, rows)
    (n,) = conn.execute("SELECT count(*) FROM topic_scores").fetchone()
    assert n == 1


def test_orchestrate_empty_returns_zero_rows(conn):
    stats = orchestrate(conn, market="US")
    assert stats["scored"] == 0


def test_orchestrate_scores_entities_in_topic_stats(conn):
    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed", "host": "example.com",
        "tier": None, "category": None, "enabled": 1, "notes": None,
    }, key="source_id")
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-1', 'web:example.com', 'https://example.com/a', 'example.com', "
        "'Fed cuts', '2026-09-24T12:00:00Z', '2026-09-24T12:00:00Z', 1, 'h1')"
    )
    conn.execute(
        "INSERT INTO item_entities (entry_id, source_key, entity, entity_type, "
        "taxonomy_id, confidence, tagged_at) VALUES "
        "('e1', 'item:itm-1', 'Fed', 'ORG', NULL, 1.0, '2026-09-24T12:00:00Z')"
    )
    conn.execute(
        "INSERT INTO topic_stats (hour_utc, market, entity, new_items, "
        "competitor_hosts, gnews_query_hits, discover_obs, discover_visibility, "
        "avg_time_on_feed_min, winning_format) VALUES "
        "('2026-09-24T12:00:00Z', 'US', 'Fed', 2, 3, 1, 0, 0.0, NULL, 'news')"
    )
    conn.commit()

    stats = orchestrate(conn, market="US")
    assert stats["scored"] == 1
    (n,) = conn.execute("SELECT count(*) FROM topic_scores").fetchone()
    assert n == 1


def test_cli_tos_dry_run(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "tos",
         "--db", str(db_path), "--dry-run"],
        capture_output=True, text=True, check=True,
    )
    assert "tos:" in r.stdout
