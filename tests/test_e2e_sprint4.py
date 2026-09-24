"""End-to-end smoke: init v4 warehouse, run scorecard on empty DB."""
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_init_creates_scorecards_table(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    conn = sqlite3.connect(str(db_path))
    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 4
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "scorecards" in tables


def test_db_stats_lists_scorecards(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "db-stats", "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    assert "scorecards" in r.stdout


def test_empty_warehouse_scorecard_writes_row_and_md(tmp_path: Path):
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
    assert (out_dir / "2026-W39.md").exists()
    assert (out_dir / "latest.md").exists()

    md = (out_dir / "latest.md").read_text(encoding="utf-8")
    assert "No digests were produced this week" in md
    assert "GSC not populated" in md
