import csv
from pathlib import Path

from discover_intel.config import seed_sources_from_xlsx


def test_seed_sources_from_real_xlsx(tmp_path: Path, fixtures_dir: Path):
    cfg = tmp_path / "config"
    result = seed_sources_from_xlsx(
        xlsx_path=fixtures_dir / "usa_top_publishers.xlsx",
        config_dir=cfg,
    )

    # Expected row counts per spec §13 acceptance #2:
    assert result["web"] >= 15   # ~20 (Sheet1 rows with a non-null RSS URL)
    assert result["gnews"] == 31 + 15 + 4  # 31 site-scoped + 15 beat + 4 sections = 50
    # xlsx has 100 rows; 6 are D2TR-name duplicates with NULL channel_id
    # (WGAL, KGW, KHOU, Fox Weather, CTVNews, ABC7 News — all covered by
    # sibling rows with resolved UC ids like wgaltv, KGW News, KHOU 11, etc.).
    # Net usable YouTube channels: 94.
    assert result["youtube"] >= 90

    web_rows = list(csv.DictReader((cfg / "sources_web.csv").open(encoding="utf-8")))
    assert web_rows, "sources_web.csv should have rows"
    assert web_rows[0].keys() >= {
        "source_id", "kind", "market", "name", "url", "host", "tier",
        "category", "enabled", "notes",
    }
    assert all(r["kind"] == "web" for r in web_rows)

    yt_rows = list(csv.DictReader((cfg / "sources_youtube.csv").open(encoding="utf-8")))
    assert all(r["url"].startswith(
        "https://www.youtube.com/feeds/videos.xml?channel_id="
    ) for r in yt_rows)

    gnews_rows = list(csv.DictReader((cfg / "sources_gnews.csv").open(encoding="utf-8")))
    kinds = {r["kind"] for r in gnews_rows}
    assert kinds == {"gnews_site", "gnews_query", "gnews_section"}
