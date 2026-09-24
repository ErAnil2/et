import json
import subprocess
import sys
from pathlib import Path

from discover_intel.delivery.slack_digest import render_digest, write_digest


def _seed_topic_scores(conn) -> None:
    ev = json.dumps({
        "top_discover_titles": [
            {"title": "Fed cuts by 25", "host": "nj.com", "visibility": 100.0}
        ],
        "competitor_hosts": ["nj.com", "cbs.com"],
        "beat_queries": ["Federal Reserve"],
        "stats_snapshot": {"new_items": 5},
    })
    conn.execute(
        "INSERT INTO topic_scores (scored_at, market, entity, tos, momentum, "
        "headroom, timing, format_match, lane_fit, suggested_format, "
        "evidence_json) VALUES ('2026-09-24T14:00:00Z', 'US', 'Federal Reserve', "
        "78.5, 0.8, 1.0, 0.7, 1.0, 1.0, 'news', ?)",
        (ev,),
    )
    conn.execute(
        "INSERT INTO topic_scores (scored_at, market, entity, tos, momentum, "
        "headroom, timing, format_match, lane_fit, suggested_format, "
        "evidence_json) VALUES ('2026-09-24T14:00:00Z', 'US', 'Below Threshold', "
        "40.0, 0.4, 0.5, 0.3, 0.5, 0.3, 'news', ?)",
        (ev,),
    )
    conn.commit()


def _min_config() -> dict:
    return {
        "tos": {
            "thresholds": {"publish": 60.0, "watchlist": 45.0},
            "suggested_headline_patterns": {
                "news": "{entity}: {fact}",
                "analysis": "Why {entity}...",
                "default": "{entity}: {angle}",
            },
        }
    }


def test_render_digest_includes_publish_threshold_topics(conn):
    _seed_topic_scores(conn)
    text = render_digest(conn, top_n=15, config=_min_config())
    assert "Federal Reserve" in text
    assert "TOS 78" in text or "78.5" in text
    assert "Below Threshold" not in text


def test_render_digest_empty_topic_scores_returns_placeholder(conn):
    text = render_digest(conn, top_n=15, config=_min_config())
    assert "No topics" in text or "0 topics" in text or "empty" in text.lower()


def test_write_digest_creates_timestamped_and_latest(conn, tmp_path):
    _seed_topic_scores(conn)
    text = render_digest(conn, top_n=15, config=_min_config())
    dest = tmp_path / "digests"
    written = write_digest(text, out_dir=dest, timestamp="2026-09-24T14:00:00Z")
    assert written.exists()
    assert (dest / "latest.md").exists()
    assert (dest / "latest.md").read_text(encoding="utf-8") == text


def test_cli_digest_dry_run(tmp_path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "digest",
         "--db", str(db_path), "--dry-run"],
        capture_output=True, text=True, check=True,
    )
    assert "digest:" in r.stdout or "No topics" in r.stdout
