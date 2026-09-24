import sqlite3
import subprocess
import sys
from pathlib import Path


def test_help_lists_all_subcommands():
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "--help"],
        capture_output=True, text=True, check=True,
    )
    out = r.stdout
    for cmd in ["init-db", "seed-sources", "feeds", "import-discover",
                "import-snapshot", "gsc", "backup", "vacuum", "db-stats"]:
        assert cmd in out, f"missing subcommand {cmd} in help"


def test_init_db_creates_warehouse(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    assert db_path.exists()
    (uv,) = sqlite3.connect(str(db_path)).execute("PRAGMA user_version").fetchone()
    assert uv == 3
    assert "init-db" in r.stdout


def test_resolve_urls_subcommand_in_help():
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "resolve-urls" in r.stdout


def test_resolve_urls_dry_run(tmp_path: Path):
    """Exercise the full CLI path with a fresh DB."""
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "resolve-urls",
         "--db", str(db_path), "--limit", "10", "--dry-run"],
        capture_output=True, text=True, check=True,
    )
    assert "resolve-urls:" in r.stdout
