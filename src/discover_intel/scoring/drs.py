"""S3-C Discover Readiness Score — pre-publish gate on drafts."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml

from discover_intel.scoring.drs_components import (
    eeat, headline, image, originality, technical, timeliness,
)

log = logging.getLogger(__name__)


def load_drs_config(scoring_yaml_path: str | Path,
                    clickbait_path: str | Path | None = None) -> dict:
    with open(scoring_yaml_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cb_regexes: list[re.Pattern[str]] = []
    if clickbait_path is None:
        clickbait_path = cfg["drs"]["headline"].get("clickbait_patterns_file",
                                                     "config/clickbait_patterns.txt")
    cb_path = Path(clickbait_path)
    if cb_path.exists():
        for line in cb_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                cb_regexes.append(re.compile(s, re.IGNORECASE))
    cfg["_clickbait_regexes"] = cb_regexes
    return cfg


def _get_nlp():
    import spacy
    try:
        return spacy.load("en_core_web_md")
    except OSError:
        return spacy.load("en_core_web_sm")


def _extract_entity(nlp, title: str) -> str | None:
    doc = nlp(title)
    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG", "GPE", "PRODUCT", "EVENT"}:
            return ent.text
    return None


def _draft_id(draft: dict) -> str:
    if draft.get("url"):
        return draft["url"]
    return hashlib.sha1(draft["title"].encode("utf-8")).hexdigest()


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def score_draft(draft: dict, config: dict, conn: sqlite3.Connection | None,
                nlp: Any) -> dict:
    """Score a single draft. Returns row-shape dict for article_scores + findings."""
    drs_cfg = config["drs"]
    weights = drs_cfg["weights"]
    cb_regexes = config.get("_clickbait_regexes", [])

    title = draft.get("title", "")
    image_width = int(draft.get("image_width", 0) or 0)
    aspect = draft.get("aspect_ratio")
    author = draft.get("author") or ""
    published_at = draft.get("published_at")
    body_text = draft.get("body_text")
    url = draft.get("url")

    entity = _extract_entity(nlp, title)
    entity_lanes: list[str] = []
    if conn is not None and entity is not None:
        rows = conn.execute(
            "SELECT DISTINCT substr(e.taxonomy_id, 6) AS lane_slug "
            "FROM item_entities e "
            "WHERE e.entity = ? AND e.taxonomy_id LIKE 'lane:%'",
            (entity,),
        ).fetchall()
        entity_lanes = [r[0] for r in rows]

    h_score, h_reasons = headline(title, nlp, cb_regexes, drs_cfg["headline"])
    i_score, i_reasons = image(image_width, aspect, url, drs_cfg["image"])
    e_score, e_reasons = eeat(author, published_at, body_text, entity_lanes,
                              drs_cfg["eeat"])
    o_score, o_reasons = originality(title, entity, conn, drs_cfg["originality"])
    t_score, t_reasons = timeliness(entity, conn, drs_cfg["timeliness"])
    tech_score, tech_reasons = technical(url, drs_cfg["technical"])

    drs = 100.0 * (
        weights["headline"] * h_score
        + weights["image"] * i_score
        + weights["eeat"] * e_score
        + weights["originality"] * o_score
        + weights["timeliness"] * t_score
        + weights["technical"] * tech_score
    )

    findings = {
        "headline":    {"value": h_score,    "reasons": h_reasons},
        "image":       {"value": i_score,    "reasons": i_reasons},
        "eeat":        {"value": e_score,    "reasons": e_reasons},
        "originality": {"value": o_score,    "reasons": o_reasons},
        "timeliness":  {"value": t_score,    "reasons": t_reasons},
        "technical":   {"value": tech_score, "reasons": tech_reasons},
        "extracted_entity": entity,
        "entity_lanes": entity_lanes,
    }
    return {
        "scored_at": _iso_now(),
        "draft_id": _draft_id(draft),
        "drs": drs,
        "headline": h_score,
        "image": i_score,
        "eeat": e_score,
        "originality": o_score,
        "timeliness": t_score,
        "technical": tech_score,
        "findings_json": json.dumps(findings, ensure_ascii=False),
    }


def persist_score(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO article_scores "
        "(scored_at, draft_id, drs, headline, image, eeat, originality, "
        "timeliness, technical, findings_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (row["scored_at"], row["draft_id"], row["drs"], row["headline"],
         row["image"], row["eeat"], row["originality"], row["timeliness"],
         row["technical"], row["findings_json"]),
    )
    conn.commit()


def _print_findings(row: dict, gate: float) -> None:
    fs = json.loads(row["findings_json"])
    verdict = "PASS" if row["drs"] >= gate else "FAIL"
    print(f"DRS: {row['drs']:.1f} ({verdict} >={gate})")
    for name in ("headline", "image", "eeat", "originality", "timeliness",
                 "technical"):
        val = fs[name]["value"]
        why = "; ".join(fs[name]["reasons"])
        print(f"  {name:12s} {val:.2f}  ({why})")


def main(args) -> int:
    """CLI entry with two shapes: keyword args or --json."""
    scoring_yaml = Path("config/scoring.yaml")
    if not scoring_yaml.exists():
        print("drs: config/scoring.yaml missing", file=sys.stderr)
        return 2
    cfg = load_drs_config(scoring_yaml)

    if getattr(args, "json", None):
        draft = json.loads(Path(args.json).read_text(encoding="utf-8"))
    else:
        draft = {
            "title": args.title,
            "image_width": args.image_width,
            "author": args.author,
            "published_at": args.published_at,
        }
        if getattr(args, "url", None):
            draft["url"] = args.url
        if getattr(args, "body_file", None):
            body_path = Path(args.body_file)
            if body_path.exists():
                draft["body_text"] = body_path.read_text(encoding="utf-8")

    conn = None
    db_path = getattr(args, "db", None) or "data/warehouse.db"
    if Path(db_path).exists():
        from discover_intel import db as db_mod
        conn = db_mod.connect(db_path)
    else:
        log.info("drs: no warehouse at %s; timeliness+originality use defaults",
                 db_path)

    try:
        nlp = _get_nlp()
        row = score_draft(draft, config=cfg, conn=conn, nlp=nlp)
        if conn is not None:
            persist_score(conn, row)
        _print_findings(row, gate=float(cfg["drs"]["gate"]))
        return 0
    finally:
        if conn is not None:
            conn.close()
