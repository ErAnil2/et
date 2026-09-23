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

    # Stubs for the rest — implemented in later tasks. Present here so --help lists them.
    for name in [x for x in SUBCOMMANDS if x != "init-db"]:
        sub.add_parser(name, help=f"(stub) {name} — implemented later")

    return p


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
    print(f"{args.cmd}: not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
