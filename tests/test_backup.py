import datetime as dt
from pathlib import Path

from discover_intel.db import apply_schema, connect
from discover_intel.ops.backup import backup_db, prune_backups


def test_backup_creates_dated_file(tmp_path: Path):
    src = tmp_path / "wh.db"
    conn = connect(src)
    apply_schema(conn)
    conn.execute(
        "INSERT INTO sources (source_id, kind, market, name, url, enabled) "
        "VALUES ('x', 'web', 'US', 'x', 'https://x/y', 1)"
    )
    conn.commit()
    conn.close()

    dest_dir = tmp_path / "backups"
    path = backup_db(src, dest_dir)
    assert path.exists()
    assert path.name.startswith("warehouse-")
    assert path.suffix == ".db"


def test_backup_refuses_second_same_day_unless_force(tmp_path: Path):
    src = tmp_path / "wh.db"
    apply_schema(connect(src))
    dest_dir = tmp_path / "backups"
    p1 = backup_db(src, dest_dir)
    p2 = backup_db(src, dest_dir)
    assert p1 == p2
    p3 = backup_db(src, dest_dir, force=True)
    assert p3 == p1  # same filename, but rewritten


def test_prune_keeps_recent_dailies_and_sundays(tmp_path: Path):
    d = tmp_path / "backups"
    d.mkdir()
    base = dt.date(2026, 1, 1)
    for i in range(30):
        day = base + dt.timedelta(days=i)
        (d / f"warehouse-{day.isoformat()}.db").write_bytes(b"x")

    kept = prune_backups(d, keep_dailies=14, ref_date=base + dt.timedelta(days=29))
    assert len(kept) >= 14
    # All Sundays should survive
    for i in range(30):
        day = base + dt.timedelta(days=i)
        if day.weekday() == 6:  # Sunday
            assert (d / f"warehouse-{day.isoformat()}.db").exists()
