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


@pytest.fixture(scope="session")
def spacy_nlp():
    """Load en_core_web_sm for tests (smaller/faster than the runtime _md).
    If not installed, download once via spacy.cli.download."""
    import spacy
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        from spacy.cli.download import download
        download("en_core_web_sm")
        return spacy.load("en_core_web_sm")
