from pathlib import Path

from discover_intel.ingest.import_snapshot import import_snapshot


def test_import_snapshot_tsv(conn, fixtures_dir: Path):
    r = import_snapshot(
        conn,
        source_path=fixtures_dir / "d2tr_snapshot_sample.tsv",
        taken_at="2026-09-23T15:00:00Z",
        market="US",
        source_kind="channel",
    )
    assert r["new"] == 2
    (n,) = conn.execute("SELECT count(*) FROM discover_snapshots").fetchone()
    assert n == 2
    (v, m, tier) = conn.execute(
        "SELECT visibility_2h, time_on_feed_min, tier FROM discover_snapshots "
        "WHERE host_or_channel = 'UCinjnmQEwCddOudyCC1v7qA'"
    ).fetchone()
    assert v == 547_790.0
    assert m == 120.0
    assert tier == "B"


def test_import_snapshot_idempotent(conn, fixtures_dir: Path):
    kwargs = dict(source_path=fixtures_dir / "d2tr_snapshot_sample.tsv",
                  taken_at="2026-09-23T15:00:00Z", market="US",
                  source_kind="channel")
    r1 = import_snapshot(conn, **kwargs)
    r2 = import_snapshot(conn, **kwargs)
    assert r1["new"] == 2
    assert r2["new"] == 0
