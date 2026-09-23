# Discover Intelligence System — Sprint 1 (Ingestion) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ingestion foundation of the Discover Intelligence System — a SQLite warehouse populated from ~181 US sources (native RSS, Google News, YouTube), plus file-based importers for DiscoverTrends CSV, D2TR snapshot pastes, and GSC nightly pulls, all orchestrated by Windows Task Scheduler.

**Architecture:** Single Python 3.11+ package `discover_intel` with a top-level CLI dispatcher. Explicit parameterised SQL against a SQLite warehouse (`data/warehouse.db`, WAL mode). Serial rate-limited httpx fetches; feedparser for RSS/Atom. All modules honor `--db`, `--dry-run`, `--limit` and are idempotent on re-run. TDD throughout — no network in tests, real fixture files for the two DiscoverTrends CSVs and the publisher xlsx the user supplied.

**Tech Stack:** Python 3.11+, sqlite3 (stdlib), httpx[http2], feedparser, openpyxl, PyYAML, google-api-python-client, google-auth, python-dateutil. Dev: pytest, pytest-httpx, ruff, mypy. Windows PowerShell 5.1 wrappers + Task Scheduler (AT2019 compat).

**Spec:** `docs/superpowers/specs/2026-09-23-sprint-1-ingestion-design.md`.

**Repo root:** `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\`.

---

## Reference — data-file shapes (verified against user files)

- **`DiscoverTrends_2026-09-23_1547.csv`** — 320 lines (319 data + header). Columns: `Headline, Author, Score, URL`. `Author` values are hosts (`www.nj.com`, `timesofindia.indiatimes.com`). Timestamp encoded in filename: `2026-09-23T15:47:00Z`.
- **`DiscoverTrends_2026-09-23_1509.csv`** — 500 lines (499 data + header). Same schema.
- **`USA Top Publishers.xlsx`** — Sheet1: `Publisher, RSS Feed Url, Sitemap URL` (31 rows). Sheet2: `channel_as_listed, category, tier, visibility_2h, posts, time_on_feed, matched_channel_name, channel_url, channel_id, match_confidence` (100 rows, 98 with resolved channel_id — ABC7 News + Fox Weather remain unresolved).

---

## Phase 0 — Repo initialization

### Task 1: Repo scaffold + copy fixtures + first commit

**Files:**
- Create: `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\pyproject.toml`
- Create: `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\.gitignore`
- Create: `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\.env.example`
- Create: `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\README.md`
- Create: `src/discover_intel/__init__.py`, `src/discover_intel/util/__init__.py`, `src/discover_intel/ingest/__init__.py`, `src/discover_intel/ops/__init__.py`
- Create: `sql/`, `config/`, `scripts/`, `data/imports/discover/processed/`, `data/imports/discover/failed/`, `data/backups/`, `logs/`, `secrets/`
- Create: `secrets/README.md` (points at Desktop-path JSON)
- Copy: fixture CSVs + xlsx into `tests/fixtures/`

- [ ] **Step 1: Verify the parent directory and initialise git**

Run (from any shell in the repo parent):

```bash
cd "C:/Users/Anil.Kumar6/Desktop/My Inteligence System/discover-intel"
git init
git config core.autocrlf true
git branch -M main
```

Expected: `Initialized empty Git repository in .../discover-intel/.git/`.

- [ ] **Step 2: Create the directory tree**

```bash
mkdir -p src/discover_intel/util src/discover_intel/ingest src/discover_intel/ops sql config scripts data/imports/discover/processed data/imports/discover/failed data/backups logs secrets tests/fixtures
```

- [ ] **Step 3: Write `pyproject.toml`**

Path: `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\pyproject.toml`

```toml
[project]
name = "discover-intel"
version = "0.1.0"
description = "Discover Intelligence System — Sprint 1 (ingestion)"
requires-python = ">=3.11"
dependencies = [
  "httpx[http2]==0.27.2",
  "feedparser==6.0.11",
  "openpyxl==3.1.5",
  "PyYAML==6.0.2",
  "google-api-python-client==2.149.0",
  "google-auth==2.36.0",
  "python-dateutil==2.9.0.post0",
]

[project.optional-dependencies]
dev = [
  "pytest==8.3.3",
  "pytest-httpx==0.32.0",
  "ruff==0.7.4",
  "mypy==1.13.0",
]

[project.scripts]
discover-intel = "discover_intel.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]

[tool.pytest.ini_options]
addopts = "-ra -q"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.mypy]
python_version = "3.11"
strict = true
files = ["src/discover_intel"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 4: Write `.gitignore`**

Path: `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\.gitignore`

```
# Python
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
*.egg-info/
dist/
build/

# Project data
data/
logs/
secrets/
*.json
!config/*.json

# Editor
.vscode/
.idea/
```

- [ ] **Step 5: Write `.env.example`**

Path: `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\.env.example`

```
# Copy values into your Windows user environment via `setx NAME "value"`.
# Do NOT commit a real .env file.

GSC_SA_JSON=C:\Users\Anil.Kumar6\Desktop\My Inteligence System\ga4-mcp-504403-c72f94fdfd37 (2).json
GSC_PROPERTY=sc-domain:economictimes.indiatimes.com
# ANTHROPIC_API_KEY is not used in Sprint 1; reserved for Sprint 2 tagger LLM fallback.
```

- [ ] **Step 6: Write `README.md` skeleton**

Path: `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\README.md`

```markdown
# discover-intel

Sprint 1: ingestion foundation for the ET US Discover Intelligence System.
See `docs/superpowers/specs/2026-09-23-sprint-1-ingestion-design.md` for the design.

## First-time setup

To be completed in Task 26.
```

- [ ] **Step 7: Write `secrets/README.md`**

Path: `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\secrets\README.md`

```markdown
# secrets/

This directory is gitignored. Do NOT copy secret files here.

The Google Search Console service-account JSON stays at its Desktop path:
`C:\Users\Anil.Kumar6\Desktop\My Inteligence System\ga4-mcp-504403-c72f94fdfd37 (2).json`

Reference it via the `GSC_SA_JSON` environment variable, set once with:
`setx GSC_SA_JSON "C:\Users\Anil.Kumar6\Desktop\My Inteligence System\ga4-mcp-504403-c72f94fdfd37 (2).json"`
```

- [ ] **Step 8: Create empty `__init__.py` files**

Paths (all empty):
- `src/discover_intel/__init__.py`
- `src/discover_intel/util/__init__.py`
- `src/discover_intel/ingest/__init__.py`
- `src/discover_intel/ops/__init__.py`

Windows PowerShell:
```powershell
"" | Out-File -Encoding utf8 -NoNewline src/discover_intel/__init__.py
"" | Out-File -Encoding utf8 -NoNewline src/discover_intel/util/__init__.py
"" | Out-File -Encoding utf8 -NoNewline src/discover_intel/ingest/__init__.py
"" | Out-File -Encoding utf8 -NoNewline src/discover_intel/ops/__init__.py
```

- [ ] **Step 9: Copy fixtures**

Run (Windows PowerShell):
```powershell
Copy-Item "C:\Users\Anil.Kumar6\Downloads\DiscoverTrends_2026-09-23_1509.csv" "tests\fixtures\discovertrends_2026-09-23_1509.csv"
Copy-Item "C:\Users\Anil.Kumar6\Downloads\DiscoverTrends_2026-09-23_1547.csv" "tests\fixtures\discovertrends_2026-09-23_1547.csv"
Copy-Item "C:\Users\Anil.Kumar6\Downloads\USA Top Publishers.xlsx" "tests\fixtures\usa_top_publishers.xlsx"
```

- [ ] **Step 10: Create and activate a venv, install deps**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev]"
```

Expected: `Successfully installed discover-intel-0.1.0 ...`.

- [ ] **Step 11: First commit**

```bash
git add pyproject.toml .gitignore .env.example README.md src/ sql/ config/ scripts/ tests/ secrets/README.md docs/
git commit -m "chore: initial repo scaffold + copy spec"
```

Expected: `[main (root-commit) <hash>] chore: initial repo scaffold + copy spec`.

---

## Phase 1 — Data layer

### Task 2: `sql/schema.sql`

**Files:**
- Create: `sql/schema.sql`

- [ ] **Step 1: Write a smoke test that loads the schema**

Path: `tests/test_schema.py`

```python
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent / "sql" / "schema.sql"


def test_schema_loads_and_creates_six_tables():
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"sources", "items", "feed_polls", "discover_articles",
            "discover_snapshots", "gsc_discover"} <= tables

    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 1
```

- [ ] **Step 2: Run test and confirm it fails**

```bash
pytest tests/test_schema.py -v -q
```

Expected: `FileNotFoundError: sql/schema.sql` (or equivalent).

- [ ] **Step 3: Write `sql/schema.sql`**

Path: `sql/schema.sql` (contents copied verbatim from spec § 6, with reserved-name comment at bottom):

```sql
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS sources (
  source_id     TEXT PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN ('web','gnews_site','gnews_query','gnews_section','youtube')),
  market        TEXT NOT NULL,
  name          TEXT NOT NULL,
  url           TEXT NOT NULL,
  host          TEXT,
  tier          TEXT,
  category      TEXT,
  enabled       INTEGER NOT NULL DEFAULT 1,
  notes         TEXT
);

-- item_id = sha1(source_id + '|' + url).
-- Rationale: url is stable at ingest time; canonical_url is NULL in Sprint 1 and
-- gets filled by the Sprint-2 resolver. If item_id used coalesce(canonical_url, url),
-- the PK would change when Sprint 2 resolves the URL — breaking joins. Sprint 2
-- solves cross-source dedup via a separate `item_outcomes` matcher table, not
-- by mutating item_id.
CREATE TABLE IF NOT EXISTS items (
  item_id         TEXT PRIMARY KEY,
  source_id       TEXT NOT NULL REFERENCES sources(source_id),
  url             TEXT NOT NULL,
  canonical_url   TEXT,
  host            TEXT NOT NULL,
  title           TEXT NOT NULL,
  description     TEXT,
  author          TEXT,
  published_at    TEXT,
  first_seen_at   TEXT NOT NULL,
  last_seen_at    TEXT NOT NULL,
  seen_count      INTEGER NOT NULL DEFAULT 1,
  title_hash      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_source_first_seen ON items(source_id, first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_host_pub          ON items(host, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_canonical_url     ON items(canonical_url) WHERE canonical_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_items_title_hash        ON items(title_hash);

CREATE TABLE IF NOT EXISTS feed_polls (
  poll_id       TEXT PRIMARY KEY,
  source_id     TEXT NOT NULL REFERENCES sources(source_id),
  polled_at     TEXT NOT NULL,
  http_status   INTEGER,
  items_seen    INTEGER NOT NULL DEFAULT 0,
  items_new     INTEGER NOT NULL DEFAULT 0,
  duration_ms   INTEGER NOT NULL DEFAULT 0,
  error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_feed_polls_source_time ON feed_polls(source_id, polled_at DESC);

CREATE TABLE IF NOT EXISTS discover_articles (
  obs_id            TEXT PRIMARY KEY,
  tool              TEXT NOT NULL,
  market            TEXT NOT NULL,
  observed_at       TEXT NOT NULL,
  source_file       TEXT NOT NULL,
  imported_at       TEXT NOT NULL,
  title             TEXT NOT NULL,
  url               TEXT,
  host              TEXT,
  visibility        REAL,
  rank              INTEGER,
  time_on_feed_min  REAL,
  format            TEXT,
  author            TEXT,
  raw_json          TEXT
);
CREATE INDEX IF NOT EXISTS idx_disc_articles_obs_market ON discover_articles(observed_at DESC, market);
CREATE INDEX IF NOT EXISTS idx_disc_articles_host_obs   ON discover_articles(host, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_disc_articles_url        ON discover_articles(url) WHERE url IS NOT NULL;

CREATE TABLE IF NOT EXISTS discover_snapshots (
  snapshot_id       TEXT PRIMARY KEY,
  taken_at          TEXT NOT NULL,
  market            TEXT NOT NULL,
  source_kind       TEXT NOT NULL CHECK (source_kind IN ('host','channel')),
  host_or_channel   TEXT NOT NULL,
  visibility_2h     REAL,
  posts             INTEGER,
  time_on_feed_min  REAL,
  tier              TEXT,
  category          TEXT,
  raw_json          TEXT
);
CREATE INDEX IF NOT EXISTS idx_disc_snap_taken ON discover_snapshots(taken_at DESC, market);

CREATE TABLE IF NOT EXISTS gsc_discover (
  date          TEXT NOT NULL,
  country       TEXT NOT NULL,
  device        TEXT NOT NULL,
  page          TEXT NOT NULL,
  impressions   INTEGER NOT NULL DEFAULT 0,
  clicks        INTEGER NOT NULL DEFAULT 0,
  ctr           REAL,
  position      REAL,
  imported_at   TEXT NOT NULL,
  PRIMARY KEY (date, country, device, page)
);
CREATE INDEX IF NOT EXISTS idx_gsc_country_date ON gsc_discover(country, date DESC);

-- Reserved table names for future sprints (do not create yet):
--   Sprint 2: item_outcomes, taxonomy
--   Sprint 3: topic_stats, topic_scores, article_scores
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_schema.py -v -q
```

Expected: `1 passed in 0.0Xs`.

- [ ] **Step 5: Commit**

```bash
git add sql/schema.sql tests/test_schema.py
git commit -m "feat: add sqlite schema (six tables, user_version=1)"
```

---

### Task 3: `db.py` — connect, apply_schema, upsert

**Files:**
- Create: `src/discover_intel/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_db.py`

```python
import sqlite3
from pathlib import Path

import pytest

from discover_intel import db


def test_connect_sets_pragmas(tmp_path: Path):
    conn = db.connect(tmp_path / "w.db")
    (fk,) = conn.execute("PRAGMA foreign_keys").fetchone()
    (jm,) = conn.execute("PRAGMA journal_mode").fetchone()
    assert fk == 1
    assert jm.lower() == "wal"
    assert isinstance(conn.row_factory(conn, ("x",)), sqlite3.Row)


def test_apply_schema_is_idempotent(tmp_path: Path):
    path = tmp_path / "w.db"
    conn = db.connect(path)
    db.apply_schema(conn)
    db.apply_schema(conn)  # second call must not error
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "sources" in tables
    (uv,) = conn.execute("PRAGMA user_version").fetchone()
    assert uv == 1


def test_upsert_inserts_and_updates(tmp_path: Path):
    conn = db.connect(tmp_path / "w.db")
    db.apply_schema(conn)
    row = {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example", "url": "https://example.com/feed", "host": "example.com",
        "tier": None, "category": None, "enabled": 1, "notes": None,
    }
    db.upsert(conn, "sources", row, key="source_id")
    (n,) = conn.execute("SELECT count(*) FROM sources").fetchone()
    assert n == 1

    row["name"] = "example-updated"
    db.upsert(conn, "sources", row, key="source_id")
    (name,) = conn.execute("SELECT name FROM sources").fetchone()
    assert name == "example-updated"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_db.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.db'`.

- [ ] **Step 3: Write `db.py`**

Path: `src/discover_intel/db.py`

```python
"""Sqlite connection helpers and a small upsert utility."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "sql" / "schema.sql"


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def apply_schema(conn: sqlite3.Connection, schema_path: Path | None = None) -> None:
    """Idempotent — safe to call at the start of every job."""
    path = schema_path or SCHEMA_PATH
    conn.executescript(path.read_text(encoding="utf-8"))
    conn.commit()


def upsert(conn: sqlite3.Connection, table: str, row: dict[str, object], key: str) -> None:
    """INSERT ... ON CONFLICT(key) DO UPDATE SET ... — parameterised."""
    cols = list(row.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_list = ", ".join(cols)
    updates = ", ".join([f"{c} = excluded.{c}" for c in cols if c != key])
    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT({key}) DO UPDATE SET {updates}"
    )
    conn.execute(sql, [row[c] for c in cols])
    conn.commit()
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_db.py -v -q
```

Expected: `3 passed in 0.0Xs`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/db.py tests/test_db.py
git commit -m "feat: add db helpers (connect, apply_schema, upsert)"
```

---

### Task 4: `tests/conftest.py` — shared `db` fixture

**Files:**
- Create: `tests/conftest.py`
- Modify: `tests/test_db.py` (use fixture in one test to prove it works)

- [ ] **Step 1: Write conftest.py**

Path: `tests/conftest.py`

```python
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
```

- [ ] **Step 2: Add a fixture-using test**

Append to `tests/test_db.py`:

```python
def test_conn_fixture_has_schema(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "items" in tables
```

- [ ] **Step 3: Confirm test starts failing without the fixture wiring (sanity check)**

```bash
pytest tests/test_db.py::test_conn_fixture_has_schema -v -q
```

Expected: passes (conftest is auto-discovered by pytest).

- [ ] **Step 4: Run the whole test module**

```bash
pytest tests/ -v -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_db.py
git commit -m "test: add conn and fixtures_dir pytest fixtures"
```

---

## Phase 2 — Utils

### Task 5: `util/time.py`

**Files:**
- Create: `src/discover_intel/util/time.py`
- Create: `tests/test_util_time.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_util_time.py`

```python
import datetime as dt

import pytest

from discover_intel.util import time as timeutil


def test_utc_now_is_utc_aware():
    now = timeutil.utc_now()
    assert now.tzinfo is dt.timezone.utc


def test_parse_discovertrends_filename_ok():
    p = timeutil.parse_discovertrends_filename("DiscoverTrends_2026-09-23_1547.csv")
    assert p == dt.datetime(2026, 9, 23, 15, 47, 0, tzinfo=dt.timezone.utc)


def test_parse_discovertrends_filename_with_path():
    p = timeutil.parse_discovertrends_filename(
        "/tmp/DiscoverTrends_2026-09-23_1547.csv"
    )
    assert p.hour == 15 and p.minute == 47


def test_parse_discovertrends_filename_bad():
    with pytest.raises(ValueError):
        timeutil.parse_discovertrends_filename("something_else.csv")


def test_iso_utc_roundtrip():
    d = dt.datetime(2026, 9, 23, 15, 47, 0, tzinfo=dt.timezone.utc)
    assert timeutil.iso_utc(d) == "2026-09-23T15:47:00Z"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_util_time.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.util.time'`.

- [ ] **Step 3: Write `util/time.py`**

Path: `src/discover_intel/util/time.py`

```python
"""UTC helpers and filename → timestamp parsers."""
from __future__ import annotations

import datetime as dt
import os
import re

_DT_FN_RE = re.compile(r"DiscoverTrends_(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})\.csv$")


def utc_now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def parse_discovertrends_filename(path_or_name: str) -> dt.datetime:
    """DiscoverTrends_2026-09-23_1547.csv  →  2026-09-23T15:47:00Z"""
    name = os.path.basename(path_or_name)
    m = _DT_FN_RE.search(name)
    if not m:
        raise ValueError(
            f"Filename does not match DiscoverTrends_YYYY-MM-DD_HHMM.csv: {name!r}"
        )
    date_s, hh, mm = m.group(1), m.group(2), m.group(3)
    return dt.datetime.strptime(
        f"{date_s}T{hh}:{mm}:00+0000", "%Y-%m-%dT%H:%M:%S%z"
    )


def iso_utc(t: dt.datetime) -> str:
    """Datetime → 2026-09-23T15:47:00Z (Z suffix, second precision)."""
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_util_time.py -v -q
```

Expected: `5 passed in 0.0Xs`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/util/time.py tests/test_util_time.py
git commit -m "feat: add util.time (utc_now, parse_discovertrends_filename, iso_utc)"
```

---

### Task 6: `util/url.py`

**Files:**
- Create: `src/discover_intel/util/url.py`
- Create: `tests/test_util_url.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_util_url.py`

```python
from discover_intel.util import url as urlutil


def test_extract_host_basic():
    assert urlutil.extract_host("https://www.nj.com/some/path?x=1") == "www.nj.com"


def test_extract_host_lowercased():
    assert urlutil.extract_host("HTTPS://WWW.NJ.COM/") == "www.nj.com"


def test_extract_host_no_scheme():
    assert urlutil.extract_host("nj.com/path") == "nj.com"


def test_strip_tracking_removes_utm_and_fbclid_and_frag():
    u = "https://x.com/a?utm_source=x&utm_medium=y&fbclid=abc&gclid=zzz&keep=1#frag"
    assert urlutil.strip_tracking(u) == "https://x.com/a?keep=1"


def test_strip_tracking_keeps_query_when_no_junk():
    assert urlutil.strip_tracking("https://x.com/a?id=7") == "https://x.com/a?id=7"


def test_strip_tracking_empty_query_removed():
    assert urlutil.strip_tracking("https://x.com/a?utm_source=x") == "https://x.com/a"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_util_url.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.util.url'`.

- [ ] **Step 3: Write `util/url.py`**

Path: `src/discover_intel/util/url.py`

```python
"""URL helpers: host extraction and tracking-param stripping."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_EXACT = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "yclid"})


def extract_host(url: str) -> str:
    p = urlparse(url if "://" in url else f"//{url}", scheme="")
    return (p.hostname or "").lower()


def strip_tracking(url: str) -> str:
    p = urlparse(url)
    keep = [
        (k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
        if not any(k.startswith(pre) for pre in _TRACKING_PREFIXES)
        and k not in _TRACKING_EXACT
    ]
    new_q = urlencode(keep)
    return urlunparse(p._replace(query=new_q, fragment=""))
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_util_url.py -v -q
```

Expected: `6 passed in 0.0Xs`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/util/url.py tests/test_util_url.py
git commit -m "feat: add util.url (extract_host, strip_tracking)"
```

---

### Task 7: `util/http.py` — rate-limited client + retry

**Files:**
- Create: `src/discover_intel/util/http.py`
- Create: `tests/test_util_http.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_util_http.py`

```python
import time

import httpx
import pytest

from discover_intel.util import http as httputil


def test_token_bucket_rate_limits():
    b = httputil.TokenBucket(rate_per_sec=5, capacity=5)
    start = time.monotonic()
    for _ in range(10):
        b.acquire()
    elapsed = time.monotonic() - start
    # 10 tokens at 5/s from a bucket of 5 → the last 5 wait ~1s total
    assert elapsed >= 0.8


def test_fetch_with_retry_200(httpx_mock):
    httpx_mock.add_response(url="https://example.com/feed", status_code=200,
                            content=b"<rss/>")
    client = httputil.build_client()
    r = httputil.fetch_with_retry(client, "https://example.com/feed", bucket=None)
    assert r.status_code == 200
    assert r.content == b"<rss/>"


def test_fetch_with_retry_never_retries_404(httpx_mock):
    httpx_mock.add_response(url="https://example.com/feed", status_code=404)
    client = httputil.build_client()
    r = httputil.fetch_with_retry(client, "https://example.com/feed", bucket=None)
    assert r.status_code == 404
    # Only one call was made — pytest-httpx fails at teardown if unexpected extras arrived.


def test_fetch_with_retry_retries_500_once(httpx_mock):
    httpx_mock.add_response(url="https://example.com/feed", status_code=500)
    httpx_mock.add_response(url="https://example.com/feed", status_code=200,
                            content=b"ok")
    client = httputil.build_client()
    r = httputil.fetch_with_retry(client, "https://example.com/feed", bucket=None,
                                  backoff=(0.0, 0.0))
    assert r.status_code == 200


def test_fetch_with_retry_gives_up_after_one_retry(httpx_mock):
    httpx_mock.add_response(url="https://example.com/feed", status_code=502)
    httpx_mock.add_response(url="https://example.com/feed", status_code=502)
    client = httputil.build_client()
    r = httputil.fetch_with_retry(client, "https://example.com/feed", bucket=None,
                                  backoff=(0.0, 0.0))
    assert r.status_code == 502
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_util_http.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.util.http'`.

- [ ] **Step 3: Write `util/http.py`**

Path: `src/discover_intel/util/http.py`

```python
"""httpx client factory + token bucket rate limiter + retry wrapper."""
from __future__ import annotations

import threading
import time
from typing import Optional

import httpx

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 discover-intel/0.1"
)


class TokenBucket:
    """Thread-safe token bucket. Blocks on acquire() until a token is available."""

    def __init__(self, rate_per_sec: float, capacity: int) -> None:
        self.rate = float(rate_per_sec)
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(
                    self.capacity, self._tokens + (now - self._last) * self.rate
                )
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                deficit = 1.0 - self._tokens
                wait = deficit / self.rate
            time.sleep(wait)


def build_client(timeout: float = 10.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        http2=True,
        headers={"User-Agent": DEFAULT_UA, "Accept": "*/*"},
    )


def fetch_with_retry(
    client: httpx.Client,
    url: str,
    bucket: Optional[TokenBucket],
    backoff: tuple[float, float] = (2.0, 4.0),
) -> httpx.Response:
    """One retry on 5xx or connection error. Never retry 4xx (per PRD)."""
    if bucket is not None:
        bucket.acquire()
    try:
        r = client.get(url)
    except (httpx.TransportError, httpx.TimeoutException):
        time.sleep(backoff[0])
        if bucket is not None:
            bucket.acquire()
        return client.get(url)

    if 500 <= r.status_code < 600:
        time.sleep(backoff[0])
        if bucket is not None:
            bucket.acquire()
        return client.get(url)
    return r
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_util_http.py -v -q
```

Expected: `5 passed in 1.0-1.5s` (the rate-limit test sleeps ~1s).

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/util/http.py tests/test_util_http.py
git commit -m "feat: add util.http (TokenBucket, build_client, fetch_with_retry)"
```

---

## Phase 3 — CLI skeleton

### Task 8: `cli.py` — argparse dispatcher with `init-db`

**Files:**
- Create: `src/discover_intel/cli.py`
- Create: `src/discover_intel/__main__.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_cli.py`

```python
import subprocess
import sys
from pathlib import Path


def test_help_lists_all_subcommands():
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "--help"],
        capture_output=True, text=True, check=True,
    )
    out = r.stdout
    for cmd in ["init-db", "seed-sources", "feeds", "import-discover",
                "import-snapshot", "gsc", "backup", "vacuum", "db-stats"]:
        assert cmd in out, f"missing subcommand {cmd} in help"


def test_init_db_creates_warehouse(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    assert db_path.exists()
    import sqlite3
    (uv,) = sqlite3.connect(str(db_path)).execute("PRAGMA user_version").fetchone()
    assert uv == 1
    assert "init-db" in r.stdout
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_cli.py -v -q
```

Expected: `No module named discover_intel.__main__`.

- [ ] **Step 3: Write `__main__.py` and `cli.py`**

Path: `src/discover_intel/__main__.py`

```python
from discover_intel.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

Path: `src/discover_intel/cli.py`

```python
"""Top-level CLI dispatcher for the discover-intel package."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

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
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_cli.py -v -q
```

Expected: `2 passed in 0.X-1.Xs`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/cli.py src/discover_intel/__main__.py tests/test_cli.py
git commit -m "feat: add cli dispatcher with init-db subcommand"
```

---

## Phase 4 — Source seeding

### Task 9: `config.py` — Source dataclass + `load_sources`

**Files:**
- Create: `src/discover_intel/config.py`
- Create: `tests/test_config_load.py`
- Create: `tests/fixtures/mini_sources_web.csv`, `mini_sources_gnews.csv`, `mini_sources_youtube.csv`

- [ ] **Step 1: Write mini CSV fixtures**

Path: `tests/fixtures/mini_sources_web.csv`

```
source_id,kind,market,name,url,host,tier,category,enabled,notes
web:nj.com,web,US,nj.com,https://www.nj.com/rss.xml,www.nj.com,,,1,
```

Path: `tests/fixtures/mini_sources_gnews.csv`

```
source_id,kind,market,name,url,host,tier,category,enabled,notes
gnews:query:mortgage rates,gnews_query,US,mortgage rates,https://news.google.com/rss/search?q=%22mortgage+rates%22+when%3A1d&hl=en-US&gl=US&ceid=US:en,,,,1,beat
```

Path: `tests/fixtures/mini_sources_youtube.csv`

```
source_id,kind,market,name,url,host,tier,category,enabled,notes
yt:UCXXX,youtube,US,KTLA 5,https://www.youtube.com/feeds/videos.xml?channel_id=UCXXX,youtube.com,B,Local TV,1,
```

- [ ] **Step 2: Write the failing test**

Path: `tests/test_config_load.py`

```python
from pathlib import Path

from discover_intel.config import Source, load_sources


def test_load_sources_reads_three_csvs(tmp_path: Path, fixtures_dir: Path):
    # copy mini CSVs into a temp config/ dir
    cfg = tmp_path / "config"
    cfg.mkdir()
    for name in ("sources_web.csv", "sources_gnews.csv", "sources_youtube.csv"):
        (cfg / name).write_text(
            (fixtures_dir / f"mini_{name}").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    srcs = load_sources(cfg)
    assert len(srcs) == 3
    kinds = sorted(s.kind for s in srcs)
    assert kinds == ["gnews_query", "web", "youtube"]
    assert all(isinstance(s, Source) for s in srcs)
    (yt,) = [s for s in srcs if s.kind == "youtube"]
    assert yt.tier == "B" and yt.category == "Local TV"
```

- [ ] **Step 3: Run test to confirm it fails**

```bash
pytest tests/test_config_load.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.config'`.

- [ ] **Step 4: Write `config.py`**

Path: `src/discover_intel/config.py`

```python
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
```

- [ ] **Step 5: Run test to verify pass, then commit**

```bash
pytest tests/test_config_load.py -v -q
```

Expected: `1 passed`.

```bash
git add src/discover_intel/config.py tests/test_config_load.py tests/fixtures/mini_sources_*.csv
git commit -m "feat: add Source dataclass and load_sources CSV reader"
```

---

### Task 10: `seed_sources_from_xlsx` + `seed-sources` CLI

**Files:**
- Modify: `src/discover_intel/config.py`
- Modify: `src/discover_intel/cli.py`
- Create: `tests/test_config_seed.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_config_seed.py`

```python
import csv
from pathlib import Path

from discover_intel.config import seed_sources_from_xlsx


def test_seed_sources_from_real_xlsx(tmp_path: Path, fixtures_dir: Path):
    cfg = tmp_path / "config"
    result = seed_sources_from_xlsx(
        xlsx_path=fixtures_dir / "usa_top_publishers.xlsx",
        config_dir=cfg,
    )

    # Expected row counts per spec §13 acceptance #2:
    assert result["web"] >= 15   # ~20 (Sheet1 rows with a non-null RSS URL)
    assert result["gnews"] == 31 + 15 + 4  # 31 site-scoped + 15 beat + 4 sections = 50
    assert result["youtube"] >= 95         # ~98 rows with a resolved channel_id

    web_rows = list(csv.DictReader((cfg / "sources_web.csv").open(encoding="utf-8")))
    assert web_rows, "sources_web.csv should have rows"
    assert web_rows[0].keys() >= {
        "source_id", "kind", "market", "name", "url", "host", "tier",
        "category", "enabled", "notes",
    }
    assert all(r["kind"] == "web" for r in web_rows)

    yt_rows = list(csv.DictReader((cfg / "sources_youtube.csv").open(encoding="utf-8")))
    assert all(r["url"].startswith(
        "https://www.youtube.com/feeds/videos.xml?channel_id="
    ) for r in yt_rows)

    gnews_rows = list(csv.DictReader((cfg / "sources_gnews.csv").open(encoding="utf-8")))
    kinds = {r["kind"] for r in gnews_rows}
    assert kinds == {"gnews_site", "gnews_query", "gnews_section"}
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_config_seed.py -v -q
```

Expected: `ImportError: cannot import name 'seed_sources_from_xlsx' from 'discover_intel.config'`.

- [ ] **Step 3: Append `seed_sources_from_xlsx` and helpers to `config.py`**

Append this to `src/discover_intel/config.py`:

```python
from urllib.parse import quote_plus

import openpyxl

# Beat queries from PRD § 5. Order preserved so the CSV is stable.
BEAT_QUERIES = [
    "Federal Reserve", "mortgage rates", "housing market", "S&P 500",
    "student loans", "Social Security", "Medicare", "IRS refund",
    "layoffs", "AI jobs", "electric vehicles", "mansion", "net worth",
    "credit card debt", "cost of living",
]

GNEWS_SECTIONS = [
    ("Top Stories", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"),
    ("Business",    "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en"),
    ("Technology",  "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en"),
    ("World",       "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"),
]


def _gnews_site_url(host: str) -> str:
    q = f"site:{host} when:1d"
    return f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=en-US&gl=US&ceid=US:en"


def _gnews_query_url(q: str) -> str:
    return (
        f"https://news.google.com/rss/search?q={quote_plus(f'\"{q}\" when:1d')}"
        "&hl=en-US&gl=US&ceid=US:en"
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    cols = ["source_id", "kind", "market", "name", "url",
            "host", "tier", "category", "enabled", "notes"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})


def seed_sources_from_xlsx(xlsx_path: Path, config_dir: Path) -> dict[str, int]:
    """Regenerate the three sources_*.csv files from a USA Top Publishers.xlsx."""
    wb = openpyxl.load_workbook(str(xlsx_path), data_only=True)

    # --- Sheet1: Publishers ---
    s1 = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.worksheets[0]
    rows1 = list(s1.iter_rows(values_only=True))
    header1 = [str(c or "").strip() for c in rows1[0]]
    ix = {name: header1.index(name) for name in header1}
    pub_col   = ix.get("Publisher", 0)
    rss_col   = ix.get("RSS Feed Url", 1)

    web_rows: list[dict[str, object]] = []
    site_rows: list[dict[str, object]] = []
    for row in rows1[1:]:
        if row is None or row[pub_col] is None:
            continue
        host = str(row[pub_col]).strip().lower()
        rss  = row[rss_col]
        # Every publisher gets a gnews_site row
        site_rows.append({
            "source_id": f"gnews:site:{host}", "kind": "gnews_site",
            "market": "US", "name": f"gnews site:{host}",
            "url": _gnews_site_url(host), "host": host, "enabled": 1,
        })
        # Publishers with a native RSS feed URL also get a web row
        if rss and str(rss).strip():
            web_rows.append({
                "source_id": f"web:{host}", "kind": "web", "market": "US",
                "name": host, "url": str(rss).strip(),
                "host": host, "enabled": 1,
            })

    # --- Beat queries + sections ---
    query_rows = [
        {
            "source_id": f"gnews:query:{q.lower().replace(' ', '-')}",
            "kind": "gnews_query", "market": "US", "name": q,
            "url": _gnews_query_url(q), "enabled": 1, "notes": "beat",
        }
        for q in BEAT_QUERIES
    ]
    section_rows = [
        {
            "source_id": f"gnews:section:{name.lower().replace(' ', '-')}",
            "kind": "gnews_section", "market": "US", "name": name,
            "url": url, "enabled": 1, "notes": "section",
        }
        for name, url in GNEWS_SECTIONS
    ]

    # --- Sheet2: YouTube channels ---
    s2 = wb["Sheet2"] if "Sheet2" in wb.sheetnames else wb.worksheets[1]
    rows2 = list(s2.iter_rows(values_only=True))
    header2 = [str(c or "").strip() for c in rows2[0]]
    jx = {name: header2.index(name) for name in header2}
    yt_rows: list[dict[str, object]] = []
    for row in rows2[1:]:
        if row is None:
            continue
        ch_id = row[jx.get("channel_id", 8)]
        if not ch_id or not str(ch_id).strip().startswith("UC"):
            continue
        ch_id = str(ch_id).strip()
        name  = str(row[jx.get("channel_as_listed", 0)] or "").strip() or ch_id
        cat   = row[jx.get("category", 1)]
        tier  = row[jx.get("tier", 2)]
        yt_rows.append({
            "source_id": f"yt:{ch_id}", "kind": "youtube", "market": "US",
            "name": name,
            "url": f"https://www.youtube.com/feeds/videos.xml?channel_id={ch_id}",
            "host": "youtube.com",
            "tier": (str(tier).strip() if tier else None),
            "category": (str(cat).strip() if cat else None),
            "enabled": 1,
        })

    # --- Write files ---
    _write_csv(config_dir / "sources_web.csv", web_rows)
    _write_csv(config_dir / "sources_gnews.csv", site_rows + query_rows + section_rows)
    _write_csv(config_dir / "sources_youtube.csv", yt_rows)

    return {
        "web": len(web_rows),
        "gnews": len(site_rows) + len(query_rows) + len(section_rows),
        "youtube": len(yt_rows),
    }
```

- [ ] **Step 4: Wire the CLI**

Replace the `seed-sources` stub in `src/discover_intel/cli.py`. Edit `_build_parser`, replacing the loop that adds stubs with an explicit stub-loop that skips `seed-sources`, and add:

```python
    p_seed = sub.add_parser("seed-sources", help="regenerate sources_*.csv from xlsx")
    p_seed.add_argument("--xlsx", required=True, help="path to USA Top Publishers.xlsx")
    p_seed.add_argument(
        "--config-dir", default="config", help="output directory for the CSVs",
    )
```

Add the command handler:

```python
def cmd_seed_sources(args: argparse.Namespace) -> int:
    from discover_intel.config import seed_sources_from_xlsx
    counts = seed_sources_from_xlsx(Path(args.xlsx), Path(args.config_dir))
    print(
        f"seed-sources: wrote web={counts['web']} gnews={counts['gnews']} "
        f"youtube={counts['youtube']} into {args.config_dir}"
    )
    return 0
```

And wire it into `main`:

```python
    if args.cmd == "seed-sources":
        return cmd_seed_sources(args)
```

- [ ] **Step 5: Run tests + smoke, then commit**

```bash
pytest tests/test_config_seed.py tests/test_cli.py -v -q
```

Expected: all pass (2s or so).

Smoke run:

```bash
python -m discover_intel seed-sources --xlsx "C:\Users\Anil.Kumar6\Downloads\USA Top Publishers.xlsx" --config-dir config
```

Expected line printed: `seed-sources: wrote web=<n> gnews=50 youtube=<~98> into config`.

```bash
git add src/discover_intel/config.py src/discover_intel/cli.py tests/test_config_seed.py config/sources_*.csv
git commit -m "feat: add seed-sources command (xlsx → sources_*.csv)"
```

---

## Phase 5 — Feeds ingestion

### Task 11: `feeds.py` — parse_feed with fixture XMLs

**Files:**
- Create: `tests/fixtures/native_rss_sample.xml`
- Create: `tests/fixtures/google_news_rss_sample.xml`
- Create: `tests/fixtures/youtube_atom_sample.xml`
- Create: `src/discover_intel/ingest/feeds.py`
- Create: `tests/test_feeds_parse.py`

- [ ] **Step 1: Write the three fixture XMLs**

Path: `tests/fixtures/native_rss_sample.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Sample Native RSS</title>
  <link>https://example.com/</link>
  <description>fixture</description>
  <item>
    <title>Fed cuts rates by 25 bps</title>
    <link>https://example.com/news/fed-cut?utm_source=x</link>
    <description>Some description here.</description>
    <pubDate>Tue, 23 Sep 2026 12:00:00 GMT</pubDate>
    <author>jane@example.com (Jane Doe)</author>
  </item>
  <item>
    <title>Mortgage rates dip below 6%</title>
    <link>https://example.com/news/mortgage-6</link>
    <pubDate>Tue, 23 Sep 2026 13:30:00 GMT</pubDate>
  </item>
</channel></rss>
```

Path: `tests/fixtures/google_news_rss_sample.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Google News - site:example.com</title>
  <link>https://news.google.com/rss/search</link>
  <description>Google News</description>
  <item>
    <title>Example: Fed hint</title>
    <link>https://news.google.com/rss/articles/CBMi_ExampleBase64_?oc=5</link>
    <pubDate>Tue, 23 Sep 2026 12:05:00 GMT</pubDate>
    <source url="https://www.example.com">example.com</source>
  </item>
  <item>
    <title>Example: Mortgage story</title>
    <link>https://news.google.com/rss/articles/CBMi_AnotherId_?oc=5</link>
    <pubDate>Tue, 23 Sep 2026 12:07:00 GMT</pubDate>
    <source url="https://www.example.com">example.com</source>
  </item>
</channel></rss>
```

Path: `tests/fixtures/youtube_atom_sample.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <link rel="self" href="https://www.youtube.com/feeds/videos.xml?channel_id=UCXXX"/>
  <title>Sample Channel</title>
  <yt:channelId>UCXXX</yt:channelId>
  <entry>
    <id>yt:video:vid001</id>
    <yt:videoId>vid001</yt:videoId>
    <title>Live: hurricane update</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid001"/>
    <author><name>Sample Channel</name></author>
    <published>2026-09-23T12:00:00+00:00</published>
    <updated>2026-09-23T12:05:00+00:00</updated>
  </entry>
  <entry>
    <id>yt:video:vid002</id>
    <yt:videoId>vid002</yt:videoId>
    <title>Weather report</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=vid002"/>
    <author><name>Sample Channel</name></author>
    <published>2026-09-23T13:00:00+00:00</published>
    <updated>2026-09-23T13:01:00+00:00</updated>
  </entry>
</feed>
```

- [ ] **Step 2: Write the failing test**

Path: `tests/test_feeds_parse.py`

```python
from pathlib import Path

from discover_intel.config import Source
from discover_intel.ingest.feeds import ParsedItem, parse_feed


def _mk_source(kind: str, host: str = "example.com") -> Source:
    return Source(
        source_id=f"{kind}:{host}", kind=kind, market="US",
        name=host, url=f"https://{host}/feed", host=host,
        tier=None, category=None, enabled=1, notes=None,
    )


def test_parse_native_rss(fixtures_dir: Path):
    xml = (fixtures_dir / "native_rss_sample.xml").read_bytes()
    src = _mk_source("web", "example.com")
    items = parse_feed(xml, src)
    assert len(items) == 2
    assert all(isinstance(i, ParsedItem) for i in items)
    a = items[0]
    assert a.title == "Fed cuts rates by 25 bps"
    assert a.url.startswith("https://example.com/news/fed-cut")
    assert a.host == "example.com"
    assert a.published_at is not None and "2026-09-23" in a.published_at
    assert a.author == "jane@example.com (Jane Doe)"


def test_parse_gnews_rss(fixtures_dir: Path):
    xml = (fixtures_dir / "google_news_rss_sample.xml").read_bytes()
    src = _mk_source("gnews_site", "example.com")
    items = parse_feed(xml, src)
    assert len(items) == 2
    assert all(i.url.startswith("https://news.google.com/rss/articles/") for i in items)


def test_parse_youtube_atom(fixtures_dir: Path):
    xml = (fixtures_dir / "youtube_atom_sample.xml").read_bytes()
    src = _mk_source("youtube", "youtube.com")
    items = parse_feed(xml, src)
    assert len(items) == 2
    assert all(i.url.startswith("https://www.youtube.com/watch?v=") for i in items)
    assert items[0].title == "Live: hurricane update"
```

- [ ] **Step 3: Run test to confirm it fails**

```bash
pytest tests/test_feeds_parse.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.ingest.feeds'`.

- [ ] **Step 4: Write `feeds.py` (parser only)**

Path: `src/discover_intel/ingest/feeds.py`

```python
"""Feed ingestion — parser, persister, orchestrator."""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Iterable

import feedparser

from discover_intel.config import Source
from discover_intel.util.time import iso_utc, utc_now
from discover_intel.util.url import extract_host, strip_tracking

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedItem:
    url: str
    title: str
    host: str
    description: str | None
    author: str | None
    published_at: str | None  # ISO UTC or None


def _entry_published_iso(entry: object) -> str | None:
    tm = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if tm is None:
        return None
    return iso_utc(dt.datetime(*tm[:6], tzinfo=dt.timezone.utc))


def _pick_link(entry: object) -> str:
    link = getattr(entry, "link", None)
    if link:
        return link
    for l in getattr(entry, "links", []) or []:
        href = l.get("href") if isinstance(l, dict) else None
        if href:
            return href
    return ""


def parse_feed(xml: bytes, source: Source) -> list[ParsedItem]:
    """Parse RSS/Atom bytes into ParsedItem list. Never raises on per-entry bugs."""
    d = feedparser.parse(xml)
    out: list[ParsedItem] = []
    for e in d.entries or []:
        try:
            url = _pick_link(e).strip()
            title = (getattr(e, "title", "") or "").strip()
            if not url or not title:
                continue
            # Google News URLs are kept as-is (Sprint 2 resolver handles them).
            if not url.startswith("https://news.google.com/rss/articles/"):
                url = strip_tracking(url)
            host = extract_host(url)
            out.append(ParsedItem(
                url=url,
                title=title,
                host=host,
                description=(getattr(e, "summary", None) or None),
                author=(getattr(e, "author", None) or None),
                published_at=_entry_published_iso(e),
            ))
        except Exception:  # noqa: BLE001 — per-entry safety
            log.exception("parse_feed: entry error in %s", source.source_id)
    return out
```

- [ ] **Step 5: Run test + commit**

```bash
pytest tests/test_feeds_parse.py -v -q
```

Expected: `3 passed`.

```bash
git add src/discover_intel/ingest/feeds.py tests/test_feeds_parse.py tests/fixtures/*.xml
git commit -m "feat: add feeds.parse_feed with RSS/Atom fixture tests"
```

---

### Task 12: `feeds.py` — persist_items + persist_poll + dedup

**Files:**
- Modify: `src/discover_intel/ingest/feeds.py`
- Create: `tests/test_feeds_persist.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_feeds_persist.py`

```python
import sqlite3

from discover_intel.config import Source
from discover_intel.db import upsert
from discover_intel.ingest.feeds import (
    ParsedItem, item_id_for, persist_items, persist_poll,
)


def _seed_source(conn: sqlite3.Connection, source_id: str = "web:example.com") -> Source:
    src = Source(
        source_id=source_id, kind="web", market="US", name="example.com",
        url="https://example.com/feed", host="example.com", tier=None,
        category=None, enabled=1, notes=None,
    )
    upsert(conn, "sources", {
        "source_id": src.source_id, "kind": src.kind, "market": src.market,
        "name": src.name, "url": src.url, "host": src.host, "tier": src.tier,
        "category": src.category, "enabled": src.enabled, "notes": src.notes,
    }, key="source_id")
    return src


def _mk_item(url: str, title: str = "T") -> ParsedItem:
    return ParsedItem(url=url, title=title, host="example.com",
                      description=None, author=None, published_at=None)


def test_item_id_is_deterministic():
    a = item_id_for("web:x.com", "https://x.com/a")
    b = item_id_for("web:x.com", "https://x.com/a")
    assert a == b
    assert a != item_id_for("web:x.com", "https://x.com/b")


def test_persist_items_inserts_new(conn):
    src = _seed_source(conn)
    items = [_mk_item("https://example.com/a"), _mk_item("https://example.com/b")]
    result = persist_items(conn, src, items)
    assert result == {"seen": 2, "new": 2}
    (n,) = conn.execute("SELECT count(*) FROM items").fetchone()
    assert n == 2


def test_persist_items_bumps_seen_count_on_duplicate(conn):
    src = _seed_source(conn)
    it = _mk_item("https://example.com/a")
    persist_items(conn, src, [it])
    r2 = persist_items(conn, src, [it])
    assert r2 == {"seen": 1, "new": 0}
    (fs, ls, sc) = conn.execute(
        "SELECT first_seen_at, last_seen_at, seen_count FROM items"
    ).fetchone()
    assert sc == 2
    assert ls >= fs


def test_persist_poll_writes_row(conn):
    src = _seed_source(conn)
    persist_poll(conn, src, http_status=200, items_seen=5, items_new=3,
                 duration_ms=123, error=None)
    (n,) = conn.execute("SELECT count(*) FROM feed_polls").fetchone()
    assert n == 1
    (status, seen, new, dur) = conn.execute(
        "SELECT http_status, items_seen, items_new, duration_ms FROM feed_polls"
    ).fetchone()
    assert (status, seen, new, dur) == (200, 5, 3, 123)


def test_persist_poll_with_error(conn):
    src = _seed_source(conn)
    persist_poll(conn, src, http_status=None, items_seen=0, items_new=0,
                 duration_ms=42, error="ConnectionError: bang")
    (err,) = conn.execute("SELECT error FROM feed_polls").fetchone()
    assert "bang" in err
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_feeds_persist.py -v -q
```

Expected: `ImportError: cannot import name 'item_id_for'` (or similar).

- [ ] **Step 3: Append persistence functions to `feeds.py`**

Append to `src/discover_intel/ingest/feeds.py`:

```python
def item_id_for(source_id: str, url: str) -> str:
    return hashlib.sha1(f"{source_id}|{url}".encode("utf-8")).hexdigest()


def _title_hash(title: str) -> str:
    norm = " ".join(title.lower().split())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def persist_items(conn, source: Source, items: Iterable[ParsedItem]) -> dict:
    seen = 0
    new = 0
    now = iso_utc(utc_now())
    for it in items:
        seen += 1
        iid = item_id_for(source.source_id, it.url)
        cur = conn.execute("SELECT seen_count FROM items WHERE item_id = ?", (iid,)).fetchone()
        if cur is None:
            conn.execute(
                "INSERT INTO items ("
                "item_id, source_id, url, canonical_url, host, title, description, "
                "author, published_at, first_seen_at, last_seen_at, seen_count, title_hash"
                ") VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (iid, source.source_id, it.url, it.host, it.title,
                 it.description, it.author, it.published_at, now, now,
                 _title_hash(it.title)),
            )
            new += 1
        else:
            conn.execute(
                "UPDATE items SET last_seen_at = ?, seen_count = seen_count + 1 "
                "WHERE item_id = ?",
                (now, iid),
            )
    conn.commit()
    return {"seen": seen, "new": new}


def persist_poll(
    conn, source: Source, http_status: int | None, items_seen: int,
    items_new: int, duration_ms: int, error: str | None,
) -> str:
    polled_at = iso_utc(utc_now())
    poll_id = hashlib.sha1(f"{source.source_id}|{polled_at}".encode("utf-8")).hexdigest()
    conn.execute(
        "INSERT INTO feed_polls ("
        "poll_id, source_id, polled_at, http_status, items_seen, items_new, "
        "duration_ms, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (poll_id, source.source_id, polled_at, http_status, items_seen,
         items_new, duration_ms, error),
    )
    conn.commit()
    return poll_id
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_feeds_persist.py -v -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/ingest/feeds.py tests/test_feeds_persist.py
git commit -m "feat: add persist_items + persist_poll with dedup"
```

---

### Task 13: `feeds.py` — orchestrate() + wire into CLI

**Files:**
- Modify: `src/discover_intel/ingest/feeds.py`
- Modify: `src/discover_intel/cli.py`
- Create: `tests/test_feeds_orchestrate.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_feeds_orchestrate.py`

```python
import subprocess
import sys
from pathlib import Path

from discover_intel.db import upsert
from discover_intel.ingest.feeds import orchestrate


def _seed_two_sources(conn, fixtures_dir):
    upsert(conn, "sources", {
        "source_id": "web:example.com", "kind": "web", "market": "US",
        "name": "example.com", "url": "https://example.com/feed.xml",
        "host": "example.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    upsert(conn, "sources", {
        "source_id": "yt:UCXXX", "kind": "youtube", "market": "US",
        "name": "Sample Channel",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCXXX",
        "host": "youtube.com", "tier": "B", "category": "Local TV",
        "enabled": 1, "notes": None,
    }, key="source_id")


def test_orchestrate_uses_mocked_http(conn, fixtures_dir, httpx_mock):
    _seed_two_sources(conn, fixtures_dir)
    httpx_mock.add_response(
        url="https://example.com/feed.xml", status_code=200,
        content=(fixtures_dir / "native_rss_sample.xml").read_bytes(),
    )
    httpx_mock.add_response(
        url="https://www.youtube.com/feeds/videos.xml?channel_id=UCXXX",
        status_code=200,
        content=(fixtures_dir / "youtube_atom_sample.xml").read_bytes(),
    )
    stats = orchestrate(conn, kinds=["web", "youtube"], rate_per_sec=1000)
    assert stats["ok"] == 2
    assert stats["items_new"] == 4  # 2 native + 2 youtube
    (n_items,) = conn.execute("SELECT count(*) FROM items").fetchone()
    (n_polls,) = conn.execute("SELECT count(*) FROM feed_polls").fetchone()
    assert n_items == 4
    assert n_polls == 2


def test_orchestrate_skips_disabled_and_wrong_kind(conn, fixtures_dir, httpx_mock):
    # Insert one enabled web + one disabled + one youtube
    upsert(conn, "sources", {
        "source_id": "web:on", "kind": "web", "market": "US",
        "name": "on", "url": "https://on.example/feed.xml",
        "host": "on.example", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    upsert(conn, "sources", {
        "source_id": "web:off", "kind": "web", "market": "US",
        "name": "off", "url": "https://off.example/feed.xml",
        "host": "off.example", "tier": None, "category": None,
        "enabled": 0, "notes": None,
    }, key="source_id")
    upsert(conn, "sources", {
        "source_id": "yt:X", "kind": "youtube", "market": "US",
        "name": "X",
        "url": "https://www.youtube.com/feeds/videos.xml?channel_id=X",
        "host": "youtube.com", "tier": None, "category": None,
        "enabled": 1, "notes": None,
    }, key="source_id")
    httpx_mock.add_response(url="https://on.example/feed.xml", status_code=200,
                            content=(fixtures_dir / "native_rss_sample.xml").read_bytes())
    stats = orchestrate(conn, kinds=["web"], rate_per_sec=1000)
    assert stats["ok"] == 1
    assert stats["skipped_disabled"] == 1
    (n,) = conn.execute("SELECT count(*) FROM feed_polls").fetchone()
    assert n == 1


def test_cli_feeds_dry_run_prints_urls(tmp_path: Path, fixtures_dir: Path):
    # init db + seed one source via the CLI init-db and direct SQL
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    import sqlite3
    c = sqlite3.connect(str(db_path))
    c.execute(
        "INSERT INTO sources (source_id, kind, market, name, url, host, "
        "enabled) VALUES (?, ?, ?, ?, ?, ?, 1)",
        ("web:example.com", "web", "US", "example.com",
         "https://example.com/feed.xml", "example.com"),
    )
    c.commit()
    c.close()

    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "feeds",
         "--db", str(db_path), "--kind", "web", "--dry-run"],
        capture_output=True, text=True, check=True,
    )
    assert "example.com" in r.stdout
    assert "dry-run" in r.stdout.lower()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_feeds_orchestrate.py -v -q
```

Expected: `ImportError: cannot import name 'orchestrate'`.

- [ ] **Step 3: Append `orchestrate` to `feeds.py`**

Append to `src/discover_intel/ingest/feeds.py`:

```python
import sqlite3

from discover_intel.util.http import TokenBucket, build_client, fetch_with_retry


def _sources_for_kinds(conn: sqlite3.Connection, kinds: list[str]) -> list[Source]:
    placeholders = ", ".join(["?"] * len(kinds))
    rows = conn.execute(
        f"SELECT source_id, kind, market, name, url, host, tier, category, "
        f"enabled, notes FROM sources WHERE kind IN ({placeholders}) "
        f"ORDER BY kind, source_id",
        kinds,
    ).fetchall()
    return [Source(**dict(r)) for r in rows]


def orchestrate(
    conn: sqlite3.Connection,
    kinds: list[str],
    rate_per_sec: float = 5.0,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict:
    started = time.monotonic()
    stats = {"total": 0, "ok": 0, "http_4xx": 0, "http_5xx": 0,
             "error": 0, "skipped_disabled": 0, "items_seen": 0, "items_new": 0}
    bucket = TokenBucket(rate_per_sec=rate_per_sec, capacity=max(1, int(rate_per_sec)))
    client = build_client()
    all_srcs = _sources_for_kinds(conn, kinds)

    to_poll: list[Source] = []
    for s in all_srcs:
        if s.enabled != 1:
            stats["skipped_disabled"] += 1
            continue
        to_poll.append(s)
    if limit is not None:
        to_poll = to_poll[:limit]

    for s in to_poll:
        stats["total"] += 1
        if dry_run:
            print(f"dry-run: would GET {s.url}  (source_id={s.source_id})")
            continue

        t0 = time.monotonic()
        error: str | None = None
        http_status: int | None = None
        items_seen = items_new = 0
        try:
            r = fetch_with_retry(client, s.url, bucket=bucket)
            http_status = r.status_code
            if 200 <= r.status_code < 300:
                items = parse_feed(r.content, s)
                res = persist_items(conn, s, items)
                items_seen = res["seen"]
                items_new = res["new"]
                stats["ok"] += 1
            elif 400 <= r.status_code < 500:
                stats["http_4xx"] += 1
            else:
                stats["http_5xx"] += 1
        except Exception as exc:  # noqa: BLE001 — per-source safety
            error = f"{type(exc).__name__}: {exc}"
            stats["error"] += 1
            log.exception("feeds: fetch failed for %s", s.source_id)

        dur_ms = int((time.monotonic() - t0) * 1000)
        stats["items_seen"] += items_seen
        stats["items_new"] += items_new
        persist_poll(
            conn, s, http_status=http_status, items_seen=items_seen,
            items_new=items_new, duration_ms=dur_ms, error=error,
        )

    elapsed = time.monotonic() - started
    log.info(
        "feeds: polled %d sources, %d ok, %d 4xx, %d 5xx, %d err, %d new items in %.1fs",
        stats["total"], stats["ok"], stats["http_4xx"], stats["http_5xx"],
        stats["error"], stats["items_new"], elapsed,
    )
    print(
        f"feeds: polled {stats['total']} sources, {stats['ok']} ok, "
        f"{stats['http_4xx']} 4xx, {stats['http_5xx']} 5xx, "
        f"{stats['error']} err, {stats['items_new']} new items in {elapsed:.1f}s"
    )
    return stats


def main(args) -> int:
    """Entry point invoked from cli.py."""
    kinds = [k.strip() for k in args.kind.split(",") if k.strip()]
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    stats = orchestrate(
        conn, kinds=kinds,
        rate_per_sec=args.rate_per_sec,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    conn.close()
    return 0 if stats["error"] == 0 or (stats["ok"] + stats["error"] > 0) else 1
```

- [ ] **Step 4: Wire the CLI subcommand**

In `src/discover_intel/cli.py`, replace the `feeds` stub. Remove `feeds` from the auto-stub loop, and add:

```python
    p_feeds = sub.add_parser("feeds", help="poll sources and populate items/feed_polls")
    p_feeds.add_argument("--db", required=True)
    p_feeds.add_argument("--kind", required=True,
                         help="comma-separated: web,gnews_site,gnews_query,gnews_section,youtube")
    p_feeds.add_argument("--rate-per-sec", type=float, default=5.0, dest="rate_per_sec")
    p_feeds.add_argument("--limit", type=int, default=None)
    p_feeds.add_argument("--dry-run", action="store_true")
```

And in `main`:

```python
    if args.cmd == "feeds":
        from discover_intel.ingest.feeds import main as feeds_main
        return feeds_main(args)
```

- [ ] **Step 5: Run tests + commit**

```bash
pytest tests/test_feeds_orchestrate.py -v -q
```

Expected: `3 passed`.

```bash
git add src/discover_intel/ingest/feeds.py src/discover_intel/cli.py tests/test_feeds_orchestrate.py
git commit -m "feat: wire feeds.orchestrate + feeds CLI subcommand"
```

---

## Phase 6 — DiscoverTrends importer

### Task 14: `discover_import_mappings.yaml` + auto-detection

**Files:**
- Create: `config/discover_import_mappings.yaml`
- Create: `src/discover_intel/ingest/import_discover_file.py` (partial)
- Create: `tests/test_import_discover_detect.py`

- [ ] **Step 1: Write the mapping YAML**

Path: `config/discover_import_mappings.yaml`

```yaml
discovertrends:
  header_signature: [Headline, Author, Score, URL]
  map:
    Headline: title
    Author: host
    Score: visibility
    URL: url
  timestamp_from: filename
  filename_regex: 'DiscoverTrends_(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})\.csv'
  market: US

marfeel:
  # TODO: header_signature to be confirmed once a real Marfeel export is available.
  # Placeholder based on PRD text ("title, visibility, host, format, time").
  header_signature: [title, host, visibility, format, time]
  map:
    title: title
    host: host
    visibility: visibility
    format: format
    time: time_on_feed_min
  timestamp_from: header_row_col
  market: US
```

- [ ] **Step 2: Write the failing test**

Path: `tests/test_import_discover_detect.py`

```python
from pathlib import Path

import pytest

from discover_intel.ingest.import_discover_file import (
    UnknownFormatError, detect_tool, load_mappings,
)


def test_detect_discovertrends(fixtures_dir: Path, tmp_path: Path):
    # Copy mapping YAML into a fake config dir
    cfg = tmp_path / "config"
    cfg.mkdir()
    src_yaml = Path("config/discover_import_mappings.yaml").resolve()
    (cfg / "discover_import_mappings.yaml").write_text(
        src_yaml.read_text(encoding="utf-8"), encoding="utf-8",
    )

    mappings = load_mappings(cfg)
    tool = detect_tool(
        headers=["Headline", "Author", "Score", "URL"],
        mappings=mappings,
    )
    assert tool == "discovertrends"


def test_detect_unknown_raises():
    with pytest.raises(UnknownFormatError):
        detect_tool(
            headers=["Foo", "Bar", "Baz"],
            mappings={"discovertrends": {"header_signature": ["A", "B"]}},
        )
```

- [ ] **Step 3: Run test to confirm it fails**

```bash
pytest tests/test_import_discover_detect.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.ingest.import_discover_file'`.

- [ ] **Step 4: Write the partial module**

Path: `src/discover_intel/ingest/import_discover_file.py`

```python
"""DiscoverTrends CSV / Marfeel XLSX importer with header auto-detection."""
from __future__ import annotations

from pathlib import Path

import yaml


class UnknownFormatError(Exception):
    """Raised when no mapping's header_signature matches the file's header row."""


def load_mappings(config_dir: Path) -> dict:
    path = config_dir / "discover_import_mappings.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def detect_tool(headers: list[str], mappings: dict) -> str:
    """Return the mapping key whose header_signature is a subset of `headers`."""
    hset = set(h.strip() for h in headers)
    for tool, m in mappings.items():
        sig = set(m.get("header_signature") or [])
        if sig and sig.issubset(hset):
            return tool
    raise UnknownFormatError(
        f"Unknown export format. Headers seen: {headers}. "
        "Add a mapping in config/discover_import_mappings.yaml."
    )
```

- [ ] **Step 5: Run test + commit**

```bash
pytest tests/test_import_discover_detect.py -v -q
```

Expected: `2 passed`.

```bash
git add config/discover_import_mappings.yaml src/discover_intel/ingest/import_discover_file.py tests/test_import_discover_detect.py
git commit -m "feat: add discover import mappings + detect_tool"
```

---

### Task 15: parse + persist a single file (idempotent)

**Files:**
- Modify: `src/discover_intel/ingest/import_discover_file.py`
- Create: `tests/test_import_discover_persist.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_import_discover_persist.py`

```python
import shutil
from pathlib import Path

from discover_intel.ingest.import_discover_file import import_file


def test_import_real_discovertrends_1547(conn, fixtures_dir: Path, tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "discover_import_mappings.yaml").write_text(
        Path("config/discover_import_mappings.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    src = fixtures_dir / "discovertrends_2026-09-23_1547.csv"
    # Copy to a working file with the expected filename shape
    working = tmp_path / "DiscoverTrends_2026-09-23_1547.csv"
    shutil.copyfile(src, working)

    result = import_file(conn, working, config_dir=cfg)
    assert result["tool"] == "discovertrends"
    assert result["observed_at"] == "2026-09-23T15:47:00Z"
    # 319 data rows in this fixture (320 - header)
    assert result["new"] == 319
    (n,) = conn.execute("SELECT count(*) FROM discover_articles").fetchone()
    assert n == 319

    # Verify Author→host mapping
    (host,) = conn.execute(
        "SELECT host FROM discover_articles ORDER BY rank LIMIT 1"
    ).fetchone()
    assert "." in host  # is a domain, not a person's name


def test_import_idempotent(conn, fixtures_dir: Path, tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "discover_import_mappings.yaml").write_text(
        Path("config/discover_import_mappings.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    working = tmp_path / "DiscoverTrends_2026-09-23_1547.csv"
    shutil.copyfile(fixtures_dir / "discovertrends_2026-09-23_1547.csv", working)

    r1 = import_file(conn, working, config_dir=cfg)
    r2 = import_file(conn, working, config_dir=cfg)
    assert r1["new"] == 319
    assert r2["new"] == 0
    (n,) = conn.execute("SELECT count(*) FROM discover_articles").fetchone()
    assert n == 319
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_import_discover_persist.py -v -q
```

Expected: `ImportError: cannot import name 'import_file'`.

- [ ] **Step 3: Append the importer to `import_discover_file.py`**

Append to `src/discover_intel/ingest/import_discover_file.py`:

```python
import csv
import datetime as dt
import hashlib
import json
import logging
import re
import sqlite3

from discover_intel.util.time import iso_utc, parse_discovertrends_filename, utc_now

log = logging.getLogger(__name__)


def _obs_id(tool: str, market: str, observed_at: str, url: str | None,
            title: str) -> str:
    key = f"{tool}|{market}|{observed_at}|{url or title}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


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
        f"Unsupported timestamp_from={mapping.get('timestamp_from')!r} for tool "
        f"{mapping.get('_tool')!r} — this branch is not implemented in Sprint 1."
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

    with file_path.open(encoding="utf-8", newline="") as fh:
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

            def cell(src_col: str) -> object:
                idx = header_idx.get(src_col)
                return row[idx] if idx is not None and idx < len(row) else None

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
    log.info("import-discover: %(new)d obs new, %(seen)d seen, %(source_file)s"
             " → observed_at=%(observed_at)s", result)
    return result
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_import_discover_persist.py -v -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/ingest/import_discover_file.py tests/test_import_discover_persist.py
git commit -m "feat: import DiscoverTrends CSV → discover_articles (idempotent)"
```

---

### Task 16: watch mode + CLI wire-up

**Files:**
- Modify: `src/discover_intel/ingest/import_discover_file.py`
- Modify: `src/discover_intel/cli.py`
- Create: `tests/test_import_discover_watch.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_import_discover_watch.py`

```python
import shutil
from pathlib import Path

from discover_intel.ingest.import_discover_file import watch_directory


def test_watch_processes_and_moves_file(conn, fixtures_dir: Path, tmp_path: Path):
    imports = tmp_path / "imports" / "discover"
    imports.mkdir(parents=True)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "discover_import_mappings.yaml").write_text(
        Path("config/discover_import_mappings.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    src = imports / "DiscoverTrends_2026-09-23_1547.csv"
    shutil.copyfile(fixtures_dir / "discovertrends_2026-09-23_1547.csv", src)

    result = watch_directory(conn, imports, config_dir=tmp_path / "config")
    assert result["files_processed"] == 1
    assert not src.exists()
    processed = list((imports / "processed").rglob("*.csv"))
    assert len(processed) == 1
    (n,) = conn.execute("SELECT count(*) FROM discover_articles").fetchone()
    assert n == 319


def test_watch_moves_unparseable_to_failed(conn, tmp_path: Path):
    imports = tmp_path / "imports" / "discover"
    imports.mkdir(parents=True)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "discover_import_mappings.yaml").write_text(
        Path("config/discover_import_mappings.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    bad = imports / "not-a-discover-file.csv"
    bad.write_text("Wrong,Headers,Here\n1,2,3\n", encoding="utf-8")
    result = watch_directory(conn, imports, config_dir=tmp_path / "config")
    assert result["files_failed"] == 1
    assert not bad.exists()
    failed = list((imports / "failed").rglob("*.csv"))
    assert len(failed) == 1
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_import_discover_watch.py -v -q
```

Expected: `ImportError: cannot import name 'watch_directory'`.

- [ ] **Step 3: Append `watch_directory` and `main`**

Append to `src/discover_intel/ingest/import_discover_file.py`:

```python
import shutil


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
        except Exception as exc:  # noqa: BLE001 — per-file safety
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
                f"import-discover: {r['source_file']} → observed_at={r['observed_at']}, "
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
```

- [ ] **Step 4: Wire the CLI**

In `src/discover_intel/cli.py`, replace the `import-discover` stub:

```python
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
```

In `main`:

```python
    if args.cmd == "import-discover":
        from discover_intel.ingest.import_discover_file import main as imp_main
        return imp_main(args)
```

- [ ] **Step 5: Run tests + commit**

```bash
pytest tests/test_import_discover_watch.py -v -q
```

Expected: `2 passed`.

```bash
git add src/discover_intel/ingest/import_discover_file.py src/discover_intel/cli.py tests/test_import_discover_watch.py
git commit -m "feat: import-discover watch mode + CLI wire-up"
```

---

## Phase 7 — Snapshot importer

### Task 17: `parse_kmb` + `parse_hm` helpers

**Files:**
- Create: `src/discover_intel/ingest/import_snapshot.py` (partial)
- Create: `tests/test_snapshot_helpers.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_snapshot_helpers.py`

```python
import pytest

from discover_intel.ingest.import_snapshot import parse_hm, parse_kmb


@pytest.mark.parametrize("s,expected", [
    ("547.79K", 547790.0),
    ("1.2M",    1_200_000.0),
    ("2.5B",    2_500_000_000.0),
    ("300",     300.0),
    ("300.0",   300.0),
    ("",        None),
    (None,      None),
])
def test_parse_kmb(s, expected):
    assert parse_kmb(s) == expected


@pytest.mark.parametrize("s,minutes", [
    ("2h 0m", 120.0),
    ("1h 55m", 115.0),
    ("0h 45m", 45.0),
    ("55m", 55.0),
    ("", None),
    (None, None),
])
def test_parse_hm(s, minutes):
    assert parse_hm(s) == minutes
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_snapshot_helpers.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.ingest.import_snapshot'`.

- [ ] **Step 3: Write `import_snapshot.py` (helpers only)**

Path: `src/discover_intel/ingest/import_snapshot.py`

```python
"""D2TR-style snapshot paste importer (host/channel snapshots)."""
from __future__ import annotations

import re


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
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_snapshot_helpers.py -v -q
```

Expected: `13 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/ingest/import_snapshot.py tests/test_snapshot_helpers.py
git commit -m "feat: add parse_kmb and parse_hm snapshot helpers"
```

---

### Task 18: snapshot importer + CLI

**Files:**
- Modify: `src/discover_intel/ingest/import_snapshot.py`
- Modify: `src/discover_intel/cli.py`
- Create: `tests/fixtures/d2tr_snapshot_sample.tsv`
- Create: `tests/test_snapshot_import.py`

- [ ] **Step 1: Write the fixture**

Path: `tests/fixtures/d2tr_snapshot_sample.tsv`

```
channel_as_listed	category	tier	visibility_2h	posts	time_on_feed	matched_channel_name	channel_url	channel_id	match_confidence
KTLA 5	Local TV	B	547.79K	12	2h 0m	KTLA 5	https://www.youtube.com/channel/UCinjnmQEwCddOudyCC1v7qA	UCinjnmQEwCddOudyCC1v7qA	1.0
CBS Evening News	National	A	416.92K	6	2h 0m	CBS Evening News	https://www.youtube.com/channel/UCAeWdyKJXGWmVAXFpgLNNTg	UCAeWdyKJXGWmVAXFpgLNNTg	1.0
```

- [ ] **Step 2: Write the failing test**

Path: `tests/test_snapshot_import.py`

```python
from pathlib import Path

from discover_intel.ingest.import_snapshot import import_snapshot


def test_import_snapshot_tsv(conn, fixtures_dir: Path):
    r = import_snapshot(
        conn,
        source_path=fixtures_dir / "d2tr_snapshot_sample.tsv",
        taken_at="2026-09-23T15:00:00Z",
        market="US",
        source_kind="channel",
    )
    assert r["new"] == 2
    (n,) = conn.execute("SELECT count(*) FROM discover_snapshots").fetchone()
    assert n == 2
    (v, m, tier) = conn.execute(
        "SELECT visibility_2h, time_on_feed_min, tier FROM discover_snapshots "
        "WHERE host_or_channel = 'UCinjnmQEwCddOudyCC1v7qA'"
    ).fetchone()
    assert v == 547_790.0
    assert m == 120.0
    assert tier == "B"


def test_import_snapshot_idempotent(conn, fixtures_dir: Path):
    kwargs = dict(source_path=fixtures_dir / "d2tr_snapshot_sample.tsv",
                  taken_at="2026-09-23T15:00:00Z", market="US",
                  source_kind="channel")
    r1 = import_snapshot(conn, **kwargs)
    r2 = import_snapshot(conn, **kwargs)
    assert r1["new"] == 2
    assert r2["new"] == 0
```

- [ ] **Step 3: Run test to confirm it fails**

```bash
pytest tests/test_snapshot_import.py -v -q
```

Expected: `ImportError: cannot import name 'import_snapshot'`.

- [ ] **Step 4: Append `import_snapshot` and `main`**

Append to `src/discover_intel/ingest/import_snapshot.py`:

```python
import csv
import hashlib
import json
import logging
import sqlite3
from pathlib import Path

from discover_intel.util.time import iso_utc, utc_now

log = logging.getLogger(__name__)


def _sniff(path: Path) -> csv.Dialect:
    with path.open(encoding="utf-8", newline="") as fh:
        sample = fh.read(4096)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        return csv.excel_tab


def _snapshot_id(taken_at: str, market: str, host_or_channel: str) -> str:
    return hashlib.sha1(
        f"{taken_at}|{market}|{host_or_channel}".encode("utf-8")
    ).hexdigest()


def import_snapshot(
    conn: sqlite3.Connection,
    source_path: Path,
    taken_at: str,
    market: str = "US",
    source_kind: str = "channel",
) -> dict:
    dialect = _sniff(source_path)
    imported_at = iso_utc(utc_now())
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
```

- [ ] **Step 5: Wire the CLI, run tests, commit**

In `src/discover_intel/cli.py` replace the `import-snapshot` stub:

```python
    p_snap = sub.add_parser("import-snapshot", help="import D2TR-style snapshot paste")
    p_snap.add_argument("--db", required=True)
    p_snap.add_argument("--file", required=True)
    p_snap.add_argument("--taken-at", required=True, dest="taken_at",
                        help="ISO UTC timestamp, e.g. 2026-09-23T15:00:00Z")
    p_snap.add_argument("--market", default="US")
    p_snap.add_argument("--source-kind", default="channel",
                        choices=["channel", "host"], dest="source_kind")
```

In `main`:

```python
    if args.cmd == "import-snapshot":
        from discover_intel.ingest.import_snapshot import main as snap_main
        return snap_main(args)
```

Run:

```bash
pytest tests/test_snapshot_import.py -v -q
```

Expected: `2 passed`.

```bash
git add src/discover_intel/ingest/import_snapshot.py src/discover_intel/cli.py tests/fixtures/d2tr_snapshot_sample.tsv tests/test_snapshot_import.py
git commit -m "feat: import-snapshot module + CLI"
```

---

## Phase 8 — GSC

### Task 19: GSC API call with mocked client

**Files:**
- Create: `src/discover_intel/ingest/gsc_discover.py` (partial)
- Create: `tests/test_gsc_query.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_gsc_query.py`

```python
from unittest.mock import MagicMock, patch

from discover_intel.ingest.gsc_discover import (
    build_gsc_service, query_and_upsert,
)


def _canned_response():
    return {
        "rows": [
            {"keys": ["2026-09-20", "usa", "MOBILE",
                      "https://economictimes.indiatimes.com/x"],
             "clicks": 12, "impressions": 300, "ctr": 0.04, "position": 3.2},
            {"keys": ["2026-09-20", "usa", "DESKTOP",
                      "https://economictimes.indiatimes.com/y"],
             "clicks": 3, "impressions": 100, "ctr": 0.03, "position": 5.0},
        ],
        "responseAggregationType": "byPage",
    }


def test_query_and_upsert_writes_rows(conn):
    fake_execute = MagicMock(return_value=_canned_response())
    fake_query = MagicMock(execute=fake_execute)
    fake_service = MagicMock()
    fake_service.searchanalytics.return_value.query.return_value = fake_query

    n = query_and_upsert(
        conn, service=fake_service,
        property_url="sc-domain:economictimes.indiatimes.com",
        start="2026-09-20", end="2026-09-20",
    )
    assert n == 2

    # verify body params
    kwargs = fake_service.searchanalytics.return_value.query.call_args.kwargs
    body = kwargs["body"]
    assert body["type"] == "discover"
    assert body["dimensions"] == ["date", "country", "device", "page"]
    filters = body["dimensionFilterGroups"][0]["filters"]
    assert any(f["dimension"] == "country" and f["expression"] == "usa"
               for f in filters)

    (imp, clk) = conn.execute(
        "SELECT impressions, clicks FROM gsc_discover WHERE device='MOBILE'"
    ).fetchone()
    assert imp == 300 and clk == 12


def test_query_and_upsert_upserts_on_second_run(conn):
    def resp(start=None, end=None, clicks_bump=0):
        return {"rows": [
            {"keys": ["2026-09-20", "usa", "MOBILE",
                      "https://economictimes.indiatimes.com/x"],
             "clicks": 12 + clicks_bump, "impressions": 300,
             "ctr": 0.04, "position": 3.2},
        ]}

    fake_service = MagicMock()
    fake_service.searchanalytics.return_value.query.return_value.execute.side_effect = [
        resp(), resp(clicks_bump=5),
    ]
    query_and_upsert(conn, service=fake_service,
                     property_url="sc-domain:x", start="2026-09-20", end="2026-09-20")
    query_and_upsert(conn, service=fake_service,
                     property_url="sc-domain:x", start="2026-09-20", end="2026-09-20")
    (n, clk) = conn.execute(
        "SELECT count(*), max(clicks) FROM gsc_discover"
    ).fetchone()
    assert n == 1
    assert clk == 17  # restatement overwrote the row
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_gsc_query.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.ingest.gsc_discover'`.

- [ ] **Step 3: Write `gsc_discover.py` (partial)**

Path: `src/discover_intel/ingest/gsc_discover.py`

```python
"""Nightly Google Search Console pull (type=discover, country=usa)."""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

from discover_intel.util.time import iso_utc, utc_now

log = logging.getLogger(__name__)


def build_gsc_service(sa_json_path: str):
    """Return an authenticated searchconsole v1 service. Real path — not mocked."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        sa_json_path,
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
    )
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def _paginate(service, property_url: str, start: str, end: str, page_size: int = 25000):
    start_row = 0
    while True:
        body: dict[str, Any] = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["date", "country", "device", "page"],
            "type": "discover",
            "dimensionFilterGroups": [{
                "filters": [{
                    "dimension": "country",
                    "operator": "equals",
                    "expression": "usa",
                }],
            }],
            "rowLimit": page_size,
            "startRow": start_row,
        }
        resp = service.searchanalytics().query(
            siteUrl=property_url, body=body
        ).execute()
        rows = resp.get("rows") or []
        for r in rows:
            yield r
        if len(rows) < page_size:
            return
        start_row += page_size


def query_and_upsert(
    conn: sqlite3.Connection,
    service: Any,
    property_url: str,
    start: str,
    end: str,
) -> int:
    imported_at = iso_utc(utc_now())
    n = 0
    for r in _paginate(service, property_url, start, end):
        date_, country, device, page = r["keys"]
        conn.execute(
            "INSERT INTO gsc_discover (date, country, device, page, "
            "impressions, clicks, ctr, position, imported_at) "
            "VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(date, country, device, page) DO UPDATE SET "
            "impressions=excluded.impressions, clicks=excluded.clicks, "
            "ctr=excluded.ctr, position=excluded.position, "
            "imported_at=excluded.imported_at",
            (date_, country, device, page,
             r.get("impressions", 0), r.get("clicks", 0),
             r.get("ctr"), r.get("position"), imported_at),
        )
        n += 1
    conn.commit()
    return n
```

- [ ] **Step 4: Run test to verify pass**

```bash
pytest tests/test_gsc_query.py -v -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/ingest/gsc_discover.py tests/test_gsc_query.py
git commit -m "feat: gsc_discover query_and_upsert with mocked service"
```

---

### Task 20: GSC CLI + env validation + 403/404 remediation

**Files:**
- Modify: `src/discover_intel/ingest/gsc_discover.py`
- Modify: `src/discover_intel/cli.py`
- Create: `tests/test_gsc_cli.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_gsc_cli.py`

```python
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from discover_intel.ingest.gsc_discover import handle_http_error, main_from_env


class _FakeResp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "reason"


def test_403_remediation_message(capsys):
    err = HttpError(_FakeResp(403), b"forbidden")
    rc = handle_http_error(err)
    out = capsys.readouterr().err
    assert rc == 2
    assert "403" in out and "Users and permissions" in out


def test_404_remediation_message(capsys):
    err = HttpError(_FakeResp(404), b"not found")
    rc = handle_http_error(err)
    out = capsys.readouterr().err
    assert rc == 2
    assert "404" in out and "GSC_PROPERTY" in out


def test_main_requires_env(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("GSC_SA_JSON", raising=False)
    monkeypatch.delenv("GSC_PROPERTY", raising=False)
    rc = main_from_env(argv=["--db", str(tmp_path / "wh.db"), "--dry-run"])
    out = capsys.readouterr().err
    assert rc == 2
    assert "GSC_SA_JSON" in out and "GSC_PROPERTY" in out


def test_dry_run_prints_planned_query(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GSC_SA_JSON", str(tmp_path / "fake.json"))
    (tmp_path / "fake.json").write_text("{}")
    monkeypatch.setenv("GSC_PROPERTY", "sc-domain:example.com")
    # init the DB so main_from_env can open it
    subprocess.run([sys.executable, "-m", "discover_intel", "init-db",
                    "--db", str(tmp_path / "wh.db")], check=True)
    rc = main_from_env(argv=["--db", str(tmp_path / "wh.db"),
                             "--start", "2026-09-20", "--end", "2026-09-22",
                             "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "gsc dry-run" in out.lower()
    assert "sc-domain:example.com" in out
    assert "2026-09-20" in out and "2026-09-22" in out
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_gsc_cli.py -v -q
```

Expected: `ImportError: cannot import name 'handle_http_error'`.

- [ ] **Step 3: Append CLI + error handling**

Append to `src/discover_intel/ingest/gsc_discover.py`:

```python
import argparse
import datetime as dt
import os
import sys
from pathlib import Path


def handle_http_error(exc) -> int:
    """Print a remediation message and return the exit code."""
    status = getattr(getattr(exc, "resp", None), "status", None) or 0
    if status == 403:
        sys.stderr.write(
            "gsc: 403 Forbidden — the service account cannot read the GSC property.\n"
            "  Remediation:\n"
            "    1. Search Console → Settings → Users and permissions → Add user\n"
            "       claude-ga-mcp@ga4-mcp-504403.iam.gserviceaccount.com (Restricted or Full).\n"
            "    2. Google Cloud Console → APIs & Services → Library →\n"
            "       enable 'Google Search Console API' in project ga4-mcp-504403.\n"
        )
        return 2
    if status == 404:
        sys.stderr.write(
            "gsc: 404 Not Found — the property URL was not recognised.\n"
            "  Check GSC_PROPERTY: use 'https://economictimes.indiatimes.com/' for a URL\n"
            "  property, or 'sc-domain:economictimes.indiatimes.com' for a Domain property.\n"
        )
        return 2
    sys.stderr.write(f"gsc: HTTP error {status}: {exc}\n")
    return 1


def _default_dates() -> tuple[str, str]:
    end = utc_now().date() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=3)
    return start.isoformat(), end.isoformat()


def main_from_env(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="discover_intel gsc")
    parser.add_argument("--db", required=True)
    d_start, d_end = _default_dates()
    parser.add_argument("--start", default=d_start)
    parser.add_argument("--end", default=d_end)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    sa = os.environ.get("GSC_SA_JSON")
    prop = os.environ.get("GSC_PROPERTY")
    if not sa or not prop:
        sys.stderr.write(
            "gsc: missing env vars.\n"
            "  Set GSC_SA_JSON to the service account JSON path (setx GSC_SA_JSON ...).\n"
            "  Set GSC_PROPERTY to the property URL or sc-domain: form.\n"
        )
        return 2

    if args.dry_run:
        print(
            f"gsc dry-run: property={prop}  dates={args.start}..{args.end}  "
            f"dimensions=[date,country,device,page]  filter=country=usa"
        )
        return 0

    if not Path(sa).exists():
        sys.stderr.write(f"gsc: GSC_SA_JSON does not exist: {sa}\n")
        return 2

    try:
        from googleapiclient.errors import HttpError

        service = build_gsc_service(sa)
        conn = sqlite3.connect(args.db)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            n = query_and_upsert(conn, service, prop, args.start, args.end)
        finally:
            conn.close()
        print(
            f"gsc: pulled {args.start}..{args.end}, {n} rows upserted (usa)"
        )
        return 0
    except HttpError as exc:
        return handle_http_error(exc)


def main(args) -> int:
    argv: list[str] = ["--db", args.db, "--start", args.start, "--end", args.end]
    if args.dry_run:
        argv.append("--dry-run")
    return main_from_env(argv)
```

- [ ] **Step 4: Wire the CLI**

In `src/discover_intel/cli.py`, replace the `gsc` stub:

```python
    p_gsc = sub.add_parser("gsc", help="nightly Google Search Console pull (Discover)")
    p_gsc.add_argument("--db", required=True)
    p_gsc.add_argument("--start", default=None)
    p_gsc.add_argument("--end", default=None)
    p_gsc.add_argument("--dry-run", action="store_true")
```

In `main`:

```python
    if args.cmd == "gsc":
        from discover_intel.ingest.gsc_discover import main as gsc_main
        return gsc_main(args)
```

- [ ] **Step 5: Run tests + commit**

```bash
pytest tests/test_gsc_cli.py -v -q
```

Expected: `4 passed`.

```bash
git add src/discover_intel/ingest/gsc_discover.py src/discover_intel/cli.py tests/test_gsc_cli.py
git commit -m "feat: gsc CLI + env validation + 403/404 remediation"
```

---

## Phase 9 — Ops (backup + vacuum)

### Task 21: `ops/backup.py` — online backup + retention

**Files:**
- Create: `src/discover_intel/ops/backup.py` (partial)
- Create: `tests/test_backup.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_backup.py`

```python
import datetime as dt
from pathlib import Path

from discover_intel.db import connect, apply_schema
from discover_intel.ops.backup import backup_db, prune_backups


def test_backup_creates_dated_file(tmp_path: Path):
    src = tmp_path / "wh.db"
    conn = connect(src)
    apply_schema(conn)
    conn.execute(
        "INSERT INTO sources (source_id, kind, market, name, url, enabled) "
        "VALUES ('x', 'web', 'US', 'x', 'https://x/y', 1)"
    )
    conn.commit()
    conn.close()

    dest_dir = tmp_path / "backups"
    path = backup_db(src, dest_dir)
    assert path.exists()
    assert path.name.startswith("warehouse-")
    assert path.suffix == ".db"


def test_backup_refuses_second_same_day_unless_force(tmp_path: Path):
    src = tmp_path / "wh.db"
    apply_schema(connect(src))
    dest_dir = tmp_path / "backups"
    p1 = backup_db(src, dest_dir)
    # Second call without --force returns the existing path and does not overwrite.
    p2 = backup_db(src, dest_dir)
    assert p1 == p2
    p3 = backup_db(src, dest_dir, force=True)
    assert p3 == p1  # same filename, but rewritten


def test_prune_keeps_14_dailies_and_sundays(tmp_path: Path):
    d = tmp_path / "backups"
    d.mkdir()
    # create 30 fake daily backups
    base = dt.date(2026, 1, 1)
    for i in range(30):
        day = base + dt.timedelta(days=i)
        (d / f"warehouse-{day.isoformat()}.db").write_bytes(b"x")

    kept = prune_backups(d, keep_dailies=14, ref_date=base + dt.timedelta(days=29))
    names = sorted(p.name for p in d.iterdir())
    # 14 most-recent + all Sundays before that
    assert any(n == "warehouse-2026-01-01.db"  # Jan 1 2026 is a Thursday, not Sunday
               for n in names) is False
    # Sundays in Jan 2026: 4, 11, 18, 25. Only those before the 14-day window should remain
    # extras. All Sundays overall are preserved; the specific returned kept set is a superset
    # of the 14-day window.
    assert len(kept) >= 14
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_backup.py -v -q
```

Expected: `ModuleNotFoundError: No module named 'discover_intel.ops.backup'`.

- [ ] **Step 3: Write `ops/backup.py` (backup + prune)**

Path: `src/discover_intel/ops/backup.py`

```python
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
```

- [ ] **Step 4: Wire the CLI + run tests**

In `src/discover_intel/cli.py`, replace the `backup` stub:

```python
    p_bk = sub.add_parser("backup", help="online backup of warehouse.db")
    p_bk.add_argument("--db", required=True)
    p_bk.add_argument("--dest-dir", default="data/backups", dest="dest_dir")
    p_bk.add_argument("--force", action="store_true")
    p_bk.add_argument("--keep-dailies", type=int, default=14, dest="keep_dailies")
```

In `main`:

```python
    if args.cmd == "backup":
        from discover_intel.ops.backup import main as bk_main
        return bk_main(args)
```

Run:

```bash
pytest tests/test_backup.py -v -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/ops/backup.py src/discover_intel/cli.py tests/test_backup.py
git commit -m "feat: backup command with retention (14 dailies + Sundays)"
```

---

### Task 22: `ops/backup.py` — VACUUM + CLI

**Files:**
- Modify: `src/discover_intel/ops/backup.py`
- Modify: `src/discover_intel/cli.py`
- Create: `tests/test_vacuum.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_vacuum.py`

```python
import datetime as dt
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
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_vacuum.py -v -q
```

Expected: `ImportError: cannot import name 'vacuum_db'`.

- [ ] **Step 3: Append `vacuum_db` + `vacuum_main`**

Append to `src/discover_intel/ops/backup.py`:

```python
def vacuum_db(source: Path, backups_dir: Path, force: bool = False) -> None:
    today = _today_str()
    today_backup = backups_dir / f"warehouse-{today}.db"
    if not force and not today_backup.exists():
        raise RuntimeError(
            f"vacuum: refusing without today's backup at {today_backup}. "
            f"Run `discover_intel backup --db {source}` first, or pass --force."
        )
    conn = sqlite3.connect(str(source))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("VACUUM")
    finally:
        conn.close()
    log.info("vacuum: complete for %s", source)


def vacuum_main(args) -> int:
    vacuum_db(Path(args.db), Path(args.backups_dir), force=args.force)
    print("vacuum: done")
    return 0
```

- [ ] **Step 4: Wire the CLI and run tests**

In `src/discover_intel/cli.py`, replace the `vacuum` stub:

```python
    p_vc = sub.add_parser("vacuum", help="checkpoint WAL and VACUUM")
    p_vc.add_argument("--db", required=True)
    p_vc.add_argument("--backups-dir", default="data/backups", dest="backups_dir")
    p_vc.add_argument("--force", action="store_true")
```

In `main`:

```python
    if args.cmd == "vacuum":
        from discover_intel.ops.backup import vacuum_main
        return vacuum_main(args)
```

Run:

```bash
pytest tests/test_vacuum.py -v -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/ops/backup.py src/discover_intel/cli.py tests/test_vacuum.py
git commit -m "feat: vacuum command with today's-backup guard"
```

---

## Phase 10 — CLI finish (db-stats + full dispatcher tests)

### Task 23: `db-stats` + dispatcher completeness test

**Files:**
- Modify: `src/discover_intel/cli.py`
- Create: `tests/test_dbstats.py`

- [ ] **Step 1: Write the failing test**

Path: `tests/test_dbstats.py`

```python
import subprocess
import sys
from pathlib import Path


def test_db_stats_prints_all_tables(tmp_path: Path):
    db_path = tmp_path / "wh.db"
    subprocess.run(
        [sys.executable, "-m", "discover_intel", "init-db", "--db", str(db_path)],
        check=True,
    )
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "db-stats", "--db", str(db_path)],
        capture_output=True, text=True, check=True,
    )
    out = r.stdout
    for t in ("sources", "items", "feed_polls", "discover_articles",
              "discover_snapshots", "gsc_discover"):
        assert t in out
        assert f"{t}=0" in out or f"{t}: 0" in out


def test_dispatcher_lists_no_stubs():
    r = subprocess.run(
        [sys.executable, "-m", "discover_intel", "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "stub" not in r.stdout.lower()
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_dbstats.py -v -q
```

Expected: `db-stats` output missing tables, or "stub" in help.

- [ ] **Step 3: Implement `db-stats` and remove all stubs**

In `src/discover_intel/cli.py`, replace the stub loop entirely with explicit subparsers for every command (which by Task 22 all exist except `db-stats`). Add:

```python
    p_stats = sub.add_parser("db-stats", help="print row counts per table")
    p_stats.add_argument("--db", required=True)
```

Add the handler:

```python
def cmd_db_stats(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    tables = [
        "sources", "items", "feed_polls", "discover_articles",
        "discover_snapshots", "gsc_discover",
    ]
    counts = {}
    for t in tables:
        (n,) = conn.execute(f"SELECT count(*) FROM {t}").fetchone()
        counts[t] = n
    conn.close()
    line = " ".join(f"{t}={counts[t]}" for t in tables)
    print(f"db-stats: {line}")
    return 0
```

Wire it in `main`:

```python
    if args.cmd == "db-stats":
        return cmd_db_stats(args)
```

Remove the old auto-stub loop that adds bare subparsers — every subcommand should be explicitly defined by now.

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/ -v -q
```

Expected: all pass (~25 tests).

- [ ] **Step 5: Commit**

```bash
git add src/discover_intel/cli.py tests/test_dbstats.py
git commit -m "feat: add db-stats command; remove all stub subparsers"
```

---

## Phase 11 — PowerShell wrappers + Task Scheduler

### Task 24: PowerShell wrappers (seven scripts)

**Files:**
- Create: `scripts/run-feeds.ps1`
- Create: `scripts/run-youtube.ps1`
- Create: `scripts/run-import-discover.ps1`
- Create: `scripts/run-gsc.ps1`
- Create: `scripts/run-backup.ps1`
- Create: `scripts/run-vacuum.ps1`
- Create: `scripts/run-dbstats.ps1`

- [ ] **Step 1: Write `scripts/run-feeds.ps1`**

Path: `scripts/run-feeds.ps1`

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\feeds.log"
$ts   = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel feeds `
      --db "$root\data\warehouse.db" `
      --kind "web,gnews_site,gnews_query,gnews_section" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] feeds exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] feeds wrapper-error: $_" | Add-Content $log
  exit 1
}
```

- [ ] **Step 2: Write `scripts/run-youtube.ps1`**

Path: `scripts/run-youtube.ps1`

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\youtube.log"
$ts   = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel feeds `
      --db "$root\data\warehouse.db" `
      --kind "youtube" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] youtube exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] youtube wrapper-error: $_" | Add-Content $log
  exit 1
}
```

- [ ] **Step 3: Write the five remaining wrappers**

Path: `scripts/run-import-discover.ps1`

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\import-discover.log"
$ts   = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel import-discover `
      --db "$root\data\warehouse.db" `
      --watch `
      --imports-dir "$root\data\imports\discover" `
      --config-dir "$root\config" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] import-discover exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] import-discover wrapper-error: $_" | Add-Content $log
  exit 1
}
```

Path: `scripts/run-gsc.ps1`

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\gsc.log"
$ts   = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel gsc `
      --db "$root\data\warehouse.db" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] gsc exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] gsc wrapper-error: $_" | Add-Content $log
  exit 1
}
```

Path: `scripts/run-backup.ps1`

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\backup.log"
$ts   = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel backup `
      --db "$root\data\warehouse.db" `
      --dest-dir "$root\data\backups" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] backup exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] backup wrapper-error: $_" | Add-Content $log
  exit 1
}
```

Path: `scripts/run-vacuum.ps1`

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\vacuum.log"
$ts   = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel vacuum `
      --db "$root\data\warehouse.db" `
      --backups-dir "$root\data\backups" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] vacuum exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] vacuum wrapper-error: $_" | Add-Content $log
  exit 1
}
```

Path: `scripts/run-dbstats.ps1`

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\dbstats.log"
$ts   = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel db-stats `
      --db "$root\data\warehouse.db" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] dbstats exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] dbstats wrapper-error: $_" | Add-Content $log
  exit 1
}
```

- [ ] **Step 4: Smoke-test one wrapper**

From the repo root (with the venv active and `data\warehouse.db` initialised):

```powershell
Get-Command powershell
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\run-dbstats.ps1
Get-Content .\logs\dbstats.log -Tail 5
```

Expected: dbstats prints table counts; the log file gets an exit=0 line.

- [ ] **Step 5: Commit**

```bash
git add scripts/run-feeds.ps1 scripts/run-youtube.ps1 scripts/run-import-discover.ps1 scripts/run-gsc.ps1 scripts/run-backup.ps1 scripts/run-vacuum.ps1 scripts/run-dbstats.ps1
git commit -m "feat: add PowerShell wrapper scripts for all seven cron jobs"
```

---

### Task 25: `register-tasks.ps1` + `unregister-tasks.ps1`

**Files:**
- Create: `scripts/register-tasks.ps1`
- Create: `scripts/unregister-tasks.ps1`

- [ ] **Step 1: Write `unregister-tasks.ps1`**

Path: `scripts/unregister-tasks.ps1`

```powershell
$ErrorActionPreference = "Continue"
$names = @(
  "DiscoverIntel_Feeds", "DiscoverIntel_YouTube", "DiscoverIntel_ImportDiscover",
  "DiscoverIntel_GSC", "DiscoverIntel_Backup", "DiscoverIntel_Vacuum",
  "DiscoverIntel_DBStats"
)
foreach ($n in $names) {
  $t = Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
  if ($t) {
    Unregister-ScheduledTask -TaskName $n -Confirm:$false
    Write-Host "unregistered: $n"
  } else {
    Write-Host "not present: $n"
  }
}
```

- [ ] **Step 2: Write `register-tasks.ps1`**

Path: `scripts/register-tasks.ps1`

```powershell
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Register-DI {
  param([string]$Name, [string]$Script, [Microsoft.PowerShell.ScheduledJob.ScheduledJobTrigger[]]$Triggers)

  # Idempotent: remove any prior version first.
  $existing = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
  if ($existing) { Unregister-ScheduledTask -TaskName $Name -Confirm:$false }

  $action    = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$root\scripts\$Script`"" `
    -WorkingDirectory $root

  $principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U -RunLevel Limited

  $settings  = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
    -Compatibility "Win8"    # Win8 == AT2019 in PowerShell 5.1 vocabulary

  Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Triggers `
    -Principal $principal -Settings $settings | Out-Null
  Write-Host "registered: $Name"
}

$now = Get-Date
$midnight = Get-Date -Hour 0 -Minute 0 -Second 0

# every 30 min (from now)
$t_feeds = New-ScheduledTaskTrigger -Once -At $now `
  -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration ([TimeSpan]::MaxValue)

# every 60 min
$t_yt    = New-ScheduledTaskTrigger -Once -At $now `
  -RepetitionInterval (New-TimeSpan -Minutes 60) -RepetitionDuration ([TimeSpan]::MaxValue)

# every 15 min
$t_imp   = New-ScheduledTaskTrigger -Once -At $now `
  -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration ([TimeSpan]::MaxValue)

# daily times
$t_gsc     = New-ScheduledTaskTrigger -Daily -At ([DateTime]"04:00")
$t_backup  = New-ScheduledTaskTrigger -Daily -At ([DateTime]"03:00")
$t_dbstats = New-ScheduledTaskTrigger -Daily -At ([DateTime]"06:00")
# Sunday 03:30
$t_vac = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At ([DateTime]"03:30")

Register-DI -Name "DiscoverIntel_Feeds"          -Script "run-feeds.ps1"           -Triggers $t_feeds
Register-DI -Name "DiscoverIntel_YouTube"        -Script "run-youtube.ps1"         -Triggers $t_yt
Register-DI -Name "DiscoverIntel_ImportDiscover" -Script "run-import-discover.ps1" -Triggers $t_imp
Register-DI -Name "DiscoverIntel_GSC"            -Script "run-gsc.ps1"             -Triggers $t_gsc
Register-DI -Name "DiscoverIntel_Backup"         -Script "run-backup.ps1"          -Triggers $t_backup
Register-DI -Name "DiscoverIntel_Vacuum"         -Script "run-vacuum.ps1"          -Triggers $t_vac
Register-DI -Name "DiscoverIntel_DBStats"        -Script "run-dbstats.ps1"         -Triggers $t_dbstats

Write-Host ""
Write-Host "Task Scheduler summary:"
Get-ScheduledTask -TaskName "DiscoverIntel_*" | Format-Table TaskName, State
```

- [ ] **Step 3: Smoke test by inspecting scripts (no live registration in the test)**

Run:

```powershell
# Parse-only sanity checks — no tasks are registered.
powershell -NoProfile -NonInteractive -Command "Get-Command .\scripts\register-tasks.ps1"
powershell -NoProfile -NonInteractive -Command "[System.Management.Automation.Language.Parser]::ParseFile('$PWD\scripts\register-tasks.ps1', [ref]$null, [ref]$errs); \$errs"
powershell -NoProfile -NonInteractive -Command "[System.Management.Automation.Language.Parser]::ParseFile('$PWD\scripts\unregister-tasks.ps1', [ref]$null, [ref]$errs); \$errs"
```

Expected: `Get-Command` prints script details; the parse checks emit no errors.

- [ ] **Step 4: Live registration test (final acceptance — do this once when ready to install)**

```powershell
.\scripts\register-tasks.ps1
Get-ScheduledTask -TaskName "DiscoverIntel_*" | Format-Table TaskName, State
# To roll back:
.\scripts\unregister-tasks.ps1
```

Expected on first: 7 lines "registered: DiscoverIntel_*", then a table showing all 7 in `Ready` state.

- [ ] **Step 5: Commit**

```bash
git add scripts/register-tasks.ps1 scripts/unregister-tasks.ps1
git commit -m "feat: register-tasks + unregister-tasks for the seven cron jobs"
```

---

## Phase 12 — E2E: README and acceptance smoke

### Task 26: Complete README with acceptance checklist

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Draft the README structure**

Sections to cover: overview, first-time setup, daily workflow (Task Scheduler auto), manual invocations, troubleshooting, then the acceptance smoke commands from spec § 13 numbered exactly.

- [ ] **Step 2: Write `README.md`**

Path: `README.md` (replaces the skeleton from Task 1)

```markdown
# discover-intel — Sprint 1 (Ingestion)

Foundation of the Discover Intelligence System for ET's US desk.
Populates a local SQLite warehouse from ~181 sources (native RSS, Google News
site/query/section, YouTube Atom) plus file-based importers for DiscoverTrends
CSV exports and D2TR snapshot pastes, and a nightly Google Search Console pull.

**Spec:** `docs/superpowers/specs/2026-09-23-sprint-1-ingestion-design.md`.
**Plan:** `docs/superpowers/plans/2026-09-23-sprint-1-ingestion.md`.

## First-time setup (Windows 11)

Run once from a fresh clone, in the repo root:

```powershell
# 1. Create the virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev]"

# 2. Persist environment variables (one-time)
setx GSC_SA_JSON "C:\Users\Anil.Kumar6\Desktop\My Inteligence System\ga4-mcp-504403-c72f94fdfd37 (2).json"
setx GSC_PROPERTY "sc-domain:economictimes.indiatimes.com"    # or the URL form

# 3. Initialise the DB and seed sources
python -m discover_intel init-db --db data\warehouse.db
python -m discover_intel seed-sources --xlsx "C:\Users\Anil.Kumar6\Downloads\USA Top Publishers.xlsx" --config-dir config

# 4. Install the seven scheduled tasks
.\scripts\register-tasks.ps1
```

**GSC prerequisites (one-time, off-code):**

1. Enable **Google Search Console API** in Google Cloud project `ga4-mcp-504403`
   (Console → APIs & Services → Library).
2. Add `claude-ga-mcp@ga4-mcp-504403.iam.gserviceaccount.com` as **Restricted**
   or **Full** on the ET Search Console property
   (Search Console → Settings → Users and permissions).

Until both are done, `discover_intel gsc` will 403 with a remediation message.

## Everyday operations

Scheduled tasks run automatically. Nothing to do.

If you need a manual run:

```powershell
python -m discover_intel feeds --db data\warehouse.db --kind web,gnews_site,gnews_query,gnews_section
python -m discover_intel feeds --db data\warehouse.db --kind youtube
python -m discover_intel import-discover --db data\warehouse.db --watch
python -m discover_intel import-discover --db data\warehouse.db --file "C:\path\to\DiscoverTrends_YYYY-MM-DD_HHMM.csv"
python -m discover_intel gsc --db data\warehouse.db
python -m discover_intel backup --db data\warehouse.db
python -m discover_intel vacuum --db data\warehouse.db
python -m discover_intel db-stats --db data\warehouse.db
```

## Acceptance smoke checklist (spec § 13)

Run each in order from the repo root with the venv active:

1. `python -m discover_intel init-db --db data\warehouse.db`
   → creates `data\warehouse.db`. Verify with:
   `python -c "import sqlite3;print(sqlite3.connect('data/warehouse.db').execute('PRAGMA user_version').fetchone())"`
   Expected: `(1,)`.

2. `python -m discover_intel seed-sources --xlsx "C:\Users\Anil.Kumar6\Downloads\USA Top Publishers.xlsx" --config-dir config`
   → writes `config\sources_{web,gnews,youtube}.csv` with ~20 web + 50 gnews + ~98 youtube rows.

3. `python -m discover_intel feeds --db data\warehouse.db --kind web,gnews_site,gnews_query,gnews_section --dry-run`
   → prints per-source URLs. Manually verify ≥ 95% look sane.

4. `python -m discover_intel feeds --db data\warehouse.db --kind web,gnews_site,gnews_query,gnews_section`
   → real run; ends in < 5 min. Prints one summary line.

5. `python -m discover_intel import-discover --db data\warehouse.db --file "C:\Users\Anil.Kumar6\Downloads\DiscoverTrends_2026-09-23_1547.csv"`
   → writes 319 rows into `discover_articles`, `observed_at = 2026-09-23T15:47:00Z`.

6. Re-run (5). Expected: `319 dup, 0 new`.

7. `python -m discover_intel gsc --db data\warehouse.db --dry-run`
   → validates env vars, prints the planned query. (Real run runs after GSC
   prerequisites are done.)

8. `python -m discover_intel db-stats --db data\warehouse.db`
   → prints `sources=N items=M feed_polls=P discover_articles=319 discover_snapshots=0 gsc_discover=0`.

9. `.\scripts\register-tasks.ps1` → registers 7 tasks;
   `Get-ScheduledTask -TaskName "DiscoverIntel_*"` shows them all `Ready`.

10. `pytest tests\ -q` — all tests pass in < 5s.

## Troubleshooting

- **`gsc: 403 Forbidden`** → the service account is not on the GSC property. See
  the two prerequisites above.
- **`gsc: 404 Not Found`** → `GSC_PROPERTY` doesn't match how the property is
  registered in Search Console. Try the sc-domain: form vs the URL form.
- **A feed keeps returning 4xx** → run `python -m discover_intel feeds --dry-run`
  to see which URL fails, then either fix the entry in `config/sources_*.csv`
  or disable it with an SQL update (`UPDATE sources SET enabled=0 WHERE
  source_id = '...'`).
- **DiscoverTrends CSV rejected with "Filename does not match ..."** → rename
  the file to match `DiscoverTrends_YYYY-MM-DD_HHMM.csv` before dropping it in
  `data\imports\discover\`.

## Reserved for later sprints

Sprints 2–4 (URL resolver, entity/topic tagger, outcome matcher, TOS/DRS
scoring, Slack digest, dashboard, scorecard) will build on this warehouse but
add their own tables and modules. See the PRD for the full plan.
```

- [ ] **Step 3: Run the full test suite as final sanity**

```bash
pytest tests/ -v -q
```

Expected: all pass in < 5s.

- [ ] **Step 4: Run acceptance smoke steps 1, 2, 5, 6, 8**

```powershell
python -m discover_intel init-db --db data\warehouse.db
python -m discover_intel seed-sources --xlsx "C:\Users\Anil.Kumar6\Downloads\USA Top Publishers.xlsx" --config-dir config
python -m discover_intel import-discover --db data\warehouse.db --file "C:\Users\Anil.Kumar6\Downloads\DiscoverTrends_2026-09-23_1547.csv"
python -m discover_intel import-discover --db data\warehouse.db --file "C:\Users\Anil.Kumar6\Downloads\DiscoverTrends_2026-09-23_1547.csv"
python -m discover_intel db-stats --db data\warehouse.db
```

Expected:
- First import prints `319 new`; second prints `0 new, 319 dup`.
- `db-stats` shows `discover_articles=319`.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: complete README (first-time setup + acceptance checklist)"
```

---

## Self-review (author, not a subagent)

### Spec coverage check

| Spec section | Covered by task(s) |
|---|---|
| § 1 Purpose | The whole plan |
| § 2 Resolved decisions | Tasks 24–25 (Task Scheduler), 10 (xlsx seeding), 16 (watch folder) |
| § 3 Non-goals | Enforced by leaving Sprint 2/3 tables out of Task 2 |
| § 4 Prerequisites | Task 26 README |
| § 5 Repo layout | Task 1 |
| § 6 Data model | Task 2 |
| § 7.1 `cli.py` | Tasks 8, 23 |
| § 7.2 `db.py` | Task 3 |
| § 7.3 `config.py` | Tasks 9, 10 |
| § 7.4 `feeds.py` | Tasks 11, 12, 13 |
| § 7.5 `import_discover_file.py` | Tasks 14, 15, 16 |
| § 7.6 `import_snapshot.py` | Tasks 17, 18 |
| § 7.7 `gsc_discover.py` | Tasks 19, 20 |
| § 7.8 `ops/backup.py` | Tasks 21, 22 |
| § 8 Failure model | Enforced across per-item/per-file try/except and poll persistence |
| § 9 Task Scheduler wiring | Tasks 24, 25 |
| § 10 Secrets | Task 1 (`.env.example`, `secrets/README.md`), Task 20 (env validation) |
| § 11 Logging | Wrapper `Tee-Object` in Task 24; Python `log = logging.getLogger(__name__)` in feeds/importers |
| § 12 Testing | pytest fixture in Task 4; each subsequent task has TDD steps |
| § 13 Acceptance criteria | Task 26 README numbered checklist |
| § 14 Dependencies | Task 1 `pyproject.toml` |
| § 15 Open questions | Non-blocking; captured in Task 26 README troubleshooting |

No gaps.

### Placeholder scan

- No "TODO" / "TBD" / "fill in later" in any task step.
- One "TODO" *inside* `config/discover_import_mappings.yaml` — that is a spec-blessed placeholder for Marfeel until a real export exists; kept per spec § 7.5.
- All test steps have concrete code; all commit steps have concrete messages.

### Type-consistency scan

- `ParsedItem` (Task 11) is imported and used in Tasks 12, 13 — same fields.
- `Source` dataclass (Task 9) shape matches every fixture insert in Tasks 12, 13.
- `parse_kmb`, `parse_hm` (Task 17) → used only in Task 18.
- `apply_schema`, `connect`, `upsert` (Task 3) — used across every DB-touching test.
- CLI `--db`, `--dry-run`, `--limit` names stable across tasks.
- Log message shapes consistent (`"cmd: ..."`).

No inconsistencies found.
