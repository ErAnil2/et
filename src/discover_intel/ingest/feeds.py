"""Feed ingestion — parser, persister, orchestrator."""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

import feedparser

from discover_intel.config import Source
from discover_intel.util.time import iso_utc
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
