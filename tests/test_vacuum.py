from pathlib import Path

import pytest

from discover_intel.db import apply_schema, connect
from discover_intel.ops.backup import backup_db, vacuum_db


def test_vacuum_refuses_without_todays_backup(tmp_path: Path):
    src = tmp_path / "wh.db"
    apply_schema(connect(src))
    with pytest.raises(RuntimeError):
        vacuum_db(src, backups_dir=tmp_path / "backups", force=False)


def test_vacuum_runs_with_todays_backup(tmp_path: Path):
    src = tmp_path / "wh.db"
    apply_schema(connect(src))
    backups = tmp_path / "backups"
    backup_db(src, backups)
    # Should not raise.
    vacuum_db(src, backups_dir=backups, force=False)


def test_vacuum_force_bypasses_check(tmp_path: Path):
    src = tmp_path / "wh.db"
    apply_schema(connect(src))
    vacuum_db(src, backups_dir=tmp_path / "backups", force=True)
