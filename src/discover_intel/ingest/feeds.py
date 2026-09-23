"""Feed ingestion — parser, persister, orchestrator."""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass

import feedparser

from discover_intel.config import Source
from discover_intel.util.http import TokenBucket, build_client, fetch_with_retry
from discover_intel.util.time import iso_utc, utc_now
from discover_intel.util.url import extract_host, strip_tracking

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedItem:
    url: str
    title: str
    host: str
    description: str | None
    author: str | None
    published_at: str | None  # ISO UTC or None


def _entry_published_iso(entry: object) -> str | None:
    tm = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tm is None:
        return None
    return iso_utc(dt.datetime(*tm[:6], tzinfo=dt.timezone.utc))


def _pick_link(entry: object) -> str:
    link = getattr(entry, "link", None)
    if link:
        return link
    for lnk in getattr(entry, "links", []) or []:
        href = lnk.get("href") if isinstance(lnk, dict) else None
        if href:
            return href
    return ""


def parse_feed(xml: bytes, source: Source) -> list[ParsedItem]:
    """Parse RSS/Atom bytes into ParsedItem list. Never raises on per-entry bugs."""
    d = feedparser.parse(xml)
    out: list[ParsedItem] = []
    for e in d.entries or []:
        try:
            url = _pick_link(e).strip()
            title = (getattr(e, "title", "") or "").strip()
            if not url or not title:
                continue
            # Google News URLs are kept as-is (Sprint 2 resolver handles them).
            if not url.startswith("https://news.google.com/rss/articles/"):
                url = strip_tracking(url)
            host = extract_host(url)
            out.append(ParsedItem(
                url=url,
                title=title,
                host=host,
                description=(getattr(e, "summary", None) or None),
                author=(getattr(e, "author", None) or None),
                published_at=_entry_published_iso(e),
            ))
        except Exception:  # noqa: BLE001 — per-entry safety
            log.exception("parse_feed: entry error in %s", source.source_id)
    return out


def item_id_for(source_id: str, url: str) -> str:
    return hashlib.sha1(f"{source_id}|{url}".encode()).hexdigest()


def _title_hash(title: str) -> str:
    norm = " ".join(title.lower().split())
    return hashlib.sha1(norm.encode()).hexdigest()


def persist_items(conn, source: Source, items: Iterable[ParsedItem]) -> dict:
    seen = 0
    new = 0
    now = iso_utc(utc_now())
    for it in items:
        seen += 1
        iid = item_id_for(source.source_id, it.url)
        cur = conn.execute("SELECT seen_count FROM items WHERE item_id = ?", (iid,)).fetchone()
        if cur is None:
            conn.execute(
                "INSERT INTO items ("
                "item_id, source_id, url, canonical_url, host, title, description, "
                "author, published_at, first_seen_at, last_seen_at, seen_count, title_hash"
                ") VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (iid, source.source_id, it.url, it.host, it.title,
                 it.description, it.author, it.published_at, now, now,
                 _title_hash(it.title)),
            )
            new += 1
        else:
            conn.execute(
                "UPDATE items SET last_seen_at = ?, seen_count = seen_count + 1 "
                "WHERE item_id = ?",
                (now, iid),
            )
    conn.commit()
    return {"seen": seen, "new": new}


def persist_poll(
    conn, source: Source, http_status: int | None, items_seen: int,
    items_new: int, duration_ms: int, error: str | None,
) -> str:
    polled_at = iso_utc(utc_now())
    poll_id = hashlib.sha1(f"{source.source_id}|{polled_at}".encode()).hexdigest()
    conn.execute(
        "INSERT INTO feed_polls ("
        "poll_id, source_id, polled_at, http_status, items_seen, items_new, "
        "duration_ms, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (poll_id, source.source_id, polled_at, http_status, items_seen,
         items_new, duration_ms, error),
    )
    conn.commit()
    return poll_id


def _sources_for_kinds(conn: sqlite3.Connection, kinds: list[str]) -> list[Source]:
    placeholders = ", ".join(["?"] * len(kinds))
    rows = conn.execute(
        f"SELECT source_id, kind, market, name, url, host, tier, category, "
        f"enabled, notes FROM sources WHERE kind IN ({placeholders}) "
        f"ORDER BY kind, source_id",
        kinds,
    ).fetchall()
    return [Source(**dict(r)) for r in rows]


def orchestrate(
    conn: sqlite3.Connection,
    kinds: list[str],
    rate_per_sec: float = 5.0,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    started = time.monotonic()
    stats = {"total": 0, "ok": 0, "http_4xx": 0, "http_5xx": 0,
             "error": 0, "skipped_disabled": 0, "items_seen": 0, "items_new": 0}
    bucket = TokenBucket(rate_per_sec=rate_per_sec, capacity=max(1, int(rate_per_sec)))
    client = build_client()
    all_srcs = _sources_for_kinds(conn, kinds)

    to_poll: list[Source] = []
    for s in all_srcs:
        if s.enabled != 1:
            stats["skipped_disabled"] += 1
            continue
        to_poll.append(s)
    if limit is not None:
        to_poll = to_poll[:limit]

    for s in to_poll:
        stats["total"] += 1
        if dry_run:
            print(f"dry-run: would GET {s.url}  (source_id={s.source_id})")
            continue

        t0 = time.monotonic()
        error: str | None = None
        http_status: int | None = None
        items_seen = items_new = 0
        try:
            r = fetch_with_retry(client, s.url, bucket=bucket)
            http_status = r.status_code
            if 200 <= r.status_code < 300:
                items = parse_feed(r.content, s)
                res = persist_items(conn, s, items)
                items_seen = res["seen"]
                items_new = res["new"]
                stats["ok"] += 1
            elif 400 <= r.status_code < 500:
                stats["http_4xx"] += 1
            else:
                stats["http_5xx"] += 1
        except Exception as exc:  # noqa: BLE001 — per-source safety
            error = f"{type(exc).__name__}: {exc}"
            stats["error"] += 1
            log.exception("feeds: fetch failed for %s", s.source_id)

        dur_ms = int((time.monotonic() - t0) * 1000)
        stats["items_seen"] += items_seen
        stats["items_new"] += items_new
        persist_poll(
            conn, s, http_status=http_status, items_seen=items_seen,
            items_new=items_new, duration_ms=dur_ms, error=error,
        )

    elapsed = time.monotonic() - started
    log.info(
        "feeds: polled %d sources, %d ok, %d 4xx, %d 5xx, %d err, %d new items in %.1fs",
        stats["total"], stats["ok"], stats["http_4xx"], stats["http_5xx"],
        stats["error"], stats["items_new"], elapsed,
    )
    print(
        f"feeds: polled {stats['total']} sources, {stats['ok']} ok, "
        f"{stats['http_4xx']} 4xx, {stats['http_5xx']} 5xx, "
        f"{stats['error']} err, {stats['items_new']} new items in {elapsed:.1f}s"
    )
    return stats


def main(args) -> int:
    """Entry point invoked from cli.py."""
    kinds = [k.strip() for k in args.kind.split(",") if k.strip()]
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    stats = orchestrate(
        conn, kinds=kinds,
        rate_per_sec=args.rate_per_sec,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    conn.close()
    return 0 if stats["error"] == 0 or (stats["ok"] + stats["error"] > 0) else 1
