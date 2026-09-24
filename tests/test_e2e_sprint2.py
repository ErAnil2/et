"""End-to-end smoke: init a Sprint-1 warehouse, then apply the v2 schema and
verify all Sprint 2 tables are present + db-stats reports them."""
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_v2_schema_applies_cleanly(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    assert "init-db" in r.stdout

    conn = sqlite3.connect(str(db_path))
    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 2

    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"sources", "items", "feed_polls", "discover_articles",
            "discover_snapshots", "gsc_discover",
            "item_outcomes", "taxonomy", "item_entities"} <= tables


def test_db_stats_lists_new_tables(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "db-stats", "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    for t in ("item_outcomes", "taxonomy", "item_entities"):
        assert t in r.stdout, f"db-stats missing {t}"
