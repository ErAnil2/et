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
