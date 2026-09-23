# Discover Intelligence System — Sprint 1 (Ingestion) Design

**Date:** 2026-09-23
**Owner:** Anil Kumar (etaitools@timesinternet.in) — ET Growth / SEO
**Status:** Design approved, ready for implementation plan
**Scope:** Sprint 1 only (schema + ingestion + importers + Windows Task Scheduler). Sprints 2–4 (resolver / matcher / tagger / TOS / DRS / delivery / scorecard) are out of scope for this spec.
**PRD:** `C:\Users\Anil.Kumar6\Downloads\PRD.md`
**Deployment target:** Windows 11 laptop, dev + prod on the same machine.

---

## 1. Purpose

Build the ingestion foundation of the Discover Intelligence System: a SQLite warehouse continuously populated from ~181 US sources (native RSS, Google News site/query/section feeds, YouTube Atom feeds), plus file-based importers for DiscoverTrends CSV exports, D2TR snapshot pastes, and nightly Google Search Console pulls. Nothing in this sprint scores, ranks, or delivers — just clean, deduped ingestion.

Everything downstream (Sprint 2 resolver/matcher/tagger, Sprint 3 TOS/DRS/digest, Sprint 4 scorecard) reads from the warehouse this sprint creates.

## 2. Resolved decisions (three forks)

Before the design was locked in, three architectural forks were resolved with the user:

1. **Scheduling — Windows Task Scheduler + PowerShell wrappers.** Chosen over in-process APScheduler because laptops sleep; Task Scheduler's "run at next available time" catches missed cadences. Native to Windows, visible in Task Scheduler UI, one process per task.
2. **Source seeding — xlsx-authoritative + PRD's Google News queries.** The user supplied `USA Top Publishers.xlsx` with 31 native RSS/sitemap publishers and 100 YouTube channels (with resolved channel IDs). Native RSS list and YouTube list come from the xlsx. Google News beat queries (15) and section feeds (4) come from the PRD. Site-scoped Google News queries use the same 31 hosts (a superset of the PRD's 23). Total: ~181 sources.
3. **DiscoverTrends importer — watch folder + manual CLI.** A Task Scheduler entry runs every 15 minutes and imports any file dropped into `data\imports\discover\`. A manual `--file` flag exists for one-off imports.

## 3. Non-goals

- **No entity/topic tagging.** Sprint 2.
- **No URL canonicalization.** Sprint 2. Google News redirect URLs are stored as-is in `items.url` with `canonical_url = NULL`.
- **No outcome matching** (linking `discover_articles` to `items`). Sprint 2.
- **No scoring** (TOS, DRS). Sprint 3.
- **No delivery** (Slack, dashboard). Sprint 3.
- **No UK market.** PRD says US-only for Stage 1; schema carries a `market` column so UK is a config flip later.
- **No feedback loop into scoring weights.** Sprint 4's scorecard is measurement-only.

## 4. Prerequisites (user must complete before Sprint 1 runs end-to-end)

1. **Google Search Console API enabled** in Google Cloud project `ga4-mcp-504403`. (Console → APIs & Services → Library → enable "Google Search Console API".) The service account was created for GA4, so this API is likely not yet enabled.
2. **Service account added to the ET Search Console property.** In Search Console → Settings → Users and permissions, add `claude-ga-mcp@ga4-mcp-504403.iam.gserviceaccount.com` as **Restricted** or **Full**.
3. **`GSC_PROPERTY` value chosen.** Full URL (`https://economictimes.indiatimes.com/`) or `sc-domain:economictimes.indiatimes.com`. Depends on how the property is registered in Search Console.
4. **Two YouTube channel IDs still unresolved** in the xlsx: ABC7 News and Fox Weather. To be filled by hand in `config/sources_youtube.csv` after the initial seed, or the xlsx updated and re-seeded.

None of these block writing code — `gsc_discover.py` can be built and unit-tested against fixtures; live GSC calls just 403 until (1) and (2) are done.

## 5. Repo layout

Everything lives under `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\discover-intel\`. Package name `discover_intel`. Python 3.11+. Single `.venv/`.

```
discover-intel/
├─ pyproject.toml              # deps + ruff config
├─ requirements.txt            # pinned
├─ README.md                   # setup, env vars, run instructions
├─ .env.example                # GSC_SA_JSON, GSC_PROPERTY, ANTHROPIC_API_KEY (Sprint 2+)
├─ .gitignore                  # secrets/, data/, logs/, .venv/, *.json under secrets/
│
├─ src/discover_intel/
│   ├─ __init__.py
│   ├─ cli.py                  # top-level dispatcher
│   ├─ db.py                   # connection + schema application
│   ├─ config.py               # source registry + env vars + xlsx seeding
│   ├─ ingest/
│   │   ├─ __init__.py
│   │   ├─ feeds.py            # RSS/Atom + Google News + YouTube poller
│   │   ├─ import_discover_file.py
│   │   ├─ import_snapshot.py
│   │   └─ gsc_discover.py
│   ├─ util/
│   │   ├─ __init__.py
│   │   ├─ http.py             # httpx client + rate limit
│   │   ├─ url.py              # normalise, strip utm/#
│   │   └─ time.py             # UTC helpers, filename → timestamp
│   └─ ops/
│       ├─ __init__.py
│       └─ backup.py           # online backup + VACUUM
│
├─ sql/
│   └─ schema.sql              # single source of truth
│
├─ config/
│   ├─ sources_web.csv         # generated from xlsx Sheet1
│   ├─ sources_gnews.csv       # 31 site-scoped + 15 beat + 4 sections
│   ├─ sources_youtube.csv     # generated from xlsx Sheet2
│   └─ discover_import_mappings.yaml   # tool → header alias map
│
├─ scripts/                    # PowerShell wrappers, all uniform shape
│   ├─ register-tasks.ps1
│   ├─ unregister-tasks.ps1
│   ├─ run-feeds.ps1
│   ├─ run-youtube.ps1
│   ├─ run-import-discover.ps1
│   ├─ run-gsc.ps1
│   ├─ run-backup.ps1
│   ├─ run-vacuum.ps1
│   └─ run-dbstats.ps1
│
├─ data/                       # gitignored
│   ├─ warehouse.db
│   ├─ backups/
│   └─ imports/
│       └─ discover/
│           ├─ processed/YYYY-MM/
│           └─ failed/
│
├─ logs/                       # gitignored, rotating
│
├─ secrets/                    # gitignored
│   └─ README.md               # instructions; JSON stays at Desktop path
│
└─ tests/
    ├─ conftest.py
    ├─ fixtures/
    │   ├─ google_news_rss_sample.xml
    │   ├─ native_rss_sample.xml
    │   ├─ youtube_atom_sample.xml
    │   ├─ discovertrends_2026-09-23_1509.csv    # user's file, copied in
    │   ├─ discovertrends_2026-09-23_1547.csv
    │   ├─ marfeel_sample.xlsx                    # placeholder, tests skip
    │   └─ d2tr_snapshot_sample.tsv               # derived from xlsx Sheet2
    └─ test_*.py
```

**Layout rationale:**
- **Src layout with `pyproject.toml`** prevents accidental imports of `data/` or `tests/` at runtime and keeps ruff/pytest paths clean.
- **Single CLI dispatcher.** All jobs invoke `python -m discover_intel <cmd>`. PowerShell wrappers stay one-line variants of the same shape.
- **SA JSON stays outside the repo.** Referenced by `GSC_SA_JSON` env var pointing at `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\ga4-mcp-504403-c72f94fdfd37 (2).json`. `.gitignore` has `*.json` under `secrets/` as belt-and-suspenders.

## 6. Data model

Six tables. All timestamps UTC ISO-8601. Postgres-portable types (no `AUTOINCREMENT`, no SQLite-only collations).

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
```

**Key non-obvious data-model decisions:**

- **`DiscoverTrends.Author` maps to `discover_articles.host`, not `author`.** Verified across both sample CSVs — every value in that column is a domain (`www.nj.com`, `timesofindia.indiatimes.com`, etc.). The `author` field stays NULL for DiscoverTrends rows.
- **`observed_at` for DiscoverTrends comes from filename.** Regex `DiscoverTrends_(\d{4}-\d{2}-\d{2})_(\d{2})(\d{2})\.csv` → ISO UTC. If the filename doesn't match, importer refuses (no invented timestamps). Directly closes PRD open question #1.
- **`discover_articles.format` stays NULL for DiscoverTrends.** The CSV has no format column. Sprint 2 tagger fills it via `config/format_rules.yaml`. Marfeel imports populate it directly if present.
- **`raw_json` on `discover_articles` and `discover_snapshots`.** Any tool-specific columns without a first-class field are stashed as JSON — cheap future-proofing.
- **`sources.tier` and `sources.category`** carry the xlsx's tier (A/B/C) and category (National / Local TV / International / Business / Lifestyle). Sprint 2+ will use these for weighting; cheap to populate now.
- **No Sprint 2/3 tables** (`item_outcomes`, `taxonomy`, `topic_stats`, `topic_scores`, `article_scores`). Reserved names listed at the bottom of `schema.sql` as a comment; adding them later is a `user_version` bump.

## 7. Component contracts

Each module honors the PRD non-functionals: `--db`, `--dry-run` (when writing), `--limit`, idempotent re-runs, one-line summary log, UTC everywhere, no network in tests.

### 7.1 `cli.py` — top-level dispatcher

Signature: `python -m discover_intel <subcommand> [args...]`.

Subcommands: `init-db`, `seed-sources`, `feeds`, `import-discover`, `import-snapshot`, `gsc`, `backup`, `vacuum`, `db-stats`. Each is a thin argparse handler dispatching to the module's `main(args)`.

`db-stats` prints row counts per table — useful for sanity checks and daily cron logs.

### 7.2 `db.py`

- `connect(path) -> sqlite3.Connection`: `PRAGMA foreign_keys=ON`, `journal_mode=WAL`, `busy_timeout=5000`, `row_factory = sqlite3.Row`.
- `apply_schema(conn)`: runs `sql/schema.sql` if `PRAGMA user_version` is behind. Idempotent — safe on every job start.
- `upsert(conn, table, row, key)` helper. No ORM. Explicit parameterised SQL.

### 7.3 `config.py`

- Loads `config/sources_*.csv` into a unified list of `Source` dataclasses.
- `seed-sources` command reads the xlsx (default: `C:\Users\Anil.Kumar6\Downloads\USA Top Publishers.xlsx`, override via `--xlsx`) and **writes/overwrites** the three CSVs deterministically. Hand-editing CSVs is not the workflow; re-run `seed-sources` after any xlsx change.
- Env vars: `GSC_SA_JSON` (path), `GSC_PROPERTY` (URL or `sc-domain:` form). No `.env` loader — set once via `setx`.

**Source seeding rules:**

- **`sources_web.csv`** ← xlsx Sheet1, filtered to rows with a non-null RSS feed URL. Sitemap-only rows are skipped for native-RSS polling (RSS is cheap, sitemaps are big/slow) — but they still get covered by the site-scoped Google News query below.
- **`sources_gnews.csv`** ← three sections concatenated:
  - 31 `gnews_site` rows: `https://news.google.com/rss/search?q=site:<host>+when:1d&hl=en-US&gl=US&ceid=US:en` for every host in xlsx Sheet1.
  - 15 `gnews_query` beat-query rows (transcribed from PRD § 5: Fed, mortgage rates, mansion, net worth, etc.).
  - 4 `gnews_section` rows: Top Stories, Business, Technology, World (US edition).
- **`sources_youtube.csv`** ← xlsx Sheet2, all 100 rows with a resolved `channel_id`. Feed URL = `https://www.youtube.com/feeds/videos.xml?channel_id=<id>`. ABC7 News and Fox Weather remain unresolved and are omitted; user fills in later.

### 7.4 `ingest/feeds.py`

Runs against `sources.enabled=1`, filtered by `--kind` (comma-separated: `web,gnews_site,gnews_query,gnews_section,youtube`). Two Task Scheduler entries share this one module: feeds/30-min covers `web,gnews_*`; youtube/60-min covers `youtube` only.

- **Fetch:** `httpx.Client(timeout=10, follow_redirects=True, http2=True)` with browser-like UA. Global **5 req/s** token-bucket rate limit. Retries: **1 retry on 5xx or connection error**, backoff (2s, 4s). **Never retry 4xx** (per PRD).
- **Parse:** `feedparser` for RSS/Atom (handles YouTube Atom and Google News RSS). Extract `title`, `link`, `published`, `summary`, `author`.
- **Google News URLs stored as-is.** No canonicalisation in Sprint 1. Sprint 2 resolver fills `canonical_url`.
- **Item ID + dedup:** `item_id = sha1(source_id + '|' + url)`. Same `item_id` → bump `last_seen_at`, `seen_count`; leave `first_seen_at` untouched.
- **Poll record always written**, including on error — that's how per-source health surfaces later.
- **Concurrency:** serial with rate limit. 181 sources × ~200ms ≈ 40s per run, well under the PRD's 5-minute budget.
- **Exit code:** 0 on partial failure, 2 on config error, 1 on unhandled exception.
- **Summary line:** `feeds: polled 181 sources, 178 ok, 2 4xx, 1 5xx, 892 new items in 41.3s`.

### 7.5 `ingest/import_discover_file.py`

- `python -m discover_intel import-discover [--file X] [--watch] [--force-reimport] [--dry-run]`.
- **Auto-detection:** reads the first row, matches against `header_signature` in `config/discover_import_mappings.yaml`. No match → exits 2 with `Unknown export format. Headers seen: [...]. Add a mapping in config/discover_import_mappings.yaml.`
- **Timestamp:** parsed via `filename_regex` or `timestamp_from: header_row_col`. Parse failure → refuses to import.
- **Idempotency:** `obs_id = sha1(tool + '|' + market + '|' + observed_at + '|' + coalesce(url, title))`. Same file re-imported → no new rows.
- **Watch mode:** `--watch` scans `data/imports/discover/`, processes each file, moves to `data/imports/discover/processed/YYYY-MM/` with `imported_at` suffix. Failed files → `data/imports/discover/failed/`. No long-lived process — Task Scheduler re-invokes every 15 min.
- **Summary line:** `import-discover: 1 file, 47 obs new, 0 dup, DiscoverTrends_2026-09-23_1547.csv → observed_at=2026-09-23T15:47:00Z`.

**Mapping file** (`config/discover_import_mappings.yaml`):

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

### 7.6 `ingest/import_snapshot.py`

- `python -m discover_intel import-snapshot [--file X] [--stdin] [--taken-at ISO]`. Manual only — no Task Scheduler entry.
- Accepts xlsx-like format from Sheet2 (`channel_as_listed, category, tier, visibility_2h, posts, time_on_feed, matched_channel_name, channel_url, channel_id, match_confidence`) or tsv/csv paste. Writes to `discover_snapshots`.
- Helpers: `parse_kmb("547.79K") → 547790.0`; `parse_hm("2h 0m") → 120.0`.
- Idempotency: `snapshot_id = sha1(taken_at + '|' + market + '|' + host_or_channel)`.

### 7.7 `ingest/gsc_discover.py`

- `python -m discover_intel gsc [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--dry-run]`.
- Defaults: `end = yesterday (UTC)`, `start = end - 3 days` (rolling 3-day re-pull because GSC restates late).
- Reads `GSC_SA_JSON` and `GSC_PROPERTY` env vars. `google-api-python-client` with `webmasters` v3. Search Analytics API: `type=discover`, dimensions `[date, country, device, page]`, filter `country=usa`, page size 25000, paginates.
- Upserts on compound PK. Restatements overwrite existing rows.
- **Explicit remediation messages** on 403 (SA not added to property) and 404 (property URL wrong). Doesn't silently write empty rows.
- Summary line: `gsc: pulled 2026-09-19..2026-09-22, 4123 rows upserted (usa, 3 devices, 892 pages)`.

### 7.8 `ops/backup.py`

- `python -m discover_intel backup`: SQLite online-backup API (`conn.backup(target)`) → `data/backups/warehouse-YYYY-MM-DD.db`. Keeps last 14 dailies + weekly Sundays indefinitely. Safe while writers active.
- `python -m discover_intel vacuum`: `VACUUM` (weekly, Sunday 03:30 local). WAL checkpointed first. Refuses if today's backup doesn't exist unless `--force`.

## 8. Failure model (all modules)

- **Per-item errors are logged and skipped.** Never crash a job because one feed entry has a malformed date.
- **Per-file errors move the file to `failed/`.** The job continues with remaining files.
- **Never invent data.** Missing timestamp → refuse import. Missing env var → refuse to run.
- **Always write a poll/import record** even on total failure. Downstream health monitoring depends on this.
- **Exit codes:** 0 partial-success, 2 config error, 1 unhandled exception. Task Scheduler only alerts on non-zero.

## 9. Windows Task Scheduler wiring

Seven tasks, all created by `scripts\register-tasks.ps1`. Principal: **logged-in user** (S4U — "run whether logged on or not", "do not store password"). Start-in path: repo root.

| Task | Cadence | Wrapper |
|---|---|---|
| `DiscoverIntel_Feeds` | every 30 min | `run-feeds.ps1` (logs to `feeds.log`) |
| `DiscoverIntel_YouTube` | every 60 min | `run-youtube.ps1` (logs to `youtube.log`) |
| `DiscoverIntel_ImportDiscover` | every 15 min | `run-import-discover.ps1 -Watch` |
| `DiscoverIntel_GSC` | daily 04:00 local | `run-gsc.ps1` |
| `DiscoverIntel_Backup` | daily 03:00 local | `run-backup.ps1` |
| `DiscoverIntel_Vacuum` | Sunday 03:30 local | `run-vacuum.ps1` |
| `DiscoverIntel_DBStats` | daily 06:00 local | `run-dbstats.ps1` |

**Task settings:**
- "If the task fails, restart every 5 min up to 3 times."
- "If the computer is on battery, run anyway."
- "If the task is missed, run at next available time." ← the whole reason Task Scheduler was chosen over APScheduler.
- Compatibility: `AT2019` (Windows 10/11).
- `-NoProfile -NonInteractive -ExecutionPolicy Bypass` on every PowerShell invocation.

**Wrapper pattern** (identical shape across all wrappers; only the `-m discover_intel <cmd>`, `--kind` value, and log file name differ):

```powershell
# run-feeds.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$log  = Join-Path $root "logs\feeds.log"
$ts   = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC
try {
  & "$root\.venv\Scripts\python.exe" -m discover_intel feeds `
      --db "$root\data\warehouse.db" --kind "web,gnews_site,gnews_query,gnews_section" 2>&1 |
    Tee-Object -FilePath $log -Append | Out-Null
  "[${ts}] feeds exit=$LASTEXITCODE" | Add-Content $log
  exit $LASTEXITCODE
} catch {
  "[${ts}] feeds wrapper-error: $_" | Add-Content $log
  exit 1
}
```

`run-youtube.ps1` is the same shape with `--kind "youtube"` and `logs\youtube.log`. Same for the other five wrappers. Consistent shape means one bug fixed once fixes them all.

## 10. Secrets & configuration

- **`GSC_SA_JSON`** = `C:\Users\Anil.Kumar6\Desktop\My Inteligence System\ga4-mcp-504403-c72f94fdfd37 (2).json`. Set via `setx GSC_SA_JSON "..."`. Persists across sessions.
- **`GSC_PROPERTY`** — TBD; format `https://economictimes.indiatimes.com/` or `sc-domain:economictimes.indiatimes.com`. Code refuses to run without it.
- **The JSON stays at its current path outside the repo.** Do not move it inside. `.gitignore` includes `*.json` in `secrets/` and `data/` as belt-and-suspenders.
- **README.md** carries a "First-time setup" checklist: venv, `pip install`, `setx GSC_SA_JSON`, `setx GSC_PROPERTY`, `init-db`, `seed-sources`, `register-tasks.ps1`. Total: ~5 min.

## 11. Logging

- One log file per module in `logs/`: `feeds.log`, `youtube.log`, `import-discover.log`, `gsc.log`, `backup.log`, `vacuum.log`, `dbstats.log`.
- Python: `logging.basicConfig(level=INFO, format='%(asctime)sZ %(levelname)s %(name)s %(message)s')`, `RotatingFileHandler` (10 MB × 5 kept).
- Last line of every job is the PRD-required summary.
- PowerShell wrapper appends an exit-code line and a wrapper-error line if it blew up.
- No stdout in scheduled runs. Dev mode: `--verbose` mirrors to stderr.

## 12. Testing

- **Zero network in tests.** Fixtures under `tests/fixtures/`:
  - `google_news_rss_sample.xml` — captured during dev
  - `native_rss_sample.xml`
  - `youtube_atom_sample.xml`
  - `discovertrends_2026-09-23_1509.csv` and `_1547.csv` — user's actual files
  - `marfeel_sample.xlsx` — placeholder; tests skip until a real Marfeel export is available
  - `d2tr_snapshot_sample.tsv` — derived from xlsx Sheet2
- **HTTP mocking:** `pytest-httpx`.
- **DB fixture:** fresh `:memory:` SQLite per test with `apply_schema` applied.
- **GSC:** mock `google-api-python-client` with canned responses. Verify upserts + 403 remediation message.
- **Speed:** entire suite < 5s.
- **Ruff config** in `pyproject.toml`: `line-length = 100`, rules `E, F, I, N, UP, B, SIM`, project rule: no `print()` outside `cli.py`.
- **Type hints** on public functions. `mypy --strict` on `src/discover_intel/` as a nice-to-have, not a hard gate.
- **Not tested in Sprint 1:** real network fetches (deferred to `--dry-run` smoke test in README); real GSC calls (deferred to first real run after prerequisites satisfied).

## 13. Acceptance criteria

Sprint 1 is done when all of the following pass:

1. **`python -m discover_intel init-db`** — creates `data/warehouse.db` with all six tables and applied `user_version=1`.
2. **`python -m discover_intel seed-sources --xlsx "C:\Users\Anil.Kumar6\Downloads\USA Top Publishers.xlsx"`** — writes three CSVs into `config/`, with 20-ish web + 50-ish gnews + ~98 youtube rows.
3. **`python -m discover_intel feeds --dry-run`** — prints per-source URL and status, ≥ 95% return 200/301/302. Any 4xx flagged clearly for user review.
4. **`python -m discover_intel feeds`** — populates `items` and `feed_polls` from a real run; ends in < 5 min.
5. **`python -m discover_intel import-discover --file "C:\Users\Anil.Kumar6\Downloads\DiscoverTrends_2026-09-23_1547.csv"`** — writes rows into `discover_articles` with `observed_at = 2026-09-23T15:47:00Z`.
6. **Re-running (5)** — inserts 0 new rows (idempotent).
7. **`python -m discover_intel gsc --dry-run`** — validates env vars, prints planned query. (Actual run deferred until GSC prerequisites done.)
8. **`python -m discover_intel db-stats`** — prints non-zero counts for `sources`, `items`, `feed_polls`, `discover_articles`.
9. **`.\scripts\register-tasks.ps1`** — installs 7 tasks; `Get-ScheduledTask -TaskName "DiscoverIntel_*"` shows them Ready.
10. **`pytest tests/ -q`** — all tests pass in < 5s.

## 14. Dependencies (initial `pyproject.toml`)

- `httpx[http2]` — feed fetches
- `feedparser` — RSS/Atom parsing
- `openpyxl` — xlsx reading (seed-sources)
- `PyYAML` — mapping file
- `google-api-python-client`, `google-auth` — GSC API
- `python-dateutil` — timestamp parsing edge cases
- Dev: `pytest`, `pytest-httpx`, `ruff`, `mypy`

No unnecessary dependencies. No web framework (Sprint 3). No spaCy (Sprint 2). No pandas (small data — direct sqlite3 is fine).

## 15. Open questions still to resolve (non-blocking)

1. `GSC_PROPERTY` exact form — user provides at first-run time.
2. ABC7 News and Fox Weather YouTube channel IDs — user fills in `sources_youtube.csv` post-seed.
3. Marfeel real export headers — mapping remains a placeholder until we have a sample.
4. Native RSS supplements that 403 from ET infra — deferred; will show up in `feed_polls.http_status`, then user manually disables offenders via `enabled=0`.
