import shutil
from pathlib import Path

from discover_intel.ingest.import_discover_file import import_file


def test_import_real_discovertrends_1547(conn, fixtures_dir: Path, tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "discover_import_mappings.yaml").write_text(
        Path("config/discover_import_mappings.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    src = fixtures_dir / "discovertrends_2026-09-23_1547.csv"
    working = tmp_path / "DiscoverTrends_2026-09-23_1547.csv"
    shutil.copyfile(src, working)

    result = import_file(conn, working, config_dir=cfg)
    assert result["tool"] == "discovertrends"
    assert result["observed_at"] == "2026-09-23T15:47:00Z"
    # 321 lines in the file: 1 header + 320 data rows
    assert result["new"] == 320
    (n,) = conn.execute("SELECT count(*) FROM discover_articles").fetchone()
    assert n == 320

    # Verify Author→host mapping
    (host,) = conn.execute(
        "SELECT host FROM discover_articles ORDER BY rank LIMIT 1"
    ).fetchone()
    assert "." in host  # is a domain, not a person's name


def test_import_idempotent(conn, fixtures_dir: Path, tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "discover_import_mappings.yaml").write_text(
        Path("config/discover_import_mappings.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    working = tmp_path / "DiscoverTrends_2026-09-23_1547.csv"
    shutil.copyfile(fixtures_dir / "discovertrends_2026-09-23_1547.csv", working)

    r1 = import_file(conn, working, config_dir=cfg)
    r2 = import_file(conn, working, config_dir=cfg)
    assert r1["new"] == 320
    assert r2["new"] == 0
    (n,) = conn.execute("SELECT count(*) FROM discover_articles").fetchone()
    assert n == 320
