import shutil
from pathlib import Path

from discover_intel.ingest.import_discover_file import watch_directory


def test_watch_processes_and_moves_file(conn, fixtures_dir: Path, tmp_path: Path):
    imports = tmp_path / "imports" / "discover"
    imports.mkdir(parents=True)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "discover_import_mappings.yaml").write_text(
        Path("config/discover_import_mappings.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    src = imports / "DiscoverTrends_2026-09-23_1547.csv"
    shutil.copyfile(fixtures_dir / "discovertrends_2026-09-23_1547.csv", src)

    result = watch_directory(conn, imports, config_dir=tmp_path / "config")
    assert result["files_processed"] == 1
    assert not src.exists()
    processed = list((imports / "processed").rglob("*.csv"))
    assert len(processed) == 1
    (n,) = conn.execute("SELECT count(*) FROM discover_articles").fetchone()
    assert n == 320


def test_watch_moves_unparseable_to_failed(conn, tmp_path: Path):
    imports = tmp_path / "imports" / "discover"
    imports.mkdir(parents=True)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "discover_import_mappings.yaml").write_text(
        Path("config/discover_import_mappings.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    bad = imports / "not-a-discover-file.csv"
    bad.write_text("Wrong,Headers,Here\n1,2,3\n", encoding="utf-8")
    result = watch_directory(conn, imports, config_dir=tmp_path / "config")
    assert result["files_failed"] == 1
    assert not bad.exists()
    failed = list((imports / "failed").rglob("*.csv"))
    assert len(failed) == 1
