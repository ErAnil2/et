"""S2-B outcome matcher: link discover_articles to items via a 4-stage cascade."""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3

from discover_intel.util.url import strip_tracking

log = logging.getLogger(__name__)


def _normalise_title(s: str | None) -> str:
    if not s:
        return ""
    return " ".join(s.lower().split())


def _stripped_url_equals(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return strip_tracking(a) == strip_tracking(b)


def _since_iso(since_hours: int) -> str:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=since_hours)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")


def match_url(conn: sqlite3.Connection, since_hours: int) -> list[tuple[str, str]]:
    """Stage 1: exact URL match after tracking-strip."""
    cutoff = _since_iso(since_hours)
    rows = conn.execute(
        "SELECT i.item_id, i.url, o.obs_id, o.url "
        "FROM items i JOIN discover_articles o "
        "ON i.host = o.host "
        "WHERE o.observed_at >= ? AND o.url IS NOT NULL",
        (cutoff,),
    ).fetchall()
    pairs: list[tuple[str, str]] = []
    for item_id, item_url, obs_id, obs_url in rows:
        if _stripped_url_equals(item_url, obs_url):
            pairs.append((item_id, obs_id))
    return pairs


def match_canonical(conn: sqlite3.Connection, since_hours: int) -> list[tuple[str, str]]:
    """Stage 2: exact canonical-URL match after tracking-strip."""
    cutoff = _since_iso(since_hours)
    rows = conn.execute(
        "SELECT i.item_id, i.canonical_url, o.obs_id, o.url "
        "FROM items i JOIN discover_articles o "
        "ON i.host = o.host "
        "WHERE o.observed_at >= ? AND o.url IS NOT NULL "
        "AND i.canonical_url IS NOT NULL",
        (cutoff,),
    ).fetchall()
    pairs: list[tuple[str, str]] = []
    for item_id, canonical, obs_id, obs_url in rows:
        if _stripped_url_equals(canonical, obs_url):
            pairs.append((item_id, obs_id))
    return pairs


def match_title_exact(conn: sqlite3.Connection, since_hours: int) -> list[tuple[str, str]]:
    """Stage 3: same host + normalised title (title_hash) exact match."""
    import hashlib
    cutoff = _since_iso(since_hours)
    rows = conn.execute(
        "SELECT o.obs_id, o.host, o.title FROM discover_articles o "
        "WHERE o.observed_at >= ?",
        (cutoff,),
    ).fetchall()
    pairs: list[tuple[str, str]] = []
    for obs_id, host, obs_title in rows:
        norm = _normalise_title(obs_title)
        thash = hashlib.sha1(norm.encode("utf-8")).hexdigest()
        matches = conn.execute(
            "SELECT item_id FROM items "
            "WHERE host = ? AND (title_hash = ? OR lower(title) = ?)",
            (host, thash, norm),
        ).fetchall()
        for (item_id,) in matches:
            pairs.append((item_id, obs_id))
    return pairs


def match_title_fuzzy(conn: sqlite3.Connection, since_hours: int,
                      threshold: float = 0.85) -> list[tuple[str, str]]:
    """Stage 4: same host + rapidfuzz token_set_ratio >= threshold, ±48h window."""
    from rapidfuzz import fuzz
    cutoff = _since_iso(since_hours)
    obs_rows = conn.execute(
        "SELECT obs_id, host, title, observed_at FROM discover_articles "
        "WHERE observed_at >= ?",
        (cutoff,),
    ).fetchall()

    pairs: list[tuple[str, str]] = []
    for obs_id, host, obs_title, observed_at in obs_rows:
        obs_dt = dt.datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
        window_start = (obs_dt - dt.timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
        window_end = (obs_dt + dt.timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

        candidates = conn.execute(
            "SELECT item_id, title FROM items "
            "WHERE host = ? AND first_seen_at BETWEEN ? AND ?",
            (host, window_start, window_end),
        ).fetchall()
        for item_id, item_title in candidates:
            ratio = fuzz.token_set_ratio(item_title, obs_title) / 100.0
            if ratio >= threshold:
                pairs.append((item_id, obs_id))
    return pairs


def orchestrate(conn: sqlite3.Connection, since_hours: int = 72,
                dry_run: bool = False) -> dict[str, int]:
    """Run all four cascade stages, INSERT OR IGNORE into item_outcomes."""
    import time as _time
    t0 = _time.monotonic()
    now_iso = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    stages: list[tuple[str, list[tuple[str, str]], float]] = [
        ("url",          match_url(conn, since_hours),          1.0),
        ("canonical",    match_canonical(conn, since_hours),    1.0),
        ("title_exact",  match_title_exact(conn, since_hours),  1.0),
    ]
    stats = {"matched": 0, "url": 0, "canonical": 0, "title_exact": 0,
             "title_fuzzy": 0, "obs_new": 0, "unmatched": 0}

    for name, pairs, score in stages:
        for item_id, obs_id in pairs:
            if dry_run:
                stats[name] += 1
                stats["matched"] += 1
                continue
            cur = conn.execute(
                "INSERT OR IGNORE INTO item_outcomes "
                "(item_id, obs_id, match_type, match_score, matched_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (item_id, obs_id, name, score, now_iso),
            )
            if cur.rowcount == 1:
                stats[name] += 1
                stats["matched"] += 1

    from rapidfuzz import fuzz
    fuzzy_pairs = match_title_fuzzy(conn, since_hours)
    for item_id, obs_id in fuzzy_pairs:
        row = conn.execute(
            "SELECT i.title, o.title FROM items i, discover_articles o "
            "WHERE i.item_id = ? AND o.obs_id = ?",
            (item_id, obs_id),
        ).fetchone()
        if row is None:
            continue
        score = fuzz.token_set_ratio(row[0], row[1]) / 100.0
        if dry_run:
            stats["title_fuzzy"] += 1
            stats["matched"] += 1
            continue
        cur = conn.execute(
            "INSERT OR IGNORE INTO item_outcomes "
            "(item_id, obs_id, match_type, match_score, matched_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (item_id, obs_id, "title_fuzzy", score, now_iso),
        )
        if cur.rowcount == 1:
            stats["title_fuzzy"] += 1
            stats["matched"] += 1

    if not dry_run:
        conn.commit()

    obs_known_host = conn.execute(
        "SELECT count(DISTINCT o.obs_id) FROM discover_articles o "
        "JOIN sources s ON s.host = o.host AND s.enabled = 1 "
        "WHERE o.observed_at >= ?",
        (_since_iso(since_hours),),
    ).fetchone()[0]
    matched_known_host = conn.execute(
        "SELECT count(DISTINCT io.obs_id) FROM item_outcomes io "
        "JOIN discover_articles o ON o.obs_id = io.obs_id "
        "JOIN sources s ON s.host = o.host AND s.enabled = 1 "
        "WHERE o.observed_at >= ?",
        (_since_iso(since_hours),),
    ).fetchone()[0]
    ratio = (matched_known_host / obs_known_host * 100.0) if obs_known_host else 0.0
    stats["obs_new"] = obs_known_host
    stats["unmatched"] = obs_known_host - matched_known_host

    elapsed = _time.monotonic() - t0
    line = (
        f"match-outcomes: {obs_known_host} obs new, {stats['matched']} matched "
        f"({stats['url']} url, {stats['canonical']} canonical, "
        f"{stats['title_exact']} title_exact, {stats['title_fuzzy']} title_fuzzy), "
        f"{stats['unmatched']} unmatched, {elapsed:.1f}s"
    )
    log.info(line)
    print(line)
    print(f"known-host match rate: {ratio:.1f}%")
    if ratio < 70.0 and obs_known_host > 0:
        log.warning("match-outcomes: known-host ratio %.1f%% below 70%% threshold", ratio)
    return stats


def main(args) -> int:
    """CLI entry: python -m discover_intel match-outcomes --db X --since H [--dry-run]."""
    from discover_intel import db as db_mod
    conn = db_mod.connect(args.db)
    try:
        orchestrate(conn, since_hours=args.since, dry_run=args.dry_run)
        return 0
    finally:
        conn.close()
