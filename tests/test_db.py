import sqlite3
from pathlib import Path

from discover_intel import db


def test_connect_sets_pragmas(tmp_path: Path):
    conn = db.connect(tmp_path / "w.db")
    (fk,) = conn.execute("PRAGMA foreign_keys").fetchone()
    (jm,) = conn.execute("PRAGMA journal_mode").fetchone()
    assert fk == 1
    assert jm.lower() == "wal"
    assert conn.row_factory is sqlite3.Row


def test_apply_schema_is_idempotent(tmp_path: Path):
    path = tmp_path / "w.db"
    conn = db.connect(path)
    db.apply_schema(conn)
    db.apply_schema(conn)  # second call must not error
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "sources" in tables
    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 1


def test_upsert_inserts_and_updates(tmp_path: Path):
    conn = db.connect(tmp_path / "w.db")
    db.apply_schema(conn)
    row = {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed", "host": "example.com",
        "tier": None, "category": None, "enabled": 1, "notes": None,
    }
    db.upsert(conn, "sources", row, key="source_id")
    (n,) = conn.execute("SELECT count(*) FROM sources").fetchone()
    assert n == 1

    row["name"] = "example-updated"
    db.upsert(conn, "sources", row, key="source_id")
    (name,) = conn.execute("SELECT name FROM sources").fetchone()
    assert name == "example-updated"


def test_conn_fixture_has_schema(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "items" in tables
