"""SQLite online backup + retention + VACUUM."""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from pathlib import Path

from discover_intel.util.time import utc_now

log = logging.getLogger(__name__)


def _today_str(ref: dt.date | None = None) -> str:
    return (ref or utc_now().date()).isoformat()


def backup_db(source: Path, dest_dir: Path, force: bool = False) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"warehouse-{_today_str()}.db"
    if dest.exists() and not force:
        return dest
    src_conn = sqlite3.connect(str(source))
    try:
        dst_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return dest


def prune_backups(
    dest_dir: Path,
    keep_dailies: int = 14,
    ref_date: dt.date | None = None,
) -> list[Path]:
    """Keep last N dailies + all Sundays. Return the kept set."""
    ref = ref_date or utc_now().date()
    cutoff = ref - dt.timedelta(days=keep_dailies)
    kept: list[Path] = []
    for p in sorted(dest_dir.glob("warehouse-*.db")):
        try:
            date_str = p.stem.split("warehouse-", 1)[1]
            d = dt.date.fromisoformat(date_str)
        except (IndexError, ValueError):
            kept.append(p)
            continue
        if d > cutoff or d.weekday() == 6:  # Monday=0, Sunday=6
            kept.append(p)
        else:
            p.unlink()
    return kept


def main(args) -> int:
    src = Path(args.db)
    dest_dir = Path(args.dest_dir)
    path = backup_db(src, dest_dir, force=args.force)
    kept = prune_backups(dest_dir, keep_dailies=args.keep_dailies)
    print(
        f"backup: wrote {path.name}; retention keeps {len(kept)} files "
        f"({args.keep_dailies} dailies + weekly Sundays)"
    )
    return 0
