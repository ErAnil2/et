import json
import sqlite3
from pathlib import Path

from discover_intel.db import upsert
from discover_intel.scoring.tos import (
    load_scoring_config, rank_percentile, score_entity,
)

CFG_PATH = Path(__file__).parent.parent / "config" / "scoring.yaml"


def test_rank_percentile_basic():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert 0.4 <= rank_percentile(values, 3.0) <= 0.6


def test_rank_percentile_target_below_min():
    assert rank_percentile([2.0, 3.0], 1.0) == 0.0


def test_rank_percentile_target_at_max():
    assert rank_percentile([2.0, 3.0, 4.0], 4.0) >= 0.9


def test_rank_percentile_empty_returns_zero():
    assert rank_percentile([], 3.0) == 0.0


def _seed_entity(conn: sqlite3.Connection) -> None:
    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed", "host": "example.com",
        "tier": None, "category": None, "enabled": 1, "notes": None,
    }, key="source_id")
    conn.execute(
        "INSERT INTO taxonomy (taxonomy_id, kind, label, parent_id, in_et_lane) "
        "VALUES ('lane:finance', 'lane', 'Finance', NULL, 1)"
    )
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-1', 'web:example.com', 'https://example.com/a', 'example.com', "
        "'Fed rate cut', '2026-09-24T12:00:00Z', '2026-09-24T12:00:00Z', 1, 'h1')"
    )
    conn.execute(
        "INSERT INTO item_entities (entry_id, source_key, entity, entity_type, "
        "taxonomy_id, confidence, tagged_at) VALUES "
        "('e1', 'item:itm-1', 'Federal Reserve', 'ORG', NULL, 1.0, '2026-09-24T12:00:00Z'),"
        "('e2', 'item:itm-1', 'Federal Reserve', NULL, 'lane:finance', 1.0, "
        "'2026-09-24T12:00:00Z')"
    )
    conn.execute(
        "INSERT INTO discover_articles (obs_id, tool, market, observed_at, "
        "source_file, imported_at, title, url, host, visibility, rank, "
        "time_on_feed_min, format, author, raw_json) VALUES "
        "('obs-1', 'discovertrends', 'US', '2026-09-24T13:00:00Z', 'x.csv', "
        "'2026-09-24T13:05:00Z', 'Fed cuts rates by 25', 'https://example.com/a', "
        "'example.com', 100.0, 1, 30.0, 'news', NULL, '{}')"
    )
    conn.execute(
        "INSERT INTO item_outcomes (item_id, obs_id, match_type, match_score, matched_at) "
        "VALUES ('itm-1', 'obs-1', 'url', 1.0, '2026-09-24T13:10:00Z')"
    )
    conn.execute(
        "INSERT INTO topic_stats (hour_utc, market, entity, new_items, "
        "competitor_hosts, gnews_query_hits, discover_obs, discover_visibility, "
        "avg_time_on_feed_min, winning_format) VALUES "
        "('2026-09-24T12:00:00Z', 'US', 'Federal Reserve', 3, 4, 2, 1, 100.0, "
        "30.0, 'news')"
    )
    conn.commit()


def test_load_scoring_config_reads_yaml():
    cfg = load_scoring_config(CFG_PATH)
    assert "tos" in cfg and "drs" in cfg
    assert cfg["tos"]["weights"]["momentum"] == 0.30


def test_score_entity_returns_all_components(conn):
    _seed_entity(conn)
    cfg = load_scoring_config(CFG_PATH)
    result = score_entity(
        conn, market="US", entity="Federal Reserve",
        config=cfg, scored_at="2026-09-24T14:00:00Z",
        candidate_stats={"momentum": [3.0], "timing": [30.0]},
    )
    assert "tos" in result
    assert 0.0 <= result["tos"] <= 100.0
    assert 0.0 <= result["momentum"] <= 1.0
    assert 0.0 <= result["headroom"] <= 1.0
    assert result["format_match"] == 1.0
    assert result["lane_fit"] == 1.0
    ev = json.loads(result["evidence_json"])
    assert "top_discover_titles" in ev
    assert "competitor_hosts" in ev


def test_score_entity_suggested_format_news_default(conn):
    _seed_entity(conn)
    cfg = load_scoring_config(CFG_PATH)
    result = score_entity(
        conn, market="US", entity="Federal Reserve",
        config=cfg, scored_at="2026-09-24T14:00:00Z",
        candidate_stats={"momentum": [3.0], "timing": [30.0]},
    )
    assert result["suggested_format"] == "news"
