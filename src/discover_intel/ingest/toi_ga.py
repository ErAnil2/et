"""S2-D TOI Google Analytics Data API importer.

Pulls Times of India's Discover-attributed traffic (source=google,
medium=discover) into discover_articles with tool='toi_ga'.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def build_ga_client(sa_json_path: str) -> Any:
    """Return an authenticated BetaAnalyticsDataClient."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(
        sa_json_path,
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    return BetaAnalyticsDataClient(credentials=creds)


def run_report(client: Any, property_id: str, start: str, end: str) -> list[dict[str, Any]]:
    """Query GA Data API v1beta for Discover-attributed page-level metrics."""
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Filter, FilterExpression, FilterExpressionList, Metric,
        RunReportRequest,
    )

    source_filter = FilterExpression(filter=Filter(
        field_name="sessionSource",
        string_filter=Filter.StringFilter(value="google"),
    ))
    medium_filter = FilterExpression(filter=Filter(
        field_name="sessionMedium",
        string_filter=Filter.StringFilter(value="discover"),
    ))

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[
            Dimension(name="date"),
            Dimension(name="pagePath"),
            Dimension(name="pageTitle"),
            Dimension(name="sessionSource"),
            Dimension(name="sessionMedium"),
            Dimension(name="deviceCategory"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="engagedSessions"),
            Metric(name="engagementRate"),
            Metric(name="screenPageViews"),
        ],
        dimension_filter=FilterExpression(
            and_group=FilterExpressionList(expressions=[source_filter, medium_filter]),
        ),
        date_ranges=[DateRange(start_date=start, end_date=end)],
    )

    response = client.run_report(request=request)
    dim_names = ["date", "pagePath", "pageTitle",
                 "sessionSource", "sessionMedium", "deviceCategory"]
    metric_names = ["sessions", "engagedSessions", "engagementRate", "screenPageViews"]

    out: list[dict[str, Any]] = []
    for row in response.rows:
        d = {n: v.value for n, v in zip(dim_names, row.dimension_values)}
        for i, n in enumerate(metric_names):
            raw = row.metric_values[i].value
            if n in ("sessions", "engagedSessions", "screenPageViews"):
                d[n] = int(float(raw))
            else:
                d[n] = float(raw)
        out.append(d)
    return out


def _obs_id(observed_at: str, url: str) -> str:
    key = f"toi_ga|US|{observed_at}|{url}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _ga_date_to_iso(ga_date: str) -> str:
    """Convert YYYYMMDD to ISO UTC midnight."""
    return f"{ga_date[:4]}-{ga_date[4:6]}-{ga_date[6:8]}T00:00:00Z"


def persist_rows(conn: sqlite3.Connection, rows: list[dict[str, Any]],
                 market: str = "US") -> dict[str, int]:
    """Insert or update discover_articles rows from a GA report.

    Returns {'new': N, 'updated': M} — counted by pre-checking existence
    since SQLite's UPSERT rowcount doesn't distinguish insert vs update.
    """
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stats = {"new": 0, "updated": 0}

    for r in rows:
        observed_at = _ga_date_to_iso(r["date"])
        url = "https://timesofindia.indiatimes.com" + r["pagePath"]
        obs_id = _obs_id(observed_at, url)
        raw = json.dumps(r, ensure_ascii=False)

        existing = conn.execute(
            "SELECT 1 FROM discover_articles WHERE obs_id = ?", (obs_id,)
        ).fetchone()

        conn.execute(
            "INSERT INTO discover_articles "
            "(obs_id, tool, market, observed_at, source_file, imported_at, "
            "title, url, host, visibility, rank, time_on_feed_min, format, "
            "author, raw_json) "
            "VALUES (?, 'toi_ga', ?, ?, 'toi-ga-api', ?, ?, ?, "
            "'timesofindia.indiatimes.com', ?, NULL, NULL, NULL, NULL, ?) "
            "ON CONFLICT(obs_id) DO UPDATE SET "
            "visibility=excluded.visibility, raw_json=excluded.raw_json, "
            "imported_at=excluded.imported_at",
            (obs_id, market, observed_at, now, r["pageTitle"], url,
             r["sessions"], raw),
        )

        if existing is None:
            stats["new"] += 1
        else:
            stats["updated"] += 1

    conn.commit()
    return stats


def handle_ga_error(exc: Exception) -> int:
    """Print a remediation message for GA API errors; return exit code."""
    from google.api_core import exceptions as gexc

    if isinstance(exc, gexc.PermissionDenied):
        print(
            "toi-ga: 403 Forbidden -- the service account cannot access the property.\n"
            "  1. Enable Google Analytics Data API in Cloud project ga4-mcp-504403:\n"
            "     Console -> APIs & Services -> Library -> 'Google Analytics Data API' -> Enable\n"
            "  2. Grant the service account Viewer on GA4 property 230487101:\n"
            "     analytics.google.com -> Admin -> Property Access Management ->\n"
            "     Add users -> claude-ga-mcp@ga4-mcp-504403.iam.gserviceaccount.com -> Viewer",
            file=sys.stderr,
        )
        return 2

    if isinstance(exc, gexc.NotFound):
        print(
            "toi-ga: 404 Not Found -- property ID 230487101 not recognised.\n"
            "  Verify TOI_GA_PROPERTY_ID matches a real GA4 property "
            "(Admin -> Property details -> Property ID).",
            file=sys.stderr,
        )
        return 2

    print(f"toi-ga: unexpected error: {exc}", file=sys.stderr)
    return 1


def main_from_env(db_path: str, start: str | None, end: str | None,
                  dry_run: bool = False) -> int:
    """Entry point that reads env vars and orchestrates one run."""
    sa_json = os.environ.get("TOI_GA_SA_JSON")
    property_id = os.environ.get("TOI_GA_PROPERTY_ID")

    missing = [name for name, val in
               [("TOI_GA_SA_JSON", sa_json), ("TOI_GA_PROPERTY_ID", property_id)]
               if not val]
    if missing:
        print(f"toi-ga: missing required environment variables: {', '.join(missing)}\n"
              f"  Set with:  setx TOI_GA_SA_JSON \"<path>\"  and  "
              f"setx TOI_GA_PROPERTY_ID \"230487101\"",
              file=sys.stderr)
        return 2

    if end is None:
        end = (dt.datetime.now(dt.timezone.utc).date()
               - dt.timedelta(days=1)).isoformat()
    if start is None:
        end_dt = dt.date.fromisoformat(end)
        start = (end_dt - dt.timedelta(days=3)).isoformat()

    if dry_run:
        print(
            f"toi-ga dry-run: property=properties/{property_id} "
            f"start={start} end={end} "
            f"sa_json={sa_json} "
            f"filter=sessionSource=google AND sessionMedium=discover"
        )
        return 0

    if not Path(sa_json).exists():
        print(f"toi-ga: TOI_GA_SA_JSON does not point to a file: {sa_json}",
              file=sys.stderr)
        return 2

    try:
        client = build_ga_client(sa_json)
        rows = run_report(client, property_id=property_id, start=start, end=end)
    except Exception as exc:  # noqa: BLE001
        return handle_ga_error(exc)

    from discover_intel import db as db_mod
    conn = db_mod.connect(db_path)
    try:
        stats = persist_rows(conn, rows, market="US")
    finally:
        conn.close()

    print(f"toi-ga: {start}..{end}, {stats['new']} new, {stats['updated']} updated")
    return 0


def main(args) -> int:
    """CLI entry: python -m discover_intel toi-ga --db X --start Y --end Z [--dry-run]."""
    return main_from_env(db_path=args.db, start=args.start, end=args.end,
                         dry_run=args.dry_run)
