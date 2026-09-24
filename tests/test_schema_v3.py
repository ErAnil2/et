import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "sql" / "schema.sql"


def test_schema_v3_includes_new_tables():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"topic_stats", "topic_scores", "article_scores"} <= tables
    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 3


def test_topic_scores_pk_composite():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    pk_cols = [r[1] for r in conn.execute("PRAGMA table_info(topic_scores)").fetchall()
               if r[5] > 0]
    assert set(pk_cols) == {"scored_at", "market", "entity"}


def test_topic_stats_pk_composite():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    pk_cols = [r[1] for r in conn.execute("PRAGMA table_info(topic_stats)").fetchall()
               if r[5] > 0]
    assert set(pk_cols) == {"hour_utc", "market", "entity"}
