"""Feed ingestion — parser, persister, orchestrator."""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
from collections.abc import Iterable
from dataclasses import dataclass

import feedparser

from discover_intel.config import Source
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
