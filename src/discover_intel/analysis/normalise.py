"""Title normalisation: lowercase + honorific strip + alias substitution."""
from __future__ import annotations

import csv
import re
from pathlib import Path

_HONORIFICS = ("mr.", "mrs.", "ms.", "dr.", "prof.", "sen.", "rep.", "sgt.", "gen.")


class _CaseInsensitiveDict(dict):
    """dict subclass that lowercases keys for lookup."""

    def __init__(self, base: dict[str, str]):
        super().__init__({k.lower(): v for k, v in base.items()})

    def get(self, key: str, default=None):  # type: ignore[override]
        return super().get(key.lower(), default)

    def __getitem__(self, key: str) -> str:
        return super().__getitem__(key.lower())

    def __contains__(self, key: object) -> bool:  # type: ignore[override]
        if not isinstance(key, str):
            return False
        return super().__contains__(key.lower())


def load_aliases(csv_path: Path) -> _CaseInsensitiveDict:
    """Load config/entity_aliases.csv into a case-insensitive dict."""
    with csv_path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return _CaseInsensitiveDict({r["alias"]: r["canonical"] for r in rows})


def normalise_title(text: str, aliases: dict[str, str]) -> str:
    """Lowercase + strip honorifics + apply aliases with word-boundary safety."""
    s = text.lower().strip()
    for h in _HONORIFICS:
        s = s.replace(h, "").replace(h.rstrip("."), "")
    s = " ".join(s.split())

    for alias in sorted(aliases.keys(), key=len, reverse=True):
        canonical = aliases[alias]
        pattern = r"\b" + re.escape(alias.lower()) + r"\b"
        s = re.sub(pattern, canonical.lower(), s)

    return " ".join(s.split())
