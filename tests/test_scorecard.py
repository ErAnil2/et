import json
import subprocess
import sys
from pathlib import Path

from discover_intel.analysis.scorecard import (
    compute_scorecard, iso_week_bounds, persist_scorecard,
)


def _seed(conn):
    conn.execute(
        "INSERT INTO taxonomy (taxonomy_id, kind, label, parent_id, in_et_lane) "
        "VALUES ('lane:tech_ai', 'lane', 'Tech & AI', NULL, 1)"
    )
    conn.execute(
        "INSERT INTO topic_scores (scored_at, market, entity, tos, momentum, "
        "headroom, timing, format_match, lane_fit, suggested_format, "
        "evidence_json) VALUES ('2026-09-22T14:00:00Z', 'US', 'Fed', 78.0, "
        "0.8, 1.0, 0.7, 1.0, 1.0, 'news', '{}')"
    )
    conn.commit()


def test_iso_week_bounds_returns_monday_sunday():
    start, end = iso_week_bounds("2026-W39")
    assert start.endswith("T00:00:00Z")
    assert end.endswith("T23:59:59Z")


def test_compute_scorecard_empty_warehouse(conn):
    result = compute_scorecard(conn, iso_week="2026-W39", market="US")
    assert result["digest_topics_count"] == 0
    assert result["market_precision"] is None
    et = json.loads(result["et_conversion_json"])
    assert et["gsc_populated"] is False
    ct = json.loads(result["coverage_trends_json"])
    assert isinstance(ct, list)


def test_compute_scorecard_with_data(conn):
    _seed(conn)
    result = compute_scorecard(conn, iso_week="2026-W39", market="US")
    assert result["digest_topics_count"] == 1


def test_persist_scorecard_upserts(conn):
    row = {
        "iso_week": "2026-W39", "market": "US",
        "computed_at": "2026-09-24T06:00:00Z",
        "window_start": "2026-09-21T00:00:00Z",
        "window_end": "2026-09-27T23:59:59Z",
        "digest_topics_count": 0,
        "market_precision": None,
        "et_conversion_json": '{"gsc_populated": false}',
        "coverage_trends_json": "[]",
        "markdown_path": "data/scorecards/2026-W39.md",
    }
    persist_scorecard(conn, row)
    (n,) = conn.execute("SELECT count(*) FROM scorecards").fetchone()
    assert n == 1

    row["digest_topics_count"] = 15
    persist_scorecard(conn, row)
    (n, count) = conn.execute(
        "SELECT count(*), digest_topics_count FROM scorecards"
    ).fetchone()
    assert n == 1
    assert count == 15


def test_cli_scorecard_dry_run(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "scorecard",
         "--db", str(db_path), "--week", "2026-W39", "--dry-run"],
        capture_output=True, text=True, check=True,
    )
    assert "scorecard:" in r.stdout or "US Discover Scorecard" in r.stdout


def test_cli_scorecard_writes_markdown_and_row(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    out_dir = tmp_path / "scorecards"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "scorecard",
         "--db", str(db_path), "--week", "2026-W39",
         "--out", str(out_dir)],
        capture_output=True, text=True, check=True,
    )
    assert "scorecard:" in r.stdout
    latest = out_dir / "latest.md"
    dated = out_dir / "2026-W39.md"
    assert latest.exists()
    assert dated.exists()
    import sqlite3
    (n,) = sqlite3.connect(str(db_path)).execute(
        "SELECT count(*) FROM scorecards"
    ).fetchone()
    assert n == 1
