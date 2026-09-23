"""S2-D TOI Google Analytics Data API importer.

Pulls Times of India's Discover-attributed traffic (source=google,
medium=discover) into discover_articles with tool='toi_ga'.
"""
from __future__ import annotations

import logging
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
