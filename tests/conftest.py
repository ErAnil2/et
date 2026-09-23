"""Shared pytest fixtures."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from discover_intel import db


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """Fresh sqlite DB with schema applied. Physical file so WAL works."""
    c = db.connect(tmp_path / "warehouse.db")
    db.apply_schema(c)
    return c


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def fixtures_dir() -> Path:
    return FIXTURES
