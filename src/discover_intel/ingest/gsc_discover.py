"""Nightly Google Search Console pull (type=discover, country=usa)."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from discover_intel.util.time import iso_utc, utc_now

log = logging.getLogger(__name__)


def build_gsc_service(sa_json_path: str):
    """Return an authenticated searchconsole v1 service. Real path — not mocked."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        sa_json_path,
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
    )
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def _paginate(service, property_url: str, start: str, end: str, page_size: int = 25000):
    start_row = 0
    while True:
        body: dict[str, Any] = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["date", "country", "device", "page"],
            "type": "discover",
            "dimensionFilterGroups": [{
                "filters": [{
                    "dimension": "country",
                    "operator": "equals",
                    "expression": "usa",
                }],
            }],
            "rowLimit": page_size,
            "startRow": start_row,
        }
        resp = service.searchanalytics().query(
            siteUrl=property_url, body=body
        ).execute()
        rows = resp.get("rows") or []
        yield from rows
        if len(rows) < page_size:
            return
        start_row += page_size


def query_and_upsert(
    conn: sqlite3.Connection,
    service: Any,
    property_url: str,
    start: str,
    end: str,
) -> int:
    imported_at = iso_utc(utc_now())
    n = 0
    for r in _paginate(service, property_url, start, end):
        date_, country, device, page = r["keys"]
        conn.execute(
            "INSERT INTO gsc_discover (date, country, device, page, "
            "impressions, clicks, ctr, position, imported_at) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(date, country, device, page) DO UPDATE SET "
            "impressions=excluded.impressions, clicks=excluded.clicks, "
            "ctr=excluded.ctr, position=excluded.position, "
            "imported_at=excluded.imported_at",
            (date_, country, device, page,
             r.get("impressions", 0), r.get("clicks", 0),
             r.get("ctr"), r.get("position"), imported_at),
        )
        n += 1
    conn.commit()
    return n
