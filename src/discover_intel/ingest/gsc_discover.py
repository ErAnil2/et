"""Nightly Google Search Console pull (type=discover, country=usa)."""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import sqlite3
import sys
from pathlib import Path
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


def handle_http_error(exc) -> int:
    """Print a remediation message and return the exit code."""
    status = getattr(getattr(exc, "resp", None), "status", None) or 0
    if status == 403:
        sys.stderr.write(
            "gsc: 403 Forbidden — the service account cannot read the GSC property.\n"
            "  Remediation:\n"
            "    1. Search Console -> Settings -> Users and permissions -> Add user\n"
            "       claude-ga-mcp@ga4-mcp-504403.iam.gserviceaccount.com (Restricted or Full).\n"
            "    2. Google Cloud Console -> APIs & Services -> Library ->\n"
            "       enable 'Google Search Console API' in project ga4-mcp-504403.\n"
        )
        return 2
    if status == 404:
        sys.stderr.write(
            "gsc: 404 Not Found — the property URL was not recognised.\n"
            "  Check GSC_PROPERTY: use 'https://economictimes.indiatimes.com/' for a URL\n"
            "  property, or 'sc-domain:economictimes.indiatimes.com' for a Domain property.\n"
        )
        return 2
    sys.stderr.write(f"gsc: HTTP error {status}: {exc}\n")
    return 1


def _default_dates() -> tuple[str, str]:
    end = utc_now().date() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=3)
    return start.isoformat(), end.isoformat()


def main_from_env(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="discover_intel gsc")
    parser.add_argument("--db", required=True)
    d_start, d_end = _default_dates()
    parser.add_argument("--start", default=d_start)
    parser.add_argument("--end", default=d_end)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    sa = os.environ.get("GSC_SA_JSON")
    prop = os.environ.get("GSC_PROPERTY")
    if not sa or not prop:
        sys.stderr.write(
            "gsc: missing env vars.\n"
            "  Set GSC_SA_JSON to the service account JSON path (setx GSC_SA_JSON ...).\n"
            "  Set GSC_PROPERTY to the property URL or sc-domain: form.\n"
        )
        return 2

    if args.dry_run:
        print(
            f"gsc dry-run: property={prop}  dates={args.start}..{args.end}  "
            f"dimensions=[date,country,device,page]  filter=country=usa"
        )
        return 0

    if not Path(sa).exists():
        sys.stderr.write(f"gsc: GSC_SA_JSON does not exist: {sa}\n")
        return 2

    try:
        from googleapiclient.errors import HttpError

        service = build_gsc_service(sa)
        conn = sqlite3.connect(args.db)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            n = query_and_upsert(conn, service, prop, args.start, args.end)
        finally:
            conn.close()
        print(
            f"gsc: pulled {args.start}..{args.end}, {n} rows upserted (usa)"
        )
        return 0
    except HttpError as exc:
        return handle_http_error(exc)


def main(args) -> int:
    argv: list[str] = ["--db", args.db]
    if getattr(args, "start", None):
        argv += ["--start", args.start]
    if getattr(args, "end", None):
        argv += ["--end", args.end]
    if args.dry_run:
        argv.append("--dry-run")
    return main_from_env(argv)
