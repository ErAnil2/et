"""S2-C entity/topic tagger — spaCy NER + lane classifier + format inference."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

_ALLOWED_ENT_TYPES = {"PERSON", "ORG", "GPE", "PRODUCT", "EVENT"}


def run_ner(nlp: Any, title: str) -> list[tuple[str, str]]:
    """Return [(entity_text, entity_type), ...] for allowed types only."""
    if not title:
        return []
    doc = nlp(title)
    return [(ent.text.strip(), ent.label_)
            for ent in doc.ents
            if ent.label_ in _ALLOWED_ENT_TYPES and ent.text.strip()]


def run_lanes(title: str, compiled_patterns: dict[str, re.Pattern[str]]) -> list[str]:
    """Return sorted list of matching lane slugs (deduplicated)."""
    if not title:
        return []
    hits = [slug for slug, rx in compiled_patterns.items() if rx.search(title)]
    return sorted(set(hits))


def load_lane_patterns(config_path: Path) -> dict[str, re.Pattern[str]]:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return {slug: re.compile(entry["pattern"], re.IGNORECASE | re.VERBOSE)
            for slug, entry in data.items()}


def run_format(title: str, compiled_rules: list[tuple[str, re.Pattern[str]]]) -> str:
    """First-match-wins. Default 'news' catchall must exist as last rule."""
    for fmt, rx in compiled_rules:
        if rx.search(title):
            return fmt
    return "news"


def load_format_rules(config_path: Path) -> list[tuple[str, re.Pattern[str]]]:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return [(r["format"], re.compile(r["pattern"], re.IGNORECASE | re.VERBOSE))
            for r in data]


def seed_taxonomy(conn, lane_patterns: dict[str, Any],
                  format_rules: list[tuple[str, Any]],
                  lane_labels: dict[str, str]) -> None:
    """Idempotent upsert of taxonomy rows from lane and format configs.

    All lanes seed with in_et_lane=1 — comprehensive tagging.
    Editorial can flip individual slugs to 0 via SQL later.
    """
    for slug in lane_patterns.keys():
        conn.execute(
            "INSERT OR REPLACE INTO taxonomy "
            "(taxonomy_id, kind, label, parent_id, in_et_lane) "
            "VALUES (?, 'lane', ?, NULL, 1)",
            (f"lane:{slug}", lane_labels.get(slug, slug.replace("_", " ").title())),
        )
    for fmt, _ in format_rules:
        conn.execute(
            "INSERT OR REPLACE INTO taxonomy "
            "(taxonomy_id, kind, label, parent_id, in_et_lane) "
            "VALUES (?, 'format', ?, NULL, 1)",
            (f"format:{fmt}", fmt.title()),
        )
    conn.commit()


import datetime as dt
import hashlib
import time as _time

from discover_intel.analysis.normalise import load_aliases, normalise_title


def _entry_id(source_key: str, entity: str, taxonomy_id: str | None) -> str:
    key = f"{source_key}|{entity}|{taxonomy_id or ''}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_lane_labels(config_path: Path) -> dict[str, str]:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return {slug: entry["label"] for slug, entry in data.items()}


def _pick_untagged(conn, source: str, limit: int) -> list[tuple[str, str, str | None]]:
    """Return [(source_key, title, current_format_column), ...] not yet in item_entities."""
    out: list[tuple[str, str, str | None]] = []

    if source in ("items", "both"):
        rows = conn.execute(
            "SELECT i.item_id, i.title FROM items i "
            "WHERE NOT EXISTS (SELECT 1 FROM item_entities e "
            "WHERE e.source_key = 'item:' || i.item_id) "
            "ORDER BY i.first_seen_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out.extend([(f"item:{iid}", title, None) for iid, title in rows])

    if source in ("obs", "both"):
        rows = conn.execute(
            "SELECT o.obs_id, o.title, o.format FROM discover_articles o "
            "WHERE NOT EXISTS (SELECT 1 FROM item_entities e "
            "WHERE e.source_key = 'obs:' || o.obs_id) "
            "ORDER BY o.observed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out.extend([(f"obs:{oid}", title, existing_fmt)
                    for oid, title, existing_fmt in rows])

    return out


def orchestrate(conn, source: str = "both", limit: int = 5000,
                config_dir: Path | None = None, nlp: Any = None,
                use_llm: bool = False, dry_run: bool = False) -> dict[str, int]:
    """Run the full tagger over untagged items and/or observations."""
    t0 = _time.monotonic()

    if config_dir is None:
        config_dir = Path("config")
    lane_patterns = load_lane_patterns(config_dir / "lane_keywords.yaml")
    format_rules = load_format_rules(config_dir / "format_rules.yaml")
    aliases = load_aliases(config_dir / "entity_aliases.csv")
    lane_labels = _load_lane_labels(config_dir / "lane_keywords.yaml")

    seed_taxonomy(conn, lane_patterns, format_rules, lane_labels=lane_labels)

    if nlp is None:
        import spacy
        nlp = spacy.load("en_core_web_md")

    now = _iso_now()
    rows = _pick_untagged(conn, source, limit)

    stats = {"items_tagged": 0, "obs_tagged": 0,
             "ner_entities": 0, "lane_hits": 0, "format_hits": 0, "llm_calls": 0}

    for source_key, title, existing_fmt in rows:
        norm = normalise_title(title, aliases)

        ner_pairs = run_ner(nlp, title)
        for entity, ent_type in ner_pairs:
            eid = _entry_id(source_key, entity, None)
            if not dry_run:
                conn.execute(
                    "INSERT OR IGNORE INTO item_entities "
                    "(entry_id, source_key, entity, entity_type, "
                    "taxonomy_id, confidence, tagged_at) "
                    "VALUES (?, ?, ?, ?, NULL, 1.0, ?)",
                    (eid, source_key, entity, ent_type, now),
                )
            stats["ner_entities"] += 1

        lane_hits = run_lanes(norm, lane_patterns)
        for slug in lane_hits:
            tax_id = f"lane:{slug}"
            eid = _entry_id(source_key, slug, tax_id)
            if not dry_run:
                conn.execute(
                    "INSERT OR IGNORE INTO item_entities "
                    "(entry_id, source_key, entity, entity_type, "
                    "taxonomy_id, confidence, tagged_at) "
                    "VALUES (?, ?, ?, NULL, ?, 1.0, ?)",
                    (eid, source_key, slug, tax_id, now),
                )
            stats["lane_hits"] += 1

        if existing_fmt:
            fmt = existing_fmt
        else:
            fmt = run_format(norm, format_rules)
        tax_id = f"format:{fmt}"
        eid = _entry_id(source_key, fmt, tax_id)
        if not dry_run:
            conn.execute(
                "INSERT OR IGNORE INTO item_entities "
                "(entry_id, source_key, entity, entity_type, "
                "taxonomy_id, confidence, tagged_at) "
                "VALUES (?, ?, ?, NULL, ?, 1.0, ?)",
                (eid, source_key, fmt, tax_id, now),
            )
        stats["format_hits"] += 1

        if source_key.startswith("item:"):
            stats["items_tagged"] += 1
        else:
            stats["obs_tagged"] += 1

    if not dry_run:
        conn.commit()

    elapsed = _time.monotonic() - t0
    line = (
        f"tag-entities: {stats['items_tagged']} items + {stats['obs_tagged']} obs, "
        f"{stats['ner_entities'] + stats['lane_hits'] + stats['format_hits']} entities "
        f"({stats['ner_entities']} NER, {stats['lane_hits']} lanes, "
        f"{stats['format_hits']} formats), {stats['llm_calls']} LLM, "
        f"{elapsed:.1f}s"
    )
    log.info(line)
    print(line)
    return stats


def main(args) -> int:
    """CLI entry: python -m discover_intel tag-entities --db X --source both --limit N."""
    from discover_intel import db as db_mod
    conn = db_mod.connect(args.db)
    try:
        orchestrate(conn, source=args.source, limit=args.limit,
                    use_llm=args.llm, dry_run=args.dry_run)
        return 0
    finally:
        conn.close()


import json

_LLM_CACHE_DIR = Path("data/llm_cache")
_LLM_BUDGET_PER_RUN = 500

try:
    import claude_code_sdk  # type: ignore  # noqa: F401
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False


def _call_claude_sdk(prompt: str) -> dict[str, Any]:
    """Invoke Claude Code SDK for a single classification call.

    Tests patch this function directly to avoid live SDK calls.
    """
    if not _SDK_AVAILABLE:
        raise RuntimeError("claude-code-sdk not installed; pip install -e '.[llm]'")
    import asyncio

    import claude_code_sdk

    async def _run() -> str:
        chunks: list[str] = []
        async for msg in claude_code_sdk.query(prompt=prompt):
            for block in getattr(msg, "content", []) or []:
                text = getattr(block, "text", None)
                if text:
                    chunks.append(text)
        return "".join(chunks)

    raw = asyncio.run(_run())
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON in LLM response: {raw[:200]!r}")
    return json.loads(raw[start:end + 1])


def llm_classify(title: str, lane_slugs: list[str],
                 format_slugs: list[str]) -> dict[str, Any]:
    """Classify a title via Claude Code SDK with on-disk cache."""
    _LLM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha1(title.encode("utf-8")).hexdigest()
    cache_file = _LLM_CACHE_DIR / f"{h}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    prompt = (
        f"You are a news taxonomy classifier. Return JSON only.\n"
        f"Title: {title}\n"
        f"Possible lanes: {', '.join(lane_slugs)}\n"
        f"Possible formats: {', '.join(format_slugs)}\n"
        f'Reply with {{"lanes": [slug...], "format": "slug", '
        f'"entities": [{{"text": "...", "type": "PERSON|ORG|GPE|PRODUCT|EVENT"}}], '
        f'"confidence": 0.0-1.0}}'
    )
    result = _call_claude_sdk(prompt)
    cache_file.write_text(json.dumps(result), encoding="utf-8")
    return result
