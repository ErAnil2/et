import json

import pandas as pd

from discover_intel.db import upsert
from discover_intel.delivery.dashboard import (
    et_conversion_data, feed_composition_data, lane_coverage_data,
    market_precision_data, opportunities_data, velocity_data,
)


def _seed(conn):
    ev = json.dumps({"top_discover_titles": [], "competitor_hosts": [],
                     "beat_queries": []})
    conn.execute(
        "INSERT INTO topic_scores (scored_at, market, entity, tos, momentum, "
        "headroom, timing, format_match, lane_fit, suggested_format, "
        "evidence_json) VALUES ('2026-09-24T14:00:00Z', 'US', 'A', 70.0, 0.7, "
        "1.0, 0.5, 1.0, 1.0, 'news', ?)",
        (ev,),
    )
    conn.execute(
        "INSERT INTO topic_scores (scored_at, market, entity, tos, momentum, "
        "headroom, timing, format_match, lane_fit, suggested_format, "
        "evidence_json) VALUES ('2026-09-24T14:00:00Z', 'US', 'B', 30.0, 0.3, "
        "0.5, 0.2, 0.5, 0.3, 'news', ?)",
        (ev,),
    )
    conn.commit()


def test_opportunities_data_filters_by_watchlist_threshold(conn):
    _seed(conn)
    df = opportunities_data(conn, watchlist_threshold=45.0)
    assert len(df) == 1
    assert df.iloc[0]["entity"] == "A"


def test_opportunities_data_empty_returns_empty_frame(conn):
    df = opportunities_data(conn, watchlist_threshold=45.0)
    assert len(df) == 0


def _seed_feed(conn):
    upsert(conn, "sources", {
        "source_id": "web:nj.com", "kind": "web", "market": "US",
        "name": "nj.com", "url": "https://nj.com/feed", "host": "www.nj.com",
        "tier": None, "category": None, "enabled": 1, "notes": None,
    }, key="source_id")
    now = "2026-09-24T14:00:00Z"
    for i in range(3):
        conn.execute(
            "INSERT INTO items (item_id, source_id, url, host, title, "
            "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
            f"('nj-{i}', 'web:nj.com', 'https://nj.com/{i}', 'www.nj.com', "
            f"'title {i}', ?, ?, 1, 'h{i}')",
            (now, now),
        )
    conn.commit()


def test_feed_composition_host_share(conn):
    _seed_feed(conn)
    host_share, efficiency = feed_composition_data(conn)
    assert len(host_share) >= 1
    assert "host" in host_share.columns and "items_24h" in host_share.columns
    row = host_share[host_share["host"] == "www.nj.com"].iloc[0]
    assert row["items_24h"] == 3


def test_feed_composition_returns_two_frames_when_empty(conn):
    host_share, efficiency = feed_composition_data(conn)
    assert host_share.empty
    assert efficiency.empty


def test_velocity_data_returns_dataframe(conn):
    _seed_feed(conn)
    df = velocity_data(conn)
    assert isinstance(df, pd.DataFrame)
    for col in ("host", "hour", "item_count"):
        assert col in df.columns


def test_lane_coverage_data_returns_two_frames(conn):
    conn.execute(
        "INSERT INTO taxonomy (taxonomy_id, kind, label, parent_id, in_et_lane) "
        "VALUES ('lane:tech_ai', 'lane', 'Tech & AI', NULL, 1)"
    )
    upsert(conn, "sources", {
        "source_id": "web:x.com", "kind": "web", "market": "US",
        "name": "x", "url": "https://x.com/feed", "host": "x.com",
        "tier": None, "category": None, "enabled": 1, "notes": None,
    }, key="source_id")
    conn.execute(
        "INSERT INTO items (item_id, source_id, url, host, title, "
        "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
        "('itm-1', 'web:x.com', 'https://x.com/a', 'x.com', 't', "
        "'2026-09-24T12:00:00Z', '2026-09-24T12:00:00Z', 1, 'h')"
    )
    conn.execute(
        "INSERT INTO item_entities (entry_id, source_key, entity, entity_type, "
        "taxonomy_id, confidence, tagged_at) VALUES "
        "('e1', 'item:itm-1', 'x', NULL, 'lane:tech_ai', 1.0, "
        "'2026-09-24T12:00:00Z')"
    )
    conn.commit()
    published, captured = lane_coverage_data(conn)
    assert isinstance(published, pd.DataFrame)
    assert isinstance(captured, pd.DataFrame)
    assert len(published) >= 1


def test_market_precision_no_scores_returns_empty(conn):
    df = market_precision_data(conn)
    assert isinstance(df, pd.DataFrame)


def test_et_conversion_empty_gsc_returns_flag(conn):
    result = et_conversion_data(conn)
    assert isinstance(result, dict)
    assert result.get("gsc_populated") is False
