"""S3-B Topic Opportunity Score — reads topic_stats + lanes; writes topic_scores."""
from __future__ import annotations

import bisect
import datetime as dt
import json
import logging
import sqlite3
import time as _time
from pathlib import Path

import yaml

from discover_intel.scoring.tos_components import (
    format_match, headroom, lane_fit, momentum, timing,
)

log = logging.getLogger(__name__)


def load_scoring_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def rank_percentile(values: list[float], target: float) -> float:
    """Return the rank-percentile of target within values (0.0 to 1.0)."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = bisect.bisect_right(sorted_vals, target)
    return idx / len(sorted_vals)


def _latest_topic_stats_for_entity(conn: sqlite3.Connection, market: str,
                                    entity: str) -> dict | None:
    row = conn.execute(
        "SELECT hour_utc, new_items, competitor_hosts, gnews_query_hits, "
        "discover_obs, discover_visibility, avg_time_on_feed_min, winning_format "
        "FROM topic_stats "
        "WHERE market = ? AND entity = ? "
        "ORDER BY hour_utc DESC LIMIT 1",
        (market, entity),
    ).fetchone()
    if not row:
        return None
    return {
        "hour_utc": row[0], "new_items": row[1], "competitor_hosts": row[2],
        "gnews_query_hits": row[3], "discover_obs": row[4],
        "discover_visibility": row[5], "avg_time_on_feed_min": row[6],
        "winning_format": row[7],
    }


def _entity_lane_flags(conn: sqlite3.Connection, entity: str) -> list[int]:
    rows = conn.execute(
        "SELECT DISTINCT t.in_et_lane "
        "FROM item_entities e "
        "JOIN taxonomy t ON t.taxonomy_id = e.taxonomy_id "
        "WHERE e.entity = ? AND t.kind = 'lane'",
        (entity,),
    ).fetchall()
    return [r[0] for r in rows]


def _gather_evidence(conn: sqlite3.Connection, entity: str, stats: dict) -> str:
    """Build evidence_json: top-3 Discover titles + competitor hosts + beat queries."""
    top_titles = conn.execute(
        "SELECT DISTINCT o.title, o.host, o.visibility "
        "FROM discover_articles o "
        "JOIN item_outcomes io ON io.obs_id = o.obs_id "
        "JOIN items i ON i.item_id = io.item_id "
        "JOIN item_entities e ON e.source_key = 'item:' || i.item_id "
        "WHERE e.entity = ? "
        "ORDER BY o.visibility DESC LIMIT 3",
        (entity,),
    ).fetchall()
    hosts = conn.execute(
        "SELECT DISTINCT i.host FROM items i "
        "JOIN item_entities e ON e.source_key = 'item:' || i.item_id "
        "WHERE e.entity = ? LIMIT 20",
        (entity,),
    ).fetchall()
    queries = conn.execute(
        "SELECT DISTINCT s.name FROM sources s "
        "JOIN items i ON i.source_id = s.source_id "
        "JOIN item_entities e ON e.source_key = 'item:' || i.item_id "
        "WHERE e.entity = ? AND s.kind = 'gnews_query' LIMIT 5",
        (entity,),
    ).fetchall()
    ev = {
        "top_discover_titles": [
            {"title": t[0], "host": t[1], "visibility": t[2]} for t in top_titles
        ],
        "competitor_hosts": [h[0] for h in hosts],
        "beat_queries": [q[0] for q in queries],
        "stats_snapshot": dict(stats.items()),
    }
    return json.dumps(ev, ensure_ascii=False)


def _hours_since(hour_utc: str, now_iso: str) -> float:
    try:
        h = dt.datetime.fromisoformat(hour_utc.replace("Z", "+00:00"))
        n = dt.datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        return (n - h).total_seconds() / 3600.0
    except (ValueError, AttributeError):
        return 0.0


def score_entity(conn: sqlite3.Connection, market: str, entity: str,
                 config: dict, scored_at: str,
                 candidate_stats: dict[str, list[float]] | None = None) -> dict:
    """Score a single entity. Returns the row-shape dict for topic_scores."""
    tos_cfg = config["tos"]
    weights = tos_cfg["weights"]
    curve = tos_cfg["headroom_curve"]
    decay_hours = float(tos_cfg["timing"]["freshness_decay_hours"])
    stats = _latest_topic_stats_for_entity(conn, market, entity)
    if stats is None:
        stats = {"hour_utc": scored_at, "new_items": 0, "competitor_hosts": 0,
                 "gnews_query_hits": 0, "discover_obs": 0,
                 "discover_visibility": 0.0, "avg_time_on_feed_min": None,
                 "winning_format": None}

    raw_momentum = momentum(stats["new_items"], prior_48h_mean_per_6h=1.0)
    raw_headroom = headroom(stats["competitor_hosts"], curve)
    hours_since = _hours_since(stats["hour_utc"], scored_at)
    raw_timing = timing(stats["avg_time_on_feed_min"], hours_since, decay_hours)

    if candidate_stats is None:
        candidate_stats = {"momentum": [raw_momentum], "timing": [raw_timing]}
    n_momentum = rank_percentile(candidate_stats.get("momentum", []), raw_momentum)
    n_timing = rank_percentile(candidate_stats.get("timing", []), raw_timing)

    n_format = format_match(stats["winning_format"], tos_cfg["format_match"])
    n_lane = lane_fit(_entity_lane_flags(conn, entity), tos_cfg["lane_fit"])

    tos = 100.0 * (
        weights["momentum"] * n_momentum
        + weights["headroom"] * raw_headroom
        + weights["timing"] * n_timing
        + weights["format_match"] * n_format
        + weights["lane_fit"] * n_lane
    )

    wf = stats["winning_format"]
    if wf in tos_cfg["format_match"]["producible"]:
        suggested = wf
    else:
        suggested = "news"

    return {
        "scored_at": scored_at,
        "market": market,
        "entity": entity,
        "tos": tos,
        "momentum": n_momentum,
        "headroom": raw_headroom,
        "timing": n_timing,
        "format_match": n_format,
        "lane_fit": n_lane,
        "suggested_format": suggested,
        "evidence_json": _gather_evidence(conn, entity, stats),
    }


def persist_scores(conn: sqlite3.Connection, rows: list[dict]) -> None:
    for r in rows:
        conn.execute(
            "INSERT OR REPLACE INTO topic_scores "
            "(scored_at, market, entity, tos, momentum, headroom, timing, "
            "format_match, lane_fit, suggested_format, evidence_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (r["scored_at"], r["market"], r["entity"], r["tos"],
             r["momentum"], r["headroom"], r["timing"], r["format_match"],
             r["lane_fit"], r["suggested_format"], r["evidence_json"]),
        )
    conn.commit()


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def orchestrate(conn: sqlite3.Connection, market: str = "US",
                config_path: str | Path | None = None,
                dry_run: bool = False) -> dict:
    """Score every entity present in topic_stats for the market."""
    t0 = _time.monotonic()
    if config_path is None:
        config_path = Path("config/scoring.yaml")
    if not Path(config_path).exists():
        log.warning("tos: %s not found; using defaults", config_path)
        line = "tos: 0 entities scored, 0 publish (>=60), 0 watchlist (45-60), 0 below in 0.0s"
        print(line)
        return {"scored": 0, "publish": 0, "watchlist": 0, "below": 0}
    cfg = load_scoring_config(config_path)
    scored_at = _iso_now()

    entities = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT entity FROM topic_stats WHERE market = ?",
            (market,),
        ).fetchall()
    ]

    if not entities:
        elapsed = _time.monotonic() - t0
        line = (
            f"tos: 0 entities scored, 0 publish (>=60), 0 watchlist (45-60), "
            f"0 below in {elapsed:.1f}s"
        )
        print(line)
        return {"scored": 0, "publish": 0, "watchlist": 0, "below": 0}

    raw_momentum: list[float] = []
    raw_timing: list[float] = []
    decay_h = float(cfg["tos"]["timing"]["freshness_decay_hours"])
    for entity in entities:
        stats = _latest_topic_stats_for_entity(conn, market, entity)
        if not stats:
            continue
        raw_momentum.append(momentum(stats["new_items"], prior_48h_mean_per_6h=1.0))
        hours = _hours_since(stats["hour_utc"], scored_at)
        raw_timing.append(timing(stats["avg_time_on_feed_min"], hours, decay_h))
    candidate_stats = {"momentum": raw_momentum, "timing": raw_timing}

    rows: list[dict] = []
    for entity in entities:
        row = score_entity(conn, market=market, entity=entity, config=cfg,
                           scored_at=scored_at, candidate_stats=candidate_stats)
        rows.append(row)

    if not dry_run:
        persist_scores(conn, rows)

    publish_t = float(cfg["tos"]["thresholds"]["publish"])
    watchlist_t = float(cfg["tos"]["thresholds"]["watchlist"])
    publish = sum(1 for r in rows if r["tos"] >= publish_t)
    watchlist = sum(1 for r in rows if watchlist_t <= r["tos"] < publish_t)
    below = sum(1 for r in rows if r["tos"] < watchlist_t)
    elapsed = _time.monotonic() - t0
    line = (
        f"tos: {len(rows)} entities scored, {publish} publish (>={int(publish_t)}), "
        f"{watchlist} watchlist ({int(watchlist_t)}-{int(publish_t)}), "
        f"{below} below in {elapsed:.1f}s"
    )
    log.info(line)
    print(line)
    return {"scored": len(rows), "publish": publish, "watchlist": watchlist,
            "below": below}


def main(args) -> int:
    from discover_intel import db as db_mod
    conn = db_mod.connect(args.db)
    try:
        orchestrate(conn, market=args.market, dry_run=args.dry_run)
        return 0
    finally:
        conn.close()
