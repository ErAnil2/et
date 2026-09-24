"""End-to-end smoke: init v3 warehouse, run all Sprint 3 CLIs on empty DB."""
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_init_creates_v3_tables(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    conn = sqlite3.connect(str(db_path))
    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 3
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"topic_stats", "topic_scores", "article_scores"} <= tables


def test_db_stats_lists_sprint3_tables(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "db-stats", "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    for t in ("topic_stats", "topic_scores", "article_scores"):
        assert t in r.stdout, f"db-stats missing {t}"


def test_empty_warehouse_build_topic_stats_zero_rows(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "build-topic-stats",
         "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    assert "0 rows" in r.stdout


def test_empty_warehouse_tos_zero_scored(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "tos",
         "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    assert "0 entities scored" in r.stdout


def test_empty_warehouse_digest_empty_markdown(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    out_dir = tmp_path / "digests"
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "digest",
         "--db", str(db_path), "--out", str(out_dir)],
        capture_output=True, text=True, check=True,
    )
    assert "digest:" in r.stdout
    latest = out_dir / "latest.md"
    assert latest.exists()
    assert "No topics" in latest.read_text(encoding="utf-8")


def test_drs_clickbait_below_gate(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "drs",
         "--title", "You won't believe what happened next at Fed meeting today wow",
         "--image-width", "1600",
         "--author", "Jane Doe",
         "--published-at", "2026-09-24T15:00:00Z",
         "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("DRS:"))
    val = float(line.split()[1])
    assert val < 70.0
