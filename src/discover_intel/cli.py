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

    # Stubs for the rest — implemented in later tasks. Present here so --help lists them.
    wired = {"init-db", "seed-sources", "feeds", "import-discover", "import-snapshot"}
    for name in [x for x in SUBCOMMANDS if x not in wired]:
        sub.add_parser(name, help=f"(stub) {name} — implemented later")

    return p


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
    print(f"{args.cmd}: not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
