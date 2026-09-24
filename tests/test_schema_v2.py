import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "sql" / "schema.sql"


def test_schema_v2_includes_new_tables():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"item_outcomes", "taxonomy", "item_entities"} <= tables

    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 4


def test_item_outcomes_pk_is_composite():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    pk_cols = [r[1] for r in conn.execute("PRAGMA table_info(item_outcomes)").fetchall()
               if r[5] > 0]
    assert set(pk_cols) == {"item_id", "obs_id"}


def test_taxonomy_kind_check():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO taxonomy (taxonomy_id, kind, label) VALUES (?, ?, ?)",
        ("lane:test", "lane", "Test"),
    )
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO taxonomy (taxonomy_id, kind, label) VALUES (?, ?, ?)",
            ("bad:test", "not_a_kind", "Bad"),
        )
