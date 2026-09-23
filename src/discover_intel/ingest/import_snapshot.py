"""D2TR-style snapshot paste importer (host/channel snapshots)."""
from __future__ import annotations

import re


_KMB_RE = re.compile(r"^\s*([0-9.,]+)\s*([KMB]?)\s*$", re.IGNORECASE)
_HM_RE = re.compile(r"^\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*$")


def parse_kmb(s: str | None) -> float | None:
    if s is None:
        return None
    text = str(s).strip()
    if not text:
        return None
    m = _KMB_RE.match(text)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    mul = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[m.group(2).upper()]
    return num * mul


def parse_hm(s: str | None) -> float | None:
    if s is None:
        return None
    text = str(s).strip()
    if not text:
        return None
    m = _HM_RE.match(text)
    if not m or (m.group(1) is None and m.group(2) is None):
        return None
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    return float(hours * 60 + minutes)
