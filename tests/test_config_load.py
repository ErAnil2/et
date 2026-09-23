from pathlib import Path

from discover_intel.config import Source, load_sources


def test_load_sources_reads_three_csvs(tmp_path: Path, fixtures_dir: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    for name in ("sources_web.csv", "sources_gnews.csv", "sources_youtube.csv"):
        (cfg / name).write_text(
            (fixtures_dir / f"mini_{name}").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    srcs = load_sources(cfg)
    assert len(srcs) == 3
    kinds = sorted(s.kind for s in srcs)
    assert kinds == ["gnews_query", "web", "youtube"]
    assert all(isinstance(s, Source) for s in srcs)
    (yt,) = [s for s in srcs if s.kind == "youtube"]
    assert yt.tier == "B" and yt.category == "Local TV"
