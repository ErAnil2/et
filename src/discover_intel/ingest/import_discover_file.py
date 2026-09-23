"""DiscoverTrends CSV / Marfeel XLSX importer with header auto-detection."""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import shutil
import sqlite3
from pathlib import Path

import yaml

from discover_intel.util.time import iso_utc, parse_discovertrends_filename, utc_now

log = logging.getLogger(__name__)


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


def _obs_id(tool: str, market: str, observed_at: str, url: str | None,
            title: str) -> str:
    key = f"{tool}|{market}|{observed_at}|{url or title}"
    return hashlib.sha1(key.encode()).hexdigest()


def _parse_timestamp(mapping: dict, file_path: Path) -> str:
    if mapping.get("timestamp_from") == "filename":
        rx = mapping.get("filename_regex")
        m = re.search(rx, file_path.name) if rx else None
        if not m:
            raise ValueError(
                f"Filename {file_path.name!r} does not match {rx!r}"
            )
        return iso_utc(parse_discovertrends_filename(file_path.name))
    raise ValueError(
        f"Unsupported timestamp_from={mapping.get('timestamp_from')!r} — "
        "this branch is not implemented in Sprint 1."
    )


def _coerce_float(v: object) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def import_file(
    conn: sqlite3.Connection,
    file_path: Path,
    config_dir: Path,
) -> dict:
    """Import one DiscoverTrends CSV into `discover_articles`. Idempotent."""
    mappings = load_mappings(config_dir)

    # utf-8-sig handles the BOM that DiscoverTrends exports include.
    with file_path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        headers = next(reader)
        tool = detect_tool(headers, mappings)
        mapping = mappings[tool]
        observed_at = _parse_timestamp(mapping, file_path)
        market = mapping.get("market", "US")

        col_map = mapping["map"]
        header_idx = {h.strip(): i for i, h in enumerate(headers)}
        imported_at = iso_utc(utc_now())

        new = 0
        seen = 0
        for rank, row in enumerate(reader, start=1):
            if not any(row):
                continue
            seen += 1

            def cell(src_col: str, r=row) -> object:
                idx = header_idx.get(src_col)
                return r[idx] if idx is not None and idx < len(r) else None

            fields: dict[str, object] = {"title": None, "url": None, "host": None,
                                         "visibility": None, "format": None,
                                         "time_on_feed_min": None, "author": None}
            raw: dict[str, object] = {}
            for src_col, dest in col_map.items():
                v = cell(src_col)
                raw[src_col] = v
                if dest in ("visibility", "time_on_feed_min"):
                    fields[dest] = _coerce_float(v)
                else:
                    fields[dest] = (str(v).strip() if v is not None else None)

            title = fields["title"]
            url = fields["url"]
            if not title:
                continue

            oid = _obs_id(tool, market, observed_at, url, title)
            existed = conn.execute(
                "SELECT 1 FROM discover_articles WHERE obs_id = ?", (oid,)
            ).fetchone()
            if existed:
                continue

            conn.execute(
                "INSERT INTO discover_articles ("
                "obs_id, tool, market, observed_at, source_file, imported_at, "
                "title, url, host, visibility, rank, time_on_feed_min, format, "
                "author, raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (oid, tool, market, observed_at, file_path.name, imported_at,
                 title, url, fields["host"], fields["visibility"], rank,
                 fields["time_on_feed_min"], fields["format"], fields["author"],
                 json.dumps(raw, ensure_ascii=False)),
            )
            new += 1

    conn.commit()
    result = {
        "tool": tool, "observed_at": observed_at, "seen": seen, "new": new,
        "source_file": file_path.name,
    }
    log.info(
        "import-discover: %d obs new, %d seen, %s -> observed_at=%s",
        result["new"], result["seen"], result["source_file"], result["observed_at"],
    )
    return result


def _archive_dest(imports_dir: Path, kind: str, file_path: Path) -> Path:
    now = utc_now()
    dest_dir = imports_dir / kind / f"{now.year:04d}-{now.month:02d}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    return dest_dir / f"{file_path.stem}.{stamp}{file_path.suffix}"


def watch_directory(
    conn: sqlite3.Connection,
    imports_dir: Path,
    config_dir: Path,
) -> dict:
    processed = failed = new = 0
    for f in sorted(imports_dir.glob("*.csv")):
        try:
            r = import_file(conn, f, config_dir=config_dir)
            new += r["new"]
            dest = _archive_dest(imports_dir, "processed", f)
            shutil.move(str(f), str(dest))
            processed += 1
        except Exception:  # noqa: BLE001 — per-file safety
            log.exception("import-discover: failed on %s", f.name)
            dest = _archive_dest(imports_dir, "failed", f)
            shutil.move(str(f), str(dest))
            failed += 1
    print(
        f"import-discover: {processed} file(s) processed, {failed} failed, "
        f"{new} new observations"
    )
    return {"files_processed": processed, "files_failed": failed,
            "new_observations": new}


def main(args) -> int:
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    cfg = Path(args.config_dir)
    try:
        if args.file:
            r = import_file(conn, Path(args.file), config_dir=cfg)
            print(
                f"import-discover: {r['source_file']} -> observed_at={r['observed_at']}, "
                f"{r['new']} new, {r['seen']-r['new']} dup"
            )
            return 0
        if args.watch:
            watch_directory(conn, Path(args.imports_dir), config_dir=cfg)
            return 0
        print("import-discover: pass --file X or --watch", flush=True)
        return 2
    finally:
        conn.close()
