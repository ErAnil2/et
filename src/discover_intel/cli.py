"""Top-level CLI dispatcher for the discover-intel package."""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from discover_intel import db

SUBCOMMANDS = (
    "init-db", "seed-sources", "feeds", "import-discover", "import-snapshot",
    "gsc", "backup", "vacuum", "db-stats",
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="discover_intel")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="{" + ",".join(SUBCOMMANDS) + "}")

    p_init = sub.add_parser("init-db", help="create the warehouse DB and apply schema")
    p_init.add_argument("--db", required=True, help="path to warehouse.db")

    p_seed = sub.add_parser("seed-sources", help="regenerate sources_*.csv from xlsx")
    p_seed.add_argument("--xlsx", required=True, help="path to USA Top Publishers.xlsx")
    p_seed.add_argument(
        "--config-dir", default="config", help="output directory for the CSVs",
    )

    p_feeds = sub.add_parser("feeds", help="poll sources and populate items/feed_polls")
    p_feeds.add_argument("--db", required=True)
    p_feeds.add_argument("--kind", required=True,
                         help="comma-separated: web,gnews_site,gnews_query,gnews_section,youtube")
    p_feeds.add_argument("--rate-per-sec", type=float, default=5.0, dest="rate_per_sec")
    p_feeds.add_argument("--limit", type=int, default=None)
    p_feeds.add_argument("--dry-run", action="store_true")

    p_imp = sub.add_parser("import-discover",
                           help="import DiscoverTrends CSV / Marfeel XLSX exports")
    p_imp.add_argument("--db", required=True)
    p_imp.add_argument("--file", default=None, help="one-off file path")
    p_imp.add_argument("--watch", action="store_true",
                       help="scan the imports directory once")
    p_imp.add_argument("--imports-dir", default="data/imports/discover",
                       dest="imports_dir")
    p_imp.add_argument("--config-dir", default="config", dest="config_dir")
    p_imp.add_argument("--dry-run", action="store_true")

    p_snap = sub.add_parser("import-snapshot", help="import D2TR-style snapshot paste")
    p_snap.add_argument("--db", required=True)
    p_snap.add_argument("--file", required=True)
    p_snap.add_argument("--taken-at", required=True, dest="taken_at",
                        help="ISO UTC timestamp, e.g. 2026-09-23T15:00:00Z")
    p_snap.add_argument("--market", default="US")
    p_snap.add_argument("--source-kind", default="channel",
                        choices=["channel", "host"], dest="source_kind")

    p_gsc = sub.add_parser("gsc", help="nightly Google Search Console pull (Discover)")
    p_gsc.add_argument("--db", required=True)
    p_gsc.add_argument("--start", default=None)
    p_gsc.add_argument("--end", default=None)
    p_gsc.add_argument("--dry-run", action="store_true")

    p_bk = sub.add_parser("backup", help="online backup of warehouse.db")
    p_bk.add_argument("--db", required=True)
    p_bk.add_argument("--dest-dir", default="data/backups", dest="dest_dir")
    p_bk.add_argument("--force", action="store_true")
    p_bk.add_argument("--keep-dailies", type=int, default=14, dest="keep_dailies")

    p_vc = sub.add_parser("vacuum", help="checkpoint WAL and VACUUM")
    p_vc.add_argument("--db", required=True)
    p_vc.add_argument("--backups-dir", default="data/backups", dest="backups_dir")
    p_vc.add_argument("--force", action="store_true")

    p_stats = sub.add_parser("db-stats", help="print row counts per table")
    p_stats.add_argument("--db", required=True)

    return p


def cmd_db_stats(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    tables = [
        "sources", "items", "feed_polls", "discover_articles",
        "discover_snapshots", "gsc_discover",
    ]
    counts = {}
    for t in tables:
        (n,) = conn.execute(f"SELECT count(*) FROM {t}").fetchone()  # noqa: S608 — hard-coded table names
        counts[t] = n
    conn.close()
    line = " ".join(f"{t}={counts[t]}" for t in tables)
    print(f"db-stats: {line}")
    return 0


def cmd_seed_sources(args: argparse.Namespace) -> int:
    from discover_intel.config import seed_sources_from_xlsx
    counts = seed_sources_from_xlsx(Path(args.xlsx), Path(args.config_dir))
    print(
        f"seed-sources: wrote web={counts['web']} gnews={counts['gnews']} "
        f"youtube={counts['youtube']} into {args.config_dir}"
    )
    return 0


def cmd_init_db(args: argparse.Namespace) -> int:
    path = Path(args.db)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.connect(path)
    db.apply_schema(conn)
    conn.close()
    print(f"init-db: created {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "init-db":
        return cmd_init_db(args)
    if args.cmd == "seed-sources":
        return cmd_seed_sources(args)
    if args.cmd == "feeds":
        from discover_intel.ingest.feeds import main as feeds_main
        return feeds_main(args)
    if args.cmd == "import-discover":
        from discover_intel.ingest.import_discover_file import main as imp_main
        return imp_main(args)
    if args.cmd == "import-snapshot":
        from discover_intel.ingest.import_snapshot import main as snap_main
        return snap_main(args)
    if args.cmd == "gsc":
        from discover_intel.ingest.gsc_discover import main as gsc_main
        return gsc_main(args)
    if args.cmd == "backup":
        from discover_intel.ops.backup import main as bk_main
        return bk_main(args)
    if args.cmd == "vacuum":
        from discover_intel.ops.backup import vacuum_main
        return vacuum_main(args)
    if args.cmd == "db-stats":
        return cmd_db_stats(args)
    print(f"{args.cmd}: not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
