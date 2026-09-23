from pathlib import Path

from discover_intel.config import Source
from discover_intel.ingest.feeds import ParsedItem, parse_feed


def _mk_source(kind: str, host: str = "example.com") -> Source:
    return Source(
        source_id=f"{kind}:{host}", kind=kind, market="US",
        name=host, url=f"https://{host}/feed", host=host,
        tier=None, category=None, enabled=1, notes=None,
    )


def test_parse_native_rss(fixtures_dir: Path):
    xml = (fixtures_dir / "native_rss_sample.xml").read_bytes()
    src = _mk_source("web", "example.com")
    items = parse_feed(xml, src)
    assert len(items) == 2
    assert all(isinstance(i, ParsedItem) for i in items)
    a = items[0]
    assert a.title == "Fed cuts rates by 25 bps"
    assert a.url.startswith("https://example.com/news/fed-cut")
    assert a.host == "example.com"
    assert a.published_at is not None and "2026-09-23" in a.published_at
    assert a.author == "jane@example.com (Jane Doe)"


def test_parse_gnews_rss(fixtures_dir: Path):
    xml = (fixtures_dir / "google_news_rss_sample.xml").read_bytes()
    src = _mk_source("gnews_site", "example.com")
    items = parse_feed(xml, src)
    assert len(items) == 2
    assert all(i.url.startswith("https://news.google.com/rss/articles/") for i in items)


def test_parse_youtube_atom(fixtures_dir: Path):
    xml = (fixtures_dir / "youtube_atom_sample.xml").read_bytes()
    src = _mk_source("youtube", "youtube.com")
    items = parse_feed(xml, src)
    assert len(items) == 2
    assert all(i.url.startswith("https://www.youtube.com/watch?v=") for i in items)
    assert items[0].title == "Live: hurricane update"
