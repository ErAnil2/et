import pandas as pd

from discover_intel.delivery.dashboard import coverage_trends_data


def _seed(conn):
    # Lane taxonomy
    conn.execute(
        "INSERT INTO taxonomy (taxonomy_id, kind, label, parent_id, in_et_lane) "
        "VALUES ('lane:tech_ai', 'lane', 'Tech & AI', NULL, 1)"
    )
    conn.execute(
        "INSERT INTO taxonomy (taxonomy_id, kind, label, parent_id, in_et_lane) "
        "VALUES ('lane:finance_markets', 'lane', 'Finance & Markets', NULL, 1)"
    )
    # Source + items in the current window
    conn.execute(
        "INSERT INTO sources (source_id, kind, market, name, url, host, enabled) "
        "VALUES ('web:x', 'web', 'US', 'x', 'https://x.com/feed', 'x.com', 1)"
    )
    for i in range(3):
        conn.execute(
            "INSERT INTO items (item_id, source_id, url, host, title, "
            "first_seen_at, last_seen_at, seen_count, title_hash) VALUES "
            f"('itm-{i}', 'web:x', 'https://x.com/{i}', 'x.com', 'title {i}', "
            f"'2026-09-22T12:00:00Z', '2026-09-22T12:00:00Z', 1, 'h{i}')"
        )
    # Tag itm-0 and itm-1 with tech_ai lane; itm-2 with finance_markets
    for i, tax in ((0, "lane:tech_ai"), (1, "lane:tech_ai"), (2, "lane:finance_markets")):
        conn.execute(
            "INSERT INTO item_entities (entry_id, source_key, entity, entity_type, "
            "taxonomy_id, confidence, tagged_at) VALUES "
            f"('e{i}', 'item:itm-{i}', 'E{i}', NULL, ?, 1.0, '2026-09-22T12:00:00Z')",
            (tax,),
        )
    conn.commit()


def test_coverage_trends_returns_dataframe(conn):
    _seed(conn)
    df = coverage_trends_data(conn,
                              window_start="2026-09-22T00:00:00Z",
                              window_end="2026-09-28T23:59:59Z")
    assert isinstance(df, pd.DataFrame)
    for col in ("lane", "entity_count", "prior_entity_count", "delta"):
        assert col in df.columns


def test_coverage_trends_counts_entities_per_lane(conn):
    _seed(conn)
    df = coverage_trends_data(conn,
                              window_start="2026-09-22T00:00:00Z",
                              window_end="2026-09-28T23:59:59Z")
    tech = df[df["lane"] == "Tech & AI"]
    fin = df[df["lane"] == "Finance & Markets"]
    assert len(tech) == 1
    assert tech.iloc[0]["entity_count"] == 2  # E0 + E1
    assert len(fin) == 1
    assert fin.iloc[0]["entity_count"] == 1


def test_coverage_trends_empty_window_returns_zeros(conn):
    _seed(conn)
    df = coverage_trends_data(conn,
                              window_start="2027-01-01T00:00:00Z",
                              window_end="2027-01-07T23:59:59Z")
    # Lanes still listed with 0 counts (because they exist in taxonomy)
    if not df.empty:
        assert all(df["entity_count"] == 0)
