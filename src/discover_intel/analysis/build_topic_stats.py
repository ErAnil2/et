"""S3-A hourly topic aggregates -> topic_stats."""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3

log = logging.getLogger(__name__)


def _iso_hours_ago(now_iso: str, hours: int) -> str:
    now = dt.datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    return (now - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_stats(conn: sqlite3.Connection, market: str, window_hours: int,
                  now: str | None = None) -> list[dict]:
    """Return per (hour_bucket, market, entity) aggregates over trailing window."""
    if now is None:
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    window_start = _iso_hours_ago(now, window_hours)
    twenty_four_ago = _iso_hours_ago(now, 24)
    seventy_two_ago = _iso_hours_ago(now, 72)

    combos = conn.execute(
        """
        SELECT DISTINCT
          substr(i.first_seen_at, 1, 13) || ':00:00Z' AS hour_utc,
          e.entity AS entity
        FROM items i
        JOIN item_entities e ON e.source_key = 'item:' || i.item_id
        WHERE i.first_seen_at >= ?
        ORDER BY hour_utc DESC
        """,
        (window_start,),
    ).fetchall()

    out: list[dict] = []
    for hour_utc, entity in combos:
        (new_items,) = conn.execute(
            """
            SELECT COUNT(DISTINCT i.item_id)
            FROM items i
            JOIN item_entities e ON e.source_key = 'item:' || i.item_id
            WHERE e.entity = ?
              AND substr(i.first_seen_at, 1, 13) || ':00:00Z' = ?
            """,
            (entity, hour_utc),
        ).fetchone()

        (competitor_hosts,) = conn.execute(
            """
            SELECT COUNT(DISTINCT i.host)
            FROM items i
            JOIN item_entities e ON e.source_key = 'item:' || i.item_id
            WHERE e.entity = ? AND i.first_seen_at >= ?
            """,
            (entity, twenty_four_ago),
        ).fetchone()

        (gnews_query_hits,) = conn.execute(
            """
            SELECT COUNT(DISTINCT i.item_id)
            FROM items i
            JOIN item_entities e ON e.source_key = 'item:' || i.item_id
            JOIN sources s ON s.source_id = i.source_id
            WHERE e.entity = ? AND i.first_seen_at >= ?
              AND s.kind IN ('gnews_query', 'gnews_section')
            """,
            (entity, twenty_four_ago),
        ).fetchone()

        row = conn.execute(
            """
            SELECT
              COUNT(DISTINCT o.obs_id) AS discover_obs,
              COALESCE(SUM(o.visibility), 0.0) AS discover_visibility,
              AVG(o.time_on_feed_min) AS avg_time_on_feed_min
            FROM discover_articles o
            JOIN item_outcomes io ON io.obs_id = o.obs_id
            JOIN items i ON i.item_id = io.item_id
            JOIN item_entities e ON e.source_key = 'item:' || i.item_id
            WHERE e.entity = ? AND o.observed_at >= ?
            """,
            (entity, twenty_four_ago),
        ).fetchone()
        discover_obs = row[0] if row else 0
        discover_visibility = row[1] if row else 0.0
        avg_time_on_feed_min = row[2] if row else None

        winner = conn.execute(
            """
            SELECT o.format, SUM(o.visibility) AS vis
            FROM discover_articles o
            JOIN item_outcomes io ON io.obs_id = o.obs_id
            JOIN items i ON i.item_id = io.item_id
            JOIN item_entities e ON e.source_key = 'item:' || i.item_id
            WHERE e.entity = ? AND o.observed_at >= ? AND o.format IS NOT NULL
            GROUP BY o.format
            ORDER BY vis DESC
            LIMIT 1
            """,
            (entity, seventy_two_ago),
        ).fetchone()
        winning_format = winner[0] if winner else None

        out.append({
            "hour_utc": hour_utc,
            "market": market,
            "entity": entity,
            "new_items": int(new_items or 0),
            "competitor_hosts": int(competitor_hosts or 0),
            "gnews_query_hits": int(gnews_query_hits or 0),
            "discover_obs": int(discover_obs or 0),
            "discover_visibility": float(discover_visibility or 0.0),
            "avg_time_on_feed_min": (
                float(avg_time_on_feed_min) if avg_time_on_feed_min is not None else None
            ),
            "winning_format": winning_format,
        })
    return out
