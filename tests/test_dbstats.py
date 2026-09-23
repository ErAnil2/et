import subprocess
import sys
from pathlib import Path


def test_db_stats_prints_all_tables(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "db-stats", "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    out = r.stdout
    for t in ("sources", "items", "feed_polls", "discover_articles",
              "discover_snapshots", "gsc_discover"):
        assert t in out
        assert f"{t}=0" in out or f"{t}: 0" in out


def test_dispatcher_lists_no_stubs():
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "stub" not in r.stdout.lower()
