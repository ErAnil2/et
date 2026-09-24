import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "sql" / "schema.sql"


def test_schema_loads_and_creates_six_tables():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"sources", "items", "feed_polls", "discover_articles",
            "discover_snapshots", "gsc_discover"} <= tables

    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 4  # bumped in Sprint 2 (schema.sql PRAGMA)
