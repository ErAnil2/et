"""S2-A Google News URL resolver: decode-first, HEAD-fallback."""
from __future__ import annotations

import logging
import sqlite3
import time

import httpx

from discover_intel.analysis.gnews_decoder import decode_gnews_url
from discover_intel.util.http import TokenBucket, build_client
from discover_intel.util.url import strip_tracking

log = logging.getLogger(__name__)


def resolve_one(client: httpx.Client, url: str, bucket: TokenBucket | None) -> str | None:
    """Return the final publisher URL for a Google News article URL, or None."""
    decoded = decode_gnews_url(url)
    if decoded:
        return strip_tracking(decoded)

    if bucket is not None:
        bucket.acquire()
    try:
        resp = client.head(url, follow_redirects=True, timeout=10.0)
    except (httpx.TransportError, httpx.TimeoutException) as exc:
        log.warning("resolve-urls: HEAD failed for %s: %s", url, exc)
        return None

    if 400 <= resp.status_code < 500:
        return None
    if 500 <= resp.status_code < 600:
        return None

    final = str(resp.url)
    if final == url:
        return None
    return strip_tracking(final)


def orchestrate(conn: sqlite3.Connection, limit: int = 500,
                bucket: TokenBucket | None = None,
                client: httpx.Client | None = None,
                dry_run: bool = False) -> dict[str, int]:
    """Run S2-A once. Idempotent — only touches rows with canonical_url IS NULL."""
    t0 = time.monotonic()
    if bucket is None:
        bucket = TokenBucket(rate_per_sec=5, capacity=5)
    if client is None:
        client = build_client()

    rows = conn.execute(
        "SELECT item_id, url FROM items "
        "WHERE canonical_url IS NULL "
        "AND url LIKE 'https://news.google.com/rss/articles/%' "
        "ORDER BY first_seen_at DESC LIMIT ?",
        (limit,),
    ).fetchall()

    stats = {"candidates": len(rows), "decoded": 0, "head_resolved": 0, "failed": 0}

    for item_id, url in rows:
        canonical = resolve_one(client, url, bucket=bucket)
        if canonical is None:
            stats["failed"] += 1
            continue

        if decode_gnews_url(url) is not None:
            stats["decoded"] += 1
        else:
            stats["head_resolved"] += 1

        if not dry_run:
            conn.execute(
                "UPDATE items SET canonical_url = ? WHERE item_id = ?",
                (canonical, item_id),
            )
            conn.commit()

    elapsed = time.monotonic() - t0
    line = (
        f"resolve-urls: {stats['candidates']} candidates, "
        f"{stats['decoded']} decoded, {stats['head_resolved']} HEAD-resolved, "
        f"{stats['failed']} failed in {elapsed:.1f}s"
    )
    log.info(line)
    print(line)
    return stats


def main(args) -> int:
    """CLI entry: python -m discover_intel resolve-urls --db X --limit N [--dry-run]."""
    from discover_intel import db as db_mod
    conn = db_mod.connect(args.db)
    try:
        orchestrate(conn, limit=args.limit, dry_run=args.dry_run)
        return 0
    finally:
        conn.close()
