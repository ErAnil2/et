import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "sql" / "schema.sql"


def test_schema_v4_includes_scorecards():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "scorecards" in tables
    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 4


def test_scorecards_pk_composite():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    pk_cols = [r[1] for r in conn.execute("PRAGMA table_info(scorecards)").fetchall()
               if r[5] > 0]
    assert set(pk_cols) == {"iso_week", "market"}
