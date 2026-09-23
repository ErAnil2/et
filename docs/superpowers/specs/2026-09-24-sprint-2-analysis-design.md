# Discover Intelligence System — Sprint 2 (Analysis) Design

**Date:** 2026-09-24
**Owner:** Anil Kumar (etaitools@timesinternet.in) — ET Growth / SEO
**Status:** Design approved, ready for implementation plan
**Scope:** Sprint 2 — Google News URL resolver, outcome matcher, entity/topic tagger, plus TOI GA Discover-traffic importer as a new external "market truth" signal. Sprint 3 (scoring/TOS/DRS/delivery) and Sprint 4 (scorecard) are out of scope for this spec.
**Depends on:** Sprint 1 (ingestion) — this spec assumes a working warehouse populated by Sprint 1's feeds/importers.
**Sprint 1 spec:** `docs/superpowers/specs/2026-09-23-sprint-1-ingestion-design.md`.
**PRD:** `C:\Users\Anil.Kumar6\Downloads\PRD.md` (S2 section).

---

## 1. Purpose

Turn Sprint 1's raw warehouse (feed items + discover observations) into a queryable "who won and why" dataset. Three derived operations plus one new external data source:

- **S2-A resolve URLs:** decode / follow Google News redirect URLs to fill `items.canonical_url`.
- **S2-B match outcomes:** link `discover_articles` (what Google Discover rewarded) to `items` (what publishers actually posted) via a URL → canonical → title-exact → title-fuzzy cascade.
- **S2-C tag entities:** run every title (item and discover observation) through spaCy NER + a 23-lane keyword classifier + a format-inference rule engine. Optional LLM fallback for hard cases.
- **S2-D TOI GA importer:** pull Times of India's Discover-attributed traffic via the Google Analytics Data API and store it as `discover_articles` rows with `tool='toi_ga'`.

Nothing in Sprint 2 scores, ranks, or ships. It builds the substrate Sprint 3's TOS/DRS/delivery reads from.

## 2. Resolved decisions

Six forks were resolved with the user before this design was locked in.

1. **Comprehensive theme coverage, US-only, no ET-bias filtering.** All 23 lanes get `in_et_lane=1` at seed time — the tagger classifies every story into whatever theme it fits. Whether ET competes in a lane is a Sprint-3 scoring concern (flip `in_et_lane=0` on specific lanes via SQL later), not a Sprint-2 tagging concern. US-only geography carries forward via the existing `market` column in the schema; UK becomes a config flip later.
2. **Lanes derived from real data, not the PRD's frozen list.** Analysed 820 real DiscoverTrends observations to identify 23 comprehensive lanes across money, government, culture, tech/science, curiosities, and hyperlocal. Zero ET-side data touched — pure market signal.
3. **URL resolver = decode-first, HEAD-fallback.** Try to base64-decode the Google News article id (fast, offline, ~90% success rate); fall back to `HEAD` request with 2-hop redirect follow on decode failure. Rate-limited (5 req/s, 10s timeout, never retry 4xx per PRD).
4. **LLM tagging via Claude Code Python SDK.** `claude-code-sdk` used for the optional `--llm` fallback pass. Uses your Claude Code subscription (no per-token billing). Fallback path documented as CLI subprocess if the SDK proves flaky. Off by default — activates only on items where the rule-based tagger produced zero hits.
5. **Format rules derived from real 820 titles.** Ordered regex list mapping title patterns to `news | analysis | atmosphere | service | trivia | opinion`. Trivia checked first (distinctive "In YYYY..." pattern); `news` is the default catchall.
6. **TOI GA as competitor intelligence, direct API integration.** TOI is Times Internet family but has an independent SEO strategy — using their Discover-attributed GA traffic is market signal, not internal bias. Direct `google-analytics-data` (v1beta) call using the existing shared service-account JSON (same file as GSC). GA4 property ID: `230487101`. Not manual CSV export — programmatic via env-configured credentials.

## 3. Non-goals

- **No scoring** (TOS, DRS). Sprint 3.
- **No delivery** (Slack, dashboard). Sprint 3.
- **No feedback loop from ET's own performance** into the tagger or into `in_et_lane`. ET's GSC (Sprint 1) and TOI's GA (Sprint 2) both feed only into observation storage; neither is a training input for lane assignment.
- **No dependency on Sprint 3 features.** The `--llm` pass in Sprint 2's tagger uses a placeholder gate ("zero rule hits") instead of Sprint 3's `tos_candidate=1` gate. Sprint 3 will replace the gate.
- **No Marfeel-format handling changes.** Sprint 1's Marfeel placeholder mapping stays; still no real export to test against.

## 4. Prerequisites (user, off-code)

Same shared service account as GSC. Two new prerequisites, non-blocking for coding:

1. **Enable "Google Analytics Data API" (`analyticsdata.googleapis.com`)** in Google Cloud project `ga4-mcp-504403`. Console → APIs & Services → Library → search "Google Analytics Data API" → Enable.
2. **Add the service account as Viewer on the TOI GA4 property.** analytics.google.com → Admin → Property Access Management (under Property `230487101`) → Add users → paste `claude-ga-mcp@ga4-mcp-504403.iam.gserviceaccount.com` → **Viewer** role.

The TOI GA importer 403s with a remediation message until both are done.

## 5. Repo additions

No Sprint 1 files are removed or restructured. Sprint 2 additions:

```
discover-intel/
├─ pyproject.toml                        # + spacy, rapidfuzz, google-analytics-data
│                                        # + optional-dependencies.llm = [claude-code-sdk]
├─ sql/schema.sql                        # + item_outcomes, taxonomy, item_entities
│                                        # + PRAGMA user_version = 2
├─ config/
│   ├─ lane_keywords.yaml                # NEW — 23 lanes with regex patterns
│   ├─ entity_aliases.csv                # NEW — ~30 canonical mappings
│   └─ format_rules.yaml                 # NEW — ordered pattern → format map
├─ src/discover_intel/
│   ├─ analysis/                         # NEW package (derived-data operations)
│   │   ├─ __init__.py
│   │   ├─ resolve_urls.py               # S2-A
│   │   ├─ match_outcomes.py             # S2-B
│   │   └─ tag_entities.py               # S2-C
│   ├─ ingest/
│   │   └─ toi_ga.py                     # NEW — S2-D
│   └─ cli.py                            # extend: 4 new subcommands
├─ scripts/                              # + 4 new wrappers
│   ├─ run-resolve-urls.ps1
│   ├─ run-match-outcomes.ps1
│   ├─ run-tag-entities.ps1
│   ├─ run-toi-ga.ps1
│   ├─ register-tasks.ps1                # extend: +4 tasks
│   └─ unregister-tasks.ps1              # extend: +4 names
├─ data/llm_cache/                       # NEW — content-hash disk cache for LLM outputs
├─ tests/                                # + tests for every new module
└─ README.md                             # extend: Sprint 2 setup + acceptance
```

**Key layout decisions:**

- **`analysis/` is a new package** distinct from `ingest/`. Resolver/matcher/tagger read the warehouse and write derived tables — they aren't external-data importers.
- **`toi_ga.py` lives in `ingest/`** because it pulls from an external system (GA Data API), same category as `gsc_discover.py`.
- **spaCy model is a runtime dependency, not a package dependency.** `en_core_web_md` (~50 MB) is downloaded via `python -m spacy download en_core_web_md` as a first-time-setup step. Tests use `en_core_web_sm` (smaller, faster) via a swap-in.
- **`claude-code-sdk` is optional.** Base install works without it; `--llm` flag on the tagger errors with an install hint if missing. Kept out of the base install so cron jobs stay lean.
- **`data/llm_cache/`** — content-addressed on-disk cache for LLM outputs (keyed by `sha1(title)`). Prevents re-classifying the same title across runs. Gitignored (already covered by Sprint 1's `data/`-wide ignore).

## 6. Data model additions

`PRAGMA user_version = 2`. Three new tables. Sprint 1 tables untouched — `CREATE TABLE IF NOT EXISTS` no-ops on existing ones.

```sql
PRAGMA user_version = 2;

-- Written by S2-B match_outcomes.py.
-- One row per (item, discover_observation) match. Best-match cascade fills match_type/score.
CREATE TABLE IF NOT EXISTS item_outcomes (
  item_id       TEXT NOT NULL REFERENCES items(item_id),
  obs_id        TEXT NOT NULL REFERENCES discover_articles(obs_id),
  match_type    TEXT NOT NULL CHECK (match_type IN ('url','canonical','title_exact','title_fuzzy')),
  match_score   REAL NOT NULL,          -- 1.0 for stages 1-3; 0.85-1.0 for title_fuzzy
  matched_at    TEXT NOT NULL,          -- ISO UTC of the match run
  PRIMARY KEY (item_id, obs_id)
);
CREATE INDEX IF NOT EXISTS idx_item_outcomes_obs  ON item_outcomes(obs_id);
CREATE INDEX IF NOT EXISTS idx_item_outcomes_type ON item_outcomes(match_type);

-- Seeded from config/lane_keywords.yaml on startup (idempotent upserts).
-- Kind='lane' | 'format' | 'entity_type'. Slug taxonomy_id like 'lane:tech_ai'.
CREATE TABLE IF NOT EXISTS taxonomy (
  taxonomy_id   TEXT PRIMARY KEY,       -- 'lane:tech_ai', 'format:analysis', etc.
  kind          TEXT NOT NULL CHECK (kind IN ('lane','format','entity_type')),
  label         TEXT NOT NULL,          -- human label: 'Tech & AI'
  parent_id     TEXT,                   -- for hierarchies later; NULL in Sprint 2
  in_et_lane    INTEGER NOT NULL DEFAULT 1  -- comprehensive tagging by default; flip=0 via SQL if editorial excludes
);

-- Written by S2-C tag_entities.py. Serves both items and discover observations
-- through a source_key prefix ('item:<id>' or 'obs:<id>').
CREATE TABLE IF NOT EXISTS item_entities (
  entry_id      TEXT PRIMARY KEY,       -- sha1(source_key + '|' + entity + '|' + coalesce(taxonomy_id,''))
  source_key    TEXT NOT NULL,          -- 'item:<item_id>' or 'obs:<obs_id>'
  entity        TEXT NOT NULL,          -- normalised entity string
  entity_type   TEXT,                   -- spaCy label: PERSON|ORG|GPE|PRODUCT|EVENT — NULL for lane/format tags
  taxonomy_id   TEXT,                   -- FK to taxonomy; NULL for raw NER entities
  confidence    REAL NOT NULL,          -- 1.0 rule/spaCy; 0.0-1.0 LLM-scored
  tagged_at     TEXT NOT NULL           -- ISO UTC
);
CREATE INDEX IF NOT EXISTS idx_item_entities_source ON item_entities(source_key);
CREATE INDEX IF NOT EXISTS idx_item_entities_ent    ON item_entities(entity);
CREATE INDEX IF NOT EXISTS idx_item_entities_tax    ON item_entities(taxonomy_id);
```

**Non-obvious decisions:**

- **`item_outcomes` PK is (item_id, obs_id).** One item can win Discover multiple times (multiple obs across days); one obs can theoretically match multiple items via title-fuzz. `ON CONFLICT DO NOTHING` at insert time keeps the best cascade stage (stage 1 writes first, later stages don't overwrite).
- **`taxonomy.taxonomy_id` is a slug, not a UUID.** Human-inspectable, stable across re-seeds. `<kind>:<slug>` format disambiguates `lane:sports_athletics` from `format:opinion`.
- **`item_entities.source_key` uses a prefix** so one table serves items and discover observations. Sprint 3's TOS aggregator does two prefix-filtered queries; no split needed.
- **`in_et_lane` defaults to 1** across all 23 lanes seeded from config — comprehensive tagging. Editorial can flip individual lanes to 0 via SQL if a strategic decision is made later. No code change required.
- **`confidence` column** — Sprint 2 writes `1.0` for rule/spaCy hits, and the LLM's own confidence score (0.0-1.0) for LLM outputs. Sprint 3 can weight low-confidence tags less in TOS.
- **Adding these tables to a Sprint-1 warehouse is safe.** `db.apply_schema()` is already idempotent (it just `executescript`s the whole file). `CREATE TABLE IF NOT EXISTS` no-ops on existing tables; only the three new ones get created. `PRAGMA user_version = 2` overwrites the old 1. No code change needed to `db.py`.
- **Sprint 1's schema.sql reserved-names comment lists `item_outcomes, taxonomy` for Sprint 2 but omits `item_entities`.** Sprint 1 was slightly under-specified here. Sprint 2 updates the comment as part of the schema task; nothing else changes.

## 7. Component contracts

Every module honors Sprint 1's discipline: `--db` required, `--dry-run` where they write, `--limit` on batch loops, idempotent re-runs, one-line summary log, UTC everywhere, exit codes {0=partial-success, 2=config-error, 1=unhandled-exception}.

### 7.1 S2-A · `analysis/resolve_urls.py`

CLI: `python -m discover_intel resolve-urls --db data\warehouse.db [--limit 500] [--dry-run]`.

- **Selection:** `SELECT ... FROM items WHERE canonical_url IS NULL AND url LIKE 'https://news.google.com/rss/articles/%' ORDER BY first_seen_at DESC LIMIT ?`.
- **Decoder path:** the Google News article id path segment is a URL-safe base64 of a small protobuf-like blob containing the original URL string. A regex-tolerant extractor pulls the first `https?://…` substring out of the decoded bytes. On success → use it.
- **HEAD fallback:** if decode returns nothing usable, call `httpx.Client.head(url, follow_redirects=True)` with the Sprint-1 rate-limiter (`TokenBucket`, 5 req/s). Read `response.url` as the final URL. Max 2 hops (`httpx` default). 10s timeout. Never retry 4xx per PRD.
- **Post-processing:** run resolved URL through `util.url.strip_tracking()` (removes utm_*, fbclid, gclid, fragment).
- **Persistence:** `UPDATE items SET canonical_url = ? WHERE item_id = ?`. Idempotent because selection filters `canonical_url IS NULL`. Never overwrites once set.
- **Failure handling:** per-item errors logged, canonical_url stays NULL, next run retries. Never invent a URL.
- **Summary log:** `resolve-urls: 847 candidates, 763 decoded, 71 HEAD-resolved, 13 failed in 12.4s`.
- **Test strategy:** unit tests use canned base64 blobs (fixture file with a few real GN-shaped strings); HEAD-fallback branch uses `pytest-httpx` mocks.

### 7.2 S2-B · `analysis/match_outcomes.py`

CLI: `python -m discover_intel match-outcomes --db data\warehouse.db [--since 72] [--dry-run]`.

Four-stage cascade, best-match-wins:

1. **`url`** — `WHERE strip_tracking(items.url) = strip_tracking(discover_articles.url)`.
2. **`canonical`** — `WHERE strip_tracking(items.canonical_url) = strip_tracking(discover_articles.url)`.
3. **`title_exact`** — `WHERE items.host = discover_articles.host AND items.title_hash = <normalised-title-hash of obs.title>`.
4. **`title_fuzzy`** — `WHERE items.host = obs.host AND rapidfuzz.token_set_ratio(items.title, obs.title) / 100 >= 0.85 AND items.first_seen_at BETWEEN obs.observed_at - 48h AND obs.observed_at + 48h`.

- **Scope:** only `discover_articles` with `observed_at >= now - ?since ? h`. Default 72. Keeps runs fast.
- **Persistence:** `INSERT OR IGNORE INTO item_outcomes ...`. First (best) stage wins; later stages that would produce the same (item_id, obs_id) key are no-ops. `match_score` is `1.0` for stages 1–3, the rapidfuzz ratio for stage 4.
- **Summary log:** `match-outcomes: 512 obs new, 428 matched (89 url, 141 canonical, 156 title_exact, 42 title_fuzzy), 84 unmatched, 6.1s`. Also prints the acceptance ratio: `known-host match rate: 82.7%`.
- **PRD acceptance for Sprint 2 (§ 12):** ≥ 70% of `discover_articles` **with a known host** matched to an `item`. "Known host" = observation host appears in `sources.host` for any enabled source. The summary line reports this ratio.
- **Test strategy:** DB-fixture based; seed items + discover_articles pairs for each match_type; verify the matcher picks the best cascade stage.

### 7.3 S2-C · `analysis/tag_entities.py`

CLI: `python -m discover_intel tag-entities --db data\warehouse.db [--source items|obs|both] [--limit 5000] [--llm] [--dry-run]`.

**Three parallel taggers**, all applied to every source row:

1. **spaCy NER** — `en_core_web_md` extracts entities of type `PERSON | ORG | GPE | PRODUCT | EVENT`. Each entity → one `item_entities` row with `entity_type=<label>`, `taxonomy_id=NULL`, `confidence=1.0`.
2. **Lane classifier** — reads `config/lane_keywords.yaml` (23 lanes). Each regex hit → one row with `taxonomy_id='lane:<slug>'`, `entity_type=NULL`, `confidence=1.0`. Multiple lane hits per row are expected and correct.
3. **Format inference** — reads `config/format_rules.yaml`. First matching rule wins. One row with `taxonomy_id='format:<slug>'`. On `discover_articles`, if the source already has a `format` column value (Marfeel does; DiscoverTrends doesn't), the vendor label wins and the rule engine is skipped for that row.

**Normalisation before any tagger runs:**
- Lowercase.
- Strip honorifics (Mr./Mrs./Dr./…).
- Apply `config/entity_aliases.csv` map (e.g., "Fed" → "Federal Reserve", "Musk" → "Elon Musk"). Loaded once per run as `dict[str, str]`.

**Optional LLM pass (`--llm` flag):**
- Gate: rows where the rule-based classifier produced zero hits (neither lane nor format matched). Sprint 3 will replace this gate with `tos_candidate=1`.
- Uses `claude-code-sdk`. Prompt: title text + list of the 23 lane slugs, format list, entity-type list. Response contract: JSON `{"lanes": ["slug", ...], "format": "slug", "entities": [{"text": "...", "type": "PERSON"}, ...]}`. JSON-only enforced by prompt.
- Cache: `data/llm_cache/<sha1(title)>.json` on disk. Cache hits bypass the API.
- Budget cap: 500 calls per run (PRD). Log a warning if hit; drop remaining candidates.
- Fallback path (documented, not implemented in Sprint 2): if SDK misbehaves, swap to `subprocess.run(['claude', '-p', prompt, '--output-format', 'json'])`.
- If `claude-code-sdk` isn't installed and `--llm` was passed, exit 2 with `pip install -e ".[llm]"` hint.

**Idempotency:** `entry_id = sha1(source_key + '|' + entity + '|' + coalesce(taxonomy_id, ''))`. Re-tagging the same source produces the same entry_ids → INSERT OR IGNORE no-ops. Only items new to this run get new tags.

**Selection:** only source rows that don't yet have any `item_entities` row for them. Adding a new lane later requires an explicit `--force-retag` (deferred).

**Summary log:** `tag-entities: 1240 items + 320 obs, 4127 entities (2410 NER, 1503 lanes, 214 formats), 0 LLM, 8.9s`.

**Test strategy:** DB-fixture based; test titles with known lane/format matches; use `en_core_web_sm` in tests (faster load); mock `claude-code-sdk` for LLM path via `unittest.mock.patch`.

### 7.4 S2-D · `ingest/toi_ga.py`

CLI: `python -m discover_intel toi-ga --db data\warehouse.db [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--dry-run]`.

- **Env:** `TOI_GA_SA_JSON` (path to shared credentials JSON) and `TOI_GA_PROPERTY_ID` (=`230487101`). Refuses to run without both. Explicit 403/404 remediation messages on API errors (same pattern as `gsc_discover.py`).
- **Query:** `google-analytics-data` v1beta `BetaAnalyticsDataClient.run_report()`:
  - `property = 'properties/230487101'`
  - `dimensions = [Dimension(name=n) for n in ['date', 'pagePath', 'pageTitle', 'sessionSource', 'sessionMedium', 'deviceCategory']]`
  - `metrics = [Metric(name=m) for m in ['sessions', 'engagedSessions', 'engagementRate', 'screenPageViews']]`
  - `dimension_filter = FilterExpression(and_group=FilterExpressionList(expressions=[filter_source_google, filter_medium_discover]))`
  - `date_ranges = [DateRange(start_date=start, end_date=end)]`
- **Defaults:** `end = yesterday (UTC).date()`, `start = end - 3 days` (rolling — GA data settles ~48h).
- **Persistence:** each returned row → an INSERT into `discover_articles`:
  - `tool = 'toi_ga'`
  - `market = 'US'`
  - `observed_at = <row.date>T00:00:00Z`
  - `title = row.pageTitle`
  - `url = 'https://timesofindia.indiatimes.com' + row.pagePath`
  - `host = 'timesofindia.indiatimes.com'`
  - `visibility = row.sessions` (numeric; GA doesn't return a "score" — sessions is the closest analog)
  - `raw_json = <all-row-metrics-serialised>`
  - `obs_id = sha1('toi_ga|US|<observed_at>|<url>')`
- **Restatements:** `INSERT ... ON CONFLICT(obs_id) DO UPDATE SET visibility=excluded.visibility, raw_json=excluded.raw_json, imported_at=excluded.imported_at`. Same behaviour as GSC's restatement upsert.
- **`--dry-run`** — validates env + prints planned request, doesn't hit the API.
- **Test strategy:** mock the `BetaAnalyticsDataClient` (or its Client factory) with `unittest.mock.patch`, canned `RunReportResponse` object.

## 8. Failure model (Sprint 2)

Same discipline as Sprint 1. Per-item / per-row errors log-and-skip. Never invent data. Every module writes a summary line even on partial failure. Exit codes {0, 2, 1}. Task Scheduler only alerts on non-zero.

Two module-specific behaviours worth noting:

- **`resolve_urls.py`:** if both decode and HEAD fail for a specific URL, `canonical_url` stays NULL and the row will be retried on the next run. Not marked as "resolution failed" — the resolver is optimistic and just tries again later. Only permanently-4xx URLs stop being retried (they stay NULL forever, which is correct — the story never had a live canonical).
- **`match_outcomes.py`:** if the acceptance ratio (known-host match rate) drops below 70% on a run, log a WARNING but exit 0. Sprint 3's dashboard will surface this; not a cron-fail condition.

## 9. Ops — Task Scheduler additions

Four new scheduled tasks appended to Sprint 1's seven (total = 11 after Sprint 2). PowerShell wrappers follow the exact shape of Sprint 1's — `[DateTime]::UtcNow` timestamp, per-module log file, exit-code line appended, wrapper-error line on catch.

| Task name | Cadence | Local time | Wrapper | Notes |
|---|---|---|---|---|
| `DiscoverIntel_ResolveUrls`  | every **2 h** (from now) | rolling         | `run-resolve-urls.ps1`   | `--limit 500` keeps runs bounded |
| `DiscoverIntel_MatchOutcomes`| every **2 h** (+15 min offset) | rolling  | `run-match-outcomes.ps1` | `--since 72` |
| `DiscoverIntel_TagEntities`  | every **2 h** (+30 min offset) | rolling  | `run-tag-entities.ps1`   | `--source both --limit 5000` |
| `DiscoverIntel_ToiGa`        | daily                    | 04:30 local     | `run-toi-ga.ps1`         | after GSC 04:00 |

The 15-minute offsets on the three 2-hour tasks preserve the dependency order (resolve → match → tag) without needing job chaining. If a run is missed, Task Scheduler's "run at next available time" catches it.

`register-tasks.ps1` is amended with 4 more `Register-DI` calls at the bottom before the summary print. `unregister-tasks.ps1`'s `$names` array grows by 4. Both remain idempotent.

## 10. Configuration content (summary)

Three new config files. The full content is generated as part of Task-1 of the implementation plan.

- **`config/lane_keywords.yaml`** — 23 blocks of `{slug, label, pattern}`. Patterns are Python-regex, compiled at load. Each pattern is a mix of entity keywords (e.g., `\bkroger\b`) and semantic keywords (e.g., `\bmansion\b`). Derived from the 820 real DiscoverTrends observations you supplied.
- **`config/entity_aliases.csv`** — ~30 mappings (`alias, canonical`). Case-insensitive lookup applied during normalisation before NER/lane tagging.
- **`config/format_rules.yaml`** — ordered list of `{format, pattern, reason}`. First match wins. `trivia` checked first (distinctive "In YYYY..." pattern); `news` is the default catchall.

## 11. Dependencies (delta on `pyproject.toml`)

Additions:
```toml
[project.dependencies]
# ... Sprint 1 dependencies unchanged ...
"spacy==3.7.6",
"rapidfuzz==3.10.1",
"google-analytics-data==0.18.16",

[project.optional-dependencies]
llm = ["claude-code-sdk>=0.0.10"]
dev = [
  # ... Sprint 1 dev deps ...
]
```

Plus a first-time-setup step: `python -m spacy download en_core_web_md` (~50 MB, one-time).

## 12. Testing (Sprint 2)

Same discipline as Sprint 1: no network in tests; fixture files under `tests/fixtures/`.

- **`test_resolve_urls.py`** — canned base64 blobs in `tests/fixtures/gnews_encoded_urls.txt`; `pytest-httpx` mocks for HEAD fallback.
- **`test_match_outcomes.py`** — DB-fixture based; seed known-pair rows for each cascade stage; verify best-match cascade.
- **`test_tag_entities.py`** — DB-fixture based; use `en_core_web_sm` for speed via a `conftest.py`-level swap; LLM path uses `unittest.mock.patch('discover_intel.analysis.tag_entities.claude_code_sdk_call')`.
- **`test_toi_ga.py`** — mock `BetaAnalyticsDataClient` with canned `RunReportResponse`; verify persistence and idempotency.
- **Type hints on public functions.** `mypy --strict` on `src/discover_intel/analysis/`.
- **Runtime:** whole Sprint 2 test suite < 15s (spaCy model load is the slow part; `en_core_web_sm` in tests keeps it fast).

## 13. Acceptance criteria (Sprint 2)

Adapted from PRD § 12 (Sprint 2 row) and grounded in real data:

1. **`python -m discover_intel resolve-urls`** — runs against the current warehouse; ≥ 90% of the `items.url` starting with `news.google.com/rss/articles/` end up with a non-NULL `canonical_url` within 3 runs.
2. **`python -m discover_intel match-outcomes`** — the printed acceptance ratio is ≥ 70% (per PRD).
3. **`python -m discover_intel tag-entities`** — `SELECT count(*) FROM items WHERE item_id NOT IN (SELECT DISTINCT substr(source_key, 6) FROM item_entities WHERE source_key LIKE 'item:%')` returns ≤ 10% of `items` — i.e., ≥ 90% of items have at least one entity/lane/format tag (per PRD).
4. **`python -m discover_intel toi-ga --dry-run`** — validates env vars, prints planned request. Real run works after the two off-code prerequisites are done.
5. **`python -m discover_intel db-stats`** — shows non-zero `item_outcomes` and `item_entities` counts alongside the Sprint 1 tables.
6. **`.\scripts\register-tasks.ps1`** — installs all 11 tasks (7 Sprint 1 + 4 Sprint 2); `Get-ScheduledTask -TaskName "DiscoverIntel_*"` shows them all `Ready`.
7. **`pytest tests\ -q`** — all Sprint 1 + Sprint 2 tests pass in < 30s.

**Deferred (Sprint 3 gates):**
- Lane classifier ≥ 85% agreement with a 200-row hand-labelled sample. The hand-label happens *after* first real run, so it's grounded in actual data, not synthetic.

## 14. Open questions still to resolve (non-blocking)

1. **When does the LLM fallback pass actually fire?** Sprint 2 uses "zero rule hits" as the gate. Sprint 3 will replace this with `tos_candidate=1` — logged as a Sprint-3 to-do.
2. **How does the lane classifier's accuracy hold up on real data?** Deferred to a manual 200-row hand-label after first live run.
3. **Should `taxonomy.in_et_lane=0` for `trivia_history_novelty` be flipped by editorial?** Not a code decision. Left to human review after Sprint 3 shows the format-penalty in TOS scoring.
4. **Marfeel real-export headers** — still unresolved. Mapping remains a placeholder until an export exists.
