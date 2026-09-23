"""DiscoverTrends CSV / Marfeel XLSX importer with header auto-detection."""
from __future__ import annotations

from pathlib import Path

import yaml


class UnknownFormatError(Exception):
    """Raised when no mapping's header_signature matches the file's header row."""


def load_mappings(config_dir: Path) -> dict:
    path = config_dir / "discover_import_mappings.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def detect_tool(headers: list[str], mappings: dict) -> str:
    """Return the mapping key whose header_signature is a subset of `headers`."""
    hset = {h.strip() for h in headers}
    for tool, m in mappings.items():
        sig = set(m.get("header_signature") or [])
        if sig and sig.issubset(hset):
            return tool
    raise UnknownFormatError(
        f"Unknown export format. Headers seen: {headers}. "
        "Add a mapping in config/discover_import_mappings.yaml."
    )
