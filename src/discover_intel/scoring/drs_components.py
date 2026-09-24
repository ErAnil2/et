"""Pure functions for the 6 DRS components. Each returns (score, reasons)."""
from __future__ import annotations

import re
import sqlite3
from typing import Any

_NUMBER_RE = re.compile(r"\d")
_ALLOWED_ENT_TYPES = {"PERSON", "ORG", "GPE", "PRODUCT", "EVENT"}


def headline(title: str, nlp: Any, clickbait_regexes: list,
             config: dict) -> tuple[float, list[str]]:
    """Score the headline. 0-1 with reasons list."""
    reasons: list[str] = []
    n = len(title)
    min_c = int(config["min_chars"])
    max_c = int(config["max_chars"])
    if not (min_c <= n <= max_c):
        return 0.0, [f"headline {n} chars outside [{min_c},{max_c}]"]
    reasons.append(f"length {n} chars within [{min_c},{max_c}]")

    for rx in clickbait_regexes:
        if rx.search(title):
            return 0.0, reasons + [f"clickbait pattern hit: {rx.pattern!r}"]
    reasons.append("no clickbait patterns hit")

    if config.get("require_entity_and_fact", True):
        doc = nlp(title)
        ents = [e for e in doc.ents if e.label_ in _ALLOWED_ENT_TYPES]
        has_number = bool(_NUMBER_RE.search(title))
        if not ents:
            return 0.2, reasons + ["no named entity"]
        if not has_number:
            return 0.4, reasons + [f"entity {ents[0].text!r} present but no number"]
        reasons.append(f"entity {ents[0].text!r} + number present")
        return 0.9, reasons

    return 0.8, reasons + ["entity/fact check skipped"]


def image(image_width: int, aspect_ratio: float | None,
          url: str | None, config: dict) -> tuple[float, list[str]]:
    reasons: list[str] = []
    min_w = int(config["min_width_px"])
    if image_width < min_w:
        return 0.0, [f"width {image_width} < {min_w}"]
    reasons.append(f"width {image_width} >= {min_w}")

    if config.get("reject_square_aspect_ratio", True) and aspect_ratio is not None:
        if 0.85 <= aspect_ratio <= 1.15:
            return 0.5, reasons + [f"aspect {aspect_ratio:.2f} looks square (logo?)"]
        reasons.append(f"aspect {aspect_ratio:.2f} not square")

    if url:
        reasons.append("--url given; max-image-preview:large check deferred")
    return 1.0, reasons


def eeat(author: str, published_at: str | None, body_text: str | None,
         entity_lanes: list[str], config: dict) -> tuple[float, list[str]]:
    reasons: list[str] = []
    ymyl = set(config.get("ymyl_lanes", []))
    is_ymyl = bool(set(entity_lanes) & ymyl)
    author_ok = bool(author and author.strip() and author.strip().lower() != "staff")

    if is_ymyl and config.get("require_author_ymyl", True) and not author_ok:
        return 0.0, [f"YMYL lane {list(set(entity_lanes) & ymyl)} requires named author"]

    score = 0.0
    if author_ok:
        score += 0.4
        reasons.append(f"author {author!r} ok")
    else:
        reasons.append("author missing/generic")

    if published_at:
        score += 0.3
        reasons.append(f"date {published_at} present")
    else:
        reasons.append("no published_at")

    if body_text:
        link_count = len(re.findall(r"https?://", body_text))
        if link_count >= 1:
            score += 0.3
            reasons.append(f"body has {link_count} link(s)")
        else:
            reasons.append("body has no external links")
    else:
        reasons.append("no body provided")

    return min(1.0, score), reasons


def originality(title: str, entity: str | None,
                conn: sqlite3.Connection | None,
                config: dict) -> tuple[float, list[str]]:
    if conn is None:
        return 1.0, ["originality: no --db; default 1.0"]
    from rapidfuzz import fuzz
    if entity is None:
        return 1.0, ["originality: no entity extracted; default 1.0"]
    rows = conn.execute(
        "SELECT i.title FROM items i "
        "JOIN item_entities e ON e.source_key = 'item:' || i.item_id "
        "WHERE e.entity = ? "
        "AND i.first_seen_at >= datetime('now', '-48 hours') "
        "LIMIT 200",
        (entity,),
    ).fetchall()
    if not rows:
        return 1.0, ["no competitor titles for entity in last 48h"]
    ratios = [fuzz.token_set_ratio(title, r[0]) / 100.0 for r in rows]
    max_ratio = max(ratios)
    score = max(0.0, 1.0 - max_ratio)
    return score, [f"max fuzzy ratio {max_ratio:.2f} over {len(rows)} competitors"]


def timeliness(entity: str | None, conn: sqlite3.Connection | None,
               config: dict) -> tuple[float, list[str]]:
    if conn is None or entity is None:
        return 0.5, ["timeliness: no --db or entity; default 0.5"]
    row = conn.execute(
        "SELECT tos, scored_at FROM topic_scores "
        "WHERE entity = ? ORDER BY scored_at DESC LIMIT 1",
        (entity,),
    ).fetchone()
    if not row:
        return 0.5, [f"entity {entity!r} not in topic_scores; default 0.5"]
    tos_val = float(row[0])
    floor = float(config["entity_tos_floor"])
    if tos_val < floor:
        return 0.0, [f"entity TOS {tos_val:.1f} < floor {floor}"]
    return 1.0, [f"entity TOS {tos_val:.1f} >= {floor}"]


def technical(url: str | None, config: dict) -> tuple[float, list[str]]:
    if not url:
        return float(config.get("without_url_default", 0.5)), ["no --url given"]
    return 0.75, [f"--url {url} present; deep check deferred"]
