"""Sqlite connection helpers and a small upsert utility."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "sql" / "schema.sql"


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def apply_schema(conn: sqlite3.Connection, schema_path: Path | None = None) -> None:
    """Idempotent — safe to call at the start of every job."""
    path = schema_path or SCHEMA_PATH
    conn.executescript(path.read_text(encoding="utf-8"))
    conn.commit()


def upsert(conn: sqlite3.Connection, table: str, row: dict[str, object], key: str) -> None:
    """INSERT ... ON CONFLICT(key) DO UPDATE SET ... — parameterised."""
    cols = list(row.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    updates = ", ".join([f"{c} = excluded.{c}" for c in cols if c != key])
    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT({key}) DO UPDATE SET {updates}"
    )
    conn.execute(sql, [row[c] for c in cols])
    conn.commit()
