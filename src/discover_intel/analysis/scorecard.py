"""S4 weekly scorecard — compute + persist + render Markdown."""
from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import sqlite3
import sys
from pathlib import Path

from jinja2 import Template

from discover_intel.delivery.dashboard import (
    coverage_trends_data, et_conversion_data,
)

log = logging.getLogger(__name__)


def iso_week_bounds(iso_week: str) -> tuple[str, str]:
    """Return (window_start, window_end) as ISO UTC strings for a YYYY-Www week.

    Week starts Monday 00:00:00Z, ends Sunday 23:59:59Z.
    """
    year_s, week_s = iso_week.split("-W")
    year = int(year_s)
    week = int(week_s)
    monday = dt.date.fromisocalendar(year, week, 1)
    sunday = monday + dt.timedelta(days=6)
    return (
        f"{monday.isoformat()}T00:00:00Z",
        f"{sunday.isoformat()}T23:59:59Z",
    )


def _current_iso_week(now: dt.datetime | None = None) -> str:
    """Return YYYY-Www of the ISO week ending yesterday UTC."""
    n = now or dt.datetime.now(dt.timezone.utc)
    yesterday = (n - dt.timedelta(days=1)).date()
    y, w, _ = yesterday.isocalendar()
    return f"{y}-W{w:02d}"


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_market_precision(conn: sqlite3.Connection, window_start: str,
                               window_end: str) -> tuple[int, float | None]:
    """Return (digest_topics_count, market_precision_pct_or_None) for the window."""
    (digest_count,) = conn.execute(
        "SELECT count(DISTINCT entity) FROM topic_scores "
        "WHERE scored_at BETWEEN ? AND ? AND tos >= 60.0",
        (window_start, window_end),
    ).fetchone()
    if digest_count == 0:
        return 0, None

    # Entities that had a matching discover_articles observation within 48h of scored_at
    (hits,) = conn.execute(
        """
        SELECT COUNT(DISTINCT t.entity) FROM topic_scores t
        WHERE t.scored_at BETWEEN ? AND ? AND t.tos >= 60.0
          AND EXISTS (
            SELECT 1 FROM discover_articles o
            WHERE o.observed_at BETWEEN t.scored_at
              AND datetime(t.scored_at, '+48 hours')
            AND o.title LIKE '%' || t.entity || '%'
          )
        """,
        (window_start, window_end),
    ).fetchone()
    return digest_count, (hits / digest_count * 100.0)


def compute_scorecard(conn: sqlite3.Connection, iso_week: str,
                      market: str = "US") -> dict:
    """Compute all 3 metrics for a given ISO week. Returns row-shape dict."""
    window_start, window_end = iso_week_bounds(iso_week)
    digest_count, precision = _compute_market_precision(conn, window_start, window_end)

    et = et_conversion_data(conn)
    # Flatten et_conversion for JSON storage
    et_flat: dict = {"gsc_populated": et.get("gsc_populated", False)}
    if et.get("gsc_populated"):
        on_df = et["on_digest"]
        off_df = et["off_digest"]
        et_flat["on_digest_avg_impressions"] = (
            float(on_df["avg_imp"].iloc[0]) if len(on_df) and on_df["avg_imp"].iloc[0] is not None else 0.0
        )
        et_flat["on_digest_avg_clicks"] = (
            float(on_df["avg_clk"].iloc[0]) if len(on_df) and on_df["avg_clk"].iloc[0] is not None else 0.0
        )
        et_flat["off_digest_avg_impressions"] = (
            float(off_df["avg_imp"].iloc[0]) if len(off_df) and off_df["avg_imp"].iloc[0] is not None else 0.0
        )
        et_flat["off_digest_avg_clicks"] = (
            float(off_df["avg_clk"].iloc[0]) if len(off_df) and off_df["avg_clk"].iloc[0] is not None else 0.0
        )
    else:
        et_flat["message"] = et.get("message", "GSC not populated")

    coverage_df = coverage_trends_data(conn, window_start, window_end)
    coverage = coverage_df.to_dict(orient="records") if not coverage_df.empty else []

    return {
        "iso_week": iso_week,
        "market": market,
        "computed_at": _iso_now(),
        "window_start": window_start,
        "window_end": window_end,
        "digest_topics_count": int(digest_count),
        "market_precision": precision,
        "et_conversion_json": json.dumps(et_flat),
        "coverage_trends_json": json.dumps(coverage),
        "markdown_path": f"data/scorecards/{iso_week}.md",
    }


def persist_scorecard(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO scorecards "
        "(iso_week, market, computed_at, window_start, window_end, "
        "digest_topics_count, market_precision, et_conversion_json, "
        "coverage_trends_json, markdown_path) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (row["iso_week"], row["market"], row["computed_at"],
         row["window_start"], row["window_end"],
         row["digest_topics_count"], row["market_precision"],
         row["et_conversion_json"], row["coverage_trends_json"],
         row["markdown_path"]),
    )
    conn.commit()


def _template_path() -> Path:
    return (Path(__file__).parent.parent / "delivery"
            / "scorecard_template.md.j2")


def render_scorecard(row: dict) -> str:
    template = Template(_template_path().read_text(encoding="utf-8"))
    return template.render(
        iso_week=row["iso_week"],
        window_start=row["window_start"],
        window_end=row["window_end"],
        computed_at=row["computed_at"],
        digest_topics_count=row["digest_topics_count"],
        market_precision=row["market_precision"],
        et_conversion=json.loads(row["et_conversion_json"]),
        coverage_trends=json.loads(row["coverage_trends_json"]),
    )


def write_scorecard(text: str, out_dir: Path, iso_week: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{iso_week}.md"
    dest.write_text(text, encoding="utf-8")
    latest = out_dir / "latest.md"
    shutil.copyfile(dest, latest)
    return dest


def main(args) -> int:
    from discover_intel import db as db_mod
    conn = db_mod.connect(args.db)
    try:
        iso_week = args.week or _current_iso_week()
        row = compute_scorecard(conn, iso_week=iso_week, market=args.market)
        text = render_scorecard(row)
        if args.dry_run:
            print(text)
            print(f"scorecard: dry-run rendered {iso_week}")
            return 0
        out_dir = Path(args.out)
        dest = write_scorecard(text, out_dir, iso_week)
        try:
            row["markdown_path"] = str(dest.relative_to(Path.cwd()))
        except ValueError:
            row["markdown_path"] = str(dest)
        persist_scorecard(conn, row)
        et = json.loads(row["et_conversion_json"])
        coverage = json.loads(row["coverage_trends_json"])
        precision_s = (f"{row['market_precision']:.1f}%"
                       if row["market_precision"] is not None else "N/A")
        print(f"scorecard: {iso_week} {args.market} -- "
              f"{row['digest_topics_count']} digest topics, "
              f"market_precision={precision_s}, "
              f"gsc_populated={et.get('gsc_populated', False)}, "
              f"{len(coverage)} lanes covered")
        return 0
    finally:
        conn.close()
