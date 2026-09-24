import subprocess
import sys
from pathlib import Path

from discover_intel.analysis.build_topic_stats import persist_stats


def test_persist_stats_inserts_and_upserts(conn):
    rows = [
        {"hour_utc": "2026-09-24T12:00:00Z", "market": "US", "entity": "Fed",
         "new_items": 2, "competitor_hosts": 3, "gnews_query_hits": 1,
         "discover_obs": 1, "discover_visibility": 100.0,
         "avg_time_on_feed_min": None, "winning_format": "news"},
    ]
    persist_stats(conn, rows)
    (n,) = conn.execute("SELECT count(*) FROM topic_stats").fetchone()
    assert n == 1

    rows[0]["new_items"] = 5
    persist_stats(conn, rows)
    (n, new_items) = conn.execute(
        "SELECT count(*), new_items FROM topic_stats"
    ).fetchone()
    assert n == 1
    assert new_items == 5


def test_cli_build_topic_stats_dry_run(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "build-topic-stats",
         "--db", str(db_path), "--dry-run"],
        capture_output=True, text=True, check=True,
    )
    assert "build-topic-stats:" in r.stdout
