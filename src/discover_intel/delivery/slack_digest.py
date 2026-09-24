"""S3-D-1 Markdown digest of latest topic_scores."""
from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
import sqlite3
from pathlib import Path

import yaml
from jinja2 import Template

log = logging.getLogger(__name__)


def _template_path() -> Path:
    return Path(__file__).parent / "digest_template.md.j2"


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def render_digest(conn: sqlite3.Connection, top_n: int, config: dict,
                  template_path: Path | None = None,
                  timestamp: str | None = None) -> str:
    """Render top-N publish-threshold topics as Markdown."""
    if template_path is None:
        template_path = _template_path()
    if timestamp is None:
        timestamp = _iso_now()
    tos_cfg = config["tos"]
    publish_t = float(tos_cfg["thresholds"]["publish"])
    patterns = tos_cfg.get("suggested_headline_patterns", {})

    latest_at = conn.execute(
        "SELECT MAX(scored_at) FROM topic_scores"
    ).fetchone()[0]
    topics: list[dict] = []
    if latest_at is not None:
        rows = conn.execute(
            "SELECT entity, tos, suggested_format, evidence_json "
            "FROM topic_scores "
            "WHERE scored_at = ? AND tos >= ? "
            "ORDER BY tos DESC LIMIT ?",
            (latest_at, publish_t, top_n),
        ).fetchall()
        for entity, tos, suggested, ev_json in rows:
            try:
                ev = json.loads(ev_json)
            except (json.JSONDecodeError, TypeError):
                ev = {}
            top_titles = ev.get("top_discover_titles") or []
            top_title = top_titles[0]["title"] if top_titles else None
            top_host = top_titles[0].get("host") if top_titles else None
            headline_pattern = patterns.get(suggested) or patterns.get("default", "")
            topics.append({
                "entity": entity,
                "tos": tos,
                "suggested_format": suggested,
                "top_title": top_title,
                "top_host": top_host,
                "competitor_hosts": ev.get("competitor_hosts") or [],
                "beat_queries": ev.get("beat_queries") or [],
                "headline_pattern": headline_pattern,
            })

    template = Template(template_path.read_text(encoding="utf-8"))
    return template.render(
        timestamp=timestamp,
        publish_threshold=int(publish_t),
        topics=topics,
    )


def write_digest(text: str, out_dir: Path, timestamp: str) -> Path:
    """Write timestamped digest + latest.md copy."""
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = timestamp.replace(":", "").replace(" ", "T")
    dest = out_dir / f"{safe}.md"
    dest.write_text(text, encoding="utf-8")
    latest = out_dir / "latest.md"
    shutil.copyfile(dest, latest)
    return dest


def main(args) -> int:
    from discover_intel import db as db_mod
    scoring_yaml = Path("config/scoring.yaml")
    if not scoring_yaml.exists():
        cfg = {"tos": {"thresholds": {"publish": 60.0, "watchlist": 45.0},
                       "suggested_headline_patterns": {"default": "{entity}: {angle}"}}}
    else:
        with open(scoring_yaml, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)

    conn = db_mod.connect(args.db)
    try:
        ts = _iso_now()
        text = render_digest(conn, top_n=args.top, config=cfg, timestamp=ts)
        if args.dry_run:
            print(text)
            print(f"digest: dry-run rendered {ts}")
            return 0
        out_dir = Path(args.out)
        dest = write_digest(text, out_dir, timestamp=ts)
        n_topics = text.count("\n## ")
        latest_at = conn.execute(
            "SELECT MAX(scored_at) FROM topic_scores"
        ).fetchone()[0]
        rng = "n/a"
        if latest_at:
            row = conn.execute(
                "SELECT MIN(tos), MAX(tos) FROM topic_scores WHERE scored_at = ?",
                (latest_at,),
            ).fetchone()
            if row and row[0] is not None:
                rng = f"{row[0]:.0f}-{row[1]:.0f}"
        print(f"digest: wrote {dest} -- {n_topics} topics, TOS range {rng}")
        return 0
    finally:
        conn.close()
