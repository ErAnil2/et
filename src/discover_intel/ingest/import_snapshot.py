"""D2TR-style snapshot paste importer (host/channel snapshots)."""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path

from discover_intel.util.time import iso_utc, utc_now

log = logging.getLogger(__name__)


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


def _sniff(path: Path) -> type[csv.Dialect] | csv.Dialect:
    with path.open(encoding="utf-8", newline="") as fh:
        sample = fh.read(4096)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        return csv.excel_tab


def _snapshot_id(taken_at: str, market: str, host_or_channel: str) -> str:
    return hashlib.sha1(
        f"{taken_at}|{market}|{host_or_channel}".encode()
    ).hexdigest()


def import_snapshot(
    conn: sqlite3.Connection,
    source_path: Path,
    taken_at: str,
    market: str = "US",
    source_kind: str = "channel",
) -> dict:
    dialect = _sniff(source_path)
    iso_utc(utc_now())  # (imported_at not used per-row; snapshots pool by taken_at)
    new = 0
    seen = 0
    with source_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, dialect=dialect)
        for row in reader:
            seen += 1
            key = (row.get("channel_id") or row.get("host_or_channel")
                   or row.get("channel_as_listed") or "").strip()
            if not key:
                continue
            sid = _snapshot_id(taken_at, market, key)
            existed = conn.execute(
                "SELECT 1 FROM discover_snapshots WHERE snapshot_id = ?", (sid,)
            ).fetchone()
            if existed:
                continue
            conn.execute(
                "INSERT INTO discover_snapshots ("
                "snapshot_id, taken_at, market, source_kind, host_or_channel, "
                "visibility_2h, posts, time_on_feed_min, tier, category, raw_json"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (sid, taken_at, market, source_kind, key,
                 parse_kmb(row.get("visibility_2h")),
                 int(float(row["posts"])) if row.get("posts") else None,
                 parse_hm(row.get("time_on_feed")),
                 (row.get("tier") or None),
                 (row.get("category") or None),
                 json.dumps(row, ensure_ascii=False)),
            )
            new += 1
    conn.commit()
    print(f"import-snapshot: {source_path.name}, {new} new, {seen - new} dup")
    return {"seen": seen, "new": new}


def main(args) -> int:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if args.file:
            import_snapshot(
                conn, Path(args.file), taken_at=args.taken_at,
                market=args.market, source_kind=args.source_kind,
            )
            return 0
        print("import-snapshot: pass --file X --taken-at ISO", flush=True)
        return 2
    finally:
        conn.close()
