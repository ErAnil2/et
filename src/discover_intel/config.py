"""Source registry: dataclass + CSV loader + xlsx seeder."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

CSV_FILES = ("sources_web.csv", "sources_gnews.csv", "sources_youtube.csv")


@dataclass(frozen=True)
class Source:
    source_id: str
    kind: str          # web|gnews_site|gnews_query|gnews_section|youtube
    market: str        # 'US'
    name: str
    url: str
    host: str | None
    tier: str | None
    category: str | None
    enabled: int
    notes: str | None


def _row_to_source(row: dict[str, str]) -> Source:
    def s(v: str | None) -> str | None:
        return v.strip() if (v is not None and v.strip() != "") else None
    return Source(
        source_id=row["source_id"].strip(),
        kind=row["kind"].strip(),
        market=row["market"].strip(),
        name=row["name"].strip(),
        url=row["url"].strip(),
        host=s(row.get("host")),
        tier=s(row.get("tier")),
        category=s(row.get("category")),
        enabled=int(row.get("enabled") or "1"),
        notes=s(row.get("notes")),
    )


def load_sources(config_dir: Path) -> list[Source]:
    out: list[Source] = []
    for fname in CSV_FILES:
        path = config_dir / fname
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                out.append(_row_to_source(row))
    return out
