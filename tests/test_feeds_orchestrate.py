import sqlite3
import subprocess
import sys
from pathlib import Path

from discover_intel.db import upsert
from discover_intel.ingest.feeds import orchestrate


def _seed_two_sources(conn, fixtures_dir):
    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example.com", "url": "https://example.com/feed.xml",
        "host": "example.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    upsert(conn, "sources", {
        "source_id": "yt:UCXXX", "kind": "youtube", "market": "US",
        "name": "Sample Channel",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCXXX",
        "host": "youtube.com", "tier": "B", "category": "Local TV",
        "enabled": 1, "notes": None,
    }, key="source_id")


def test_orchestrate_uses_mocked_http(conn, fixtures_dir, httpx_mock):
    _seed_two_sources(conn, fixtures_dir)
    httpx_mock.add_response(
        url="https://example.com/feed.xml", status_code=200,
        content=(fixtures_dir / "native_rss_sample.xml").read_bytes(),
    )
    httpx_mock.add_response(
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCXXX",
        status_code=200,
        content=(fixtures_dir / "youtube_atom_sample.xml").read_bytes(),
    )
    stats = orchestrate(conn, kinds=["web", "youtube"], rate_per_sec=1000)
    assert stats["ok"] == 2
    assert stats["items_new"] == 4  # 2 native + 2 youtube
    (n_items,) = conn.execute("SELECT count(*) FROM items").fetchone()
    (n_polls,) = conn.execute("SELECT count(*) FROM feed_polls").fetchone()
    assert n_items == 4
    assert n_polls == 2


def test_orchestrate_skips_disabled_and_wrong_kind(conn, fixtures_dir, httpx_mock):
    upsert(conn, "sources", {
        "source_id": "web:on", "kind": "web", "market": "US",
        "name": "on", "url": "https://on.example/feed.xml",
        "host": "on.example", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    upsert(conn, "sources", {
        "source_id": "web:off", "kind": "web", "market": "US",
        "name": "off", "url": "https://off.example/feed.xml",
        "host": "off.example", "tier": None, "category": None,
        "enabled": 0, "notes": None,
    }, key="source_id")
    upsert(conn, "sources", {
        "source_id": "yt:X", "kind": "youtube", "market": "US",
        "name": "X",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=X",
        "host": "youtube.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    httpx_mock.add_response(url="https://on.example/feed.xml", status_code=200,
                            content=(fixtures_dir / "native_rss_sample.xml").read_bytes())
    stats = orchestrate(conn, kinds=["web"], rate_per_sec=1000)
    assert stats["ok"] == 1
    assert stats["skipped_disabled"] == 1
    (n,) = conn.execute("SELECT count(*) FROM feed_polls").fetchone()
    assert n == 1


def test_cli_feeds_dry_run_prints_urls(tmp_path: Path, fixtures_dir: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    c = sqlite3.connect(str(db_path))
    c.execute(
        "INSERT INTO sources (source_id, kind, market, name, url, host, "
        "enabled) VALUES (?, ?, ?, ?, ?, ?, 1)",
        ("web:example.com", "web", "US", "example.com",
         "https://example.com/feed.xml", "example.com"),
    )
    c.commit()
    c.close()

    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "feeds",
         "--db", str(db_path), "--kind", "web", "--dry-run"],
        capture_output=True, text=True, check=True,
    )
    assert "example.com" in r.stdout
    assert "dry-run" in r.stdout.lower()
