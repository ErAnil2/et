"""S2-C entity/topic tagger — spaCy NER + lane classifier + format inference."""
from __future__ import annotations

import logging
from typing import Any

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
