# Discover Intelligence System — Sprint 3 (Scoring & Delivery) Design

**Date:** 2026-09-24
**Owner:** Anil Kumar (etaitools@timesinternet.in) — ET Growth / SEO
**Status:** Design approved, ready for implementation plan
**Scope:** Sprint 3 — topic aggregation, TOS scoring, DRS scoring, Markdown digest, Streamlit dashboard (5 tabs including an early Scorecard).
**Depends on:** Sprint 1 (ingestion) and Sprint 2 (analysis) — this spec assumes the warehouse is being populated + tagged.
**Sprint 1 spec:** `docs/superpowers/specs/2026-09-23-sprint-1-ingestion-design.md`.
**Sprint 2 spec:** `docs/superpowers/specs/2026-09-24-sprint-2-analysis-design.md`.
**PRD:** `C:\Users\Anil.Kumar6\Downloads\PRD.md` (S3 section).

---

## 1. Purpose

Turn Sprint 2's tagged warehouse into two things editors can act on:

- **A ranked list of topic opportunities** (Topic Opportunity Score, TOS) — twice-daily Markdown digest of the top-15 topics ET should write about, with evidence and suggested formats.
- **A pre-publish quality gate** (Discover Readiness Score, DRS) — a CLI that takes a draft article and returns 0–100 with per-component findings. Gate at DRS ≥ 70.

Plus a **Streamlit dashboard** for humans who want to see feed composition, competitor velocity, lane coverage, and early scorecard metrics.

## 2. Resolved decisions

Six forks resolved with the user before this design was locked in.

1. **Full Sprint 3 in one pass.** All 4 pieces (aggregator + TOS + DRS + Slack + Streamlit dashboard). Larger than Sprint 2 but coherent because everything reads from the same warehouse.
2. **Markdown-only digest — no Slack webhook.** Digest module writes `data/digests/YYYY-MM-DDTHH.md` files. Named `slack_digest.py` per PRD nomenclature; may later grow a webhook branch when `SLACK_WEBHOOK_US` env is set.
3. **All 5 dashboard tabs including Scorecard.** Scorecard is Sprint-4 territory but implemented in Sprint 3 with graceful degradation — market precision computed from what's in the DB, ET conversion shows "N/A" when GSC is empty.
4. **Fixed UTC digest cadence: 11:00 and 17:00 UTC.** Slightly earlier than 07:00/13:00 Eastern during EDT, exactly aligned during EST. Trades ~1h drift for DST-agnostic scheduling. Aligns with Windows Task Scheduler's UTC-friendly trigger primitives.
5. **All weights, thresholds, curves in `config/scoring.yaml`.** Nothing hard-coded in scoring code. This is the tuning surface for the intelligence layer.
6. **Sprint 3 topic_scores keeps history.** Every scoring run creates new rows; PK includes `scored_at`. Sprint 4 scorecard reads this for "topic X was in digest on date Y; did it show up in Discover within 48h?"

## 3. Non-goals

- **No Slack posting yet.** Deferred until user provides a webhook.
- **No feedback loop from Scorecard into scoring weights.** PRD § 8 non-goal — humans decide weight changes after ≥4 weekly scorecards.
- **No CMS integration.** Digest is Markdown files; dashboard is a local Streamlit web app. Both are read/paste-friendly, not machine-integrated.
- **No LLM in scoring.** Only rule-based components. LLM stays confined to Sprint 2's tagger fallback.
- **No production hosting.** Dashboard runs locally on the user's Windows machine. No deployment pipeline, no auth, no HTTPS.

## 4. Prerequisites (already met from Sprint 2)

- Sprint 2 modules producing `item_entities`, `item_outcomes`, and `taxonomy` rows.
- `sources`, `items`, `feed_polls`, `discover_articles`, `gsc_discover` populated by Sprint 1 jobs.

Nothing new is required off-code for Sprint 3.

## 5. Repo additions

```
discover-intel/
├─ pyproject.toml                  # + streamlit, plotly, jinja2
├─ sql/schema.sql                  # + topic_stats, topic_scores, article_scores; user_version 2→3
├─ config/
│   ├─ scoring.yaml                # NEW — all TOS/DRS weights, thresholds, curves
│   └─ clickbait_patterns.txt      # NEW — one regex per line for DRS headline check
├─ src/discover_intel/
│   ├─ analysis/
│   │   └─ build_topic_stats.py    # S3-A hourly aggregates → topic_stats
│   ├─ scoring/                    # NEW package
│   │   ├─ __init__.py
│   │   ├─ tos.py                  # S3-B Topic Opportunity Score (5 components → topic_scores)
│   │   └─ drs.py                  # S3-C Discover Readiness Score (6 components → article_scores)
│   ├─ delivery/                   # NEW package
│   │   ├─ __init__.py
│   │   ├─ slack_digest.py         # S3-D-1 Markdown digest → data/digests/*.md
│   │   └─ dashboard.py            # S3-D-2 Streamlit 5-tab dashboard
│   └─ cli.py                      # + build-topic-stats, tos, drs, digest, dashboard subcommands
├─ scripts/
│   ├─ run-build-topic-stats.ps1   # NEW
│   ├─ run-tos.ps1                 # NEW
│   ├─ run-digest.ps1              # NEW
│   ├─ register-tasks.ps1          # extend: 3 more scheduled tasks (BuildTopicStats, TOS, Digest)
│   └─ unregister-tasks.ps1        # extend: 3 more names
├─ data/digests/                   # NEW — Markdown output directory (gitignored via data/)
└─ tests/                          # + tests per new module
```

**Key layout decisions:**

- **`scoring/` and `delivery/` are new top-level packages** distinct from `analysis/`. Scoring = pure algorithm (warehouse-in, score+evidence out). Delivery = output generation (scores-in, humans-consumable-artifacts out).
- **DRS lives in `scoring/`** alongside TOS despite being operationally independent (draft-in, score-out, no warehouse read for most components). Shared config-loading pattern and both consume `scoring.yaml` — co-location wins over strict separation.
- **Dashboard is manual-launch.** No scheduled task; long-running Streamlit process.
- **Digest is Markdown-only per fork 2.** Module named `slack_digest.py` (matches PRD nomenclature). Writes `data/digests/YYYY-MM-DDTHH.md` + a `latest.md` copy.

## 6. Data model additions

`PRAGMA user_version = 3`. Three new tables. Sprint 1+2 tables untouched.

```sql
PRAGMA user_version = 3;

-- Written by S3-A build_topic_stats.py. Rolling 72h snapshot per (hour, market, entity).
-- INSERT OR REPLACE on the compound PK — recomputed each run.
CREATE TABLE IF NOT EXISTS topic_stats (
  hour_utc              TEXT NOT NULL,
  market                TEXT NOT NULL,
  entity                TEXT NOT NULL,
  new_items             INTEGER NOT NULL DEFAULT 0,
  competitor_hosts      INTEGER NOT NULL DEFAULT 0,
  gnews_query_hits      INTEGER NOT NULL DEFAULT 0,
  discover_obs          INTEGER NOT NULL DEFAULT 0,
  discover_visibility   REAL NOT NULL DEFAULT 0.0,
  avg_time_on_feed_min  REAL,
  winning_format        TEXT,
  PRIMARY KEY (hour_utc, market, entity)
);
CREATE INDEX IF NOT EXISTS idx_topic_stats_market_hour ON topic_stats(market, hour_utc DESC);
CREATE INDEX IF NOT EXISTS idx_topic_stats_entity     ON topic_stats(entity, hour_utc DESC);

-- Written by S3-B scoring/tos.py. One row per scoring run per (market, entity). History preserved.
CREATE TABLE IF NOT EXISTS topic_scores (
  scored_at         TEXT NOT NULL,
  market            TEXT NOT NULL,
  entity            TEXT NOT NULL,
  tos               REAL NOT NULL,
  momentum          REAL NOT NULL,
  headroom          REAL NOT NULL,
  timing            REAL NOT NULL,
  format_match      REAL NOT NULL,
  lane_fit          REAL NOT NULL,
  suggested_format  TEXT,
  evidence_json     TEXT NOT NULL,
  PRIMARY KEY (scored_at, market, entity)
);
CREATE INDEX IF NOT EXISTS idx_topic_scores_market_at ON topic_scores(market, scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_topic_scores_tos       ON topic_scores(tos DESC, scored_at DESC);

-- Written by S3-C scoring/drs.py. One row per pre-publish check.
CREATE TABLE IF NOT EXISTS article_scores (
  scored_at     TEXT NOT NULL,
  draft_id      TEXT NOT NULL,
  drs           REAL NOT NULL,
  headline      REAL NOT NULL,
  image         REAL NOT NULL,
  eeat          REAL NOT NULL,
  originality   REAL NOT NULL,
  timeliness    REAL NOT NULL,
  technical     REAL NOT NULL,
  findings_json TEXT NOT NULL,
  PRIMARY KEY (scored_at, draft_id)
);
CREATE INDEX IF NOT EXISTS idx_article_scores_draft ON article_scores(draft_id, scored_at DESC);
CREATE INDEX IF NOT EXISTS idx_article_scores_drs   ON article_scores(drs DESC, scored_at DESC);
```

**Non-obvious decisions:**

- **`topic_stats` PK is (hour_utc, market, entity)** — one row per hour per entity per market. Recomputed each run; `INSERT OR REPLACE` overwrites. History lives in `topic_scores`, not here. Keeps `topic_stats` bounded (~168h × 500 entities × 1 market ≈ 84k rows).
- **`topic_scores` keeps history** — every scoring run creates new rows. Sprint 4 scorecard reads this for market-precision measurement.
- **`evidence_json` and `findings_json`** — humans need to see WHY a topic scored high, not just a number. PRD § 7.5 mandates this: "The digest must show evidence, not just a number." JSON is flexible; consumers extract what they need.
- **`suggested_format` on topic_scores** — computed at scoring time from `winning_format` of the entity's most recent `topic_stats`, filtered against `producible_formats` in scoring.yaml. Stored on the row so the digest doesn't rejoin.
- **`article_scores.draft_id`** — URL when DRS has `--url`, else `sha1(title)`. Same headline scored twice gets the same draft_id; history preserved via `scored_at`.

## 7. Component contracts

Every module honors Sprint 1/2 discipline: `--db`, `--dry-run` where writing, `--limit`, idempotent, one-line summary log, UTC everywhere, exit codes {0, 2, 1}.

### 7.1 S3-A · `analysis/build_topic_stats.py`

CLI: `python -m discover_intel build-topic-stats --db X [--market US] [--window-hours 72] [--dry-run]`.

- **Reads:** `items`, `item_entities`, `item_outcomes`, `discover_articles`, `sources`.
- **Groups:** by `(hour_bucket, market, entity)` where `hour_bucket = strftime('%Y-%m-%dT%H:00:00Z', first_seen_at)`, over trailing `--window-hours`.
- **Computes:**
  - `new_items`: `COUNT(DISTINCT item_id)` mentioning entity, first-seen in that hour
  - `competitor_hosts`: `COUNT(DISTINCT items.host)` mentioning entity in last 24h
  - `gnews_query_hits`: same but filtered to `sources.kind IN ('gnews_query','gnews_section')`
  - `discover_obs`: `COUNT(DISTINCT obs_id)` via `item_outcomes` join
  - `discover_visibility`: `SUM(discover_articles.visibility)`
  - `avg_time_on_feed_min`: `AVG(discover_articles.time_on_feed_min)` — NULL if all obs lack it
  - `winning_format`: format with `MAX(SUM(visibility))` over trailing 72h
- **Writes:** `INSERT OR REPLACE INTO topic_stats`.
- **Idempotent:** re-running produces the same rows (deterministic on warehouse state).
- **Summary log:** `build-topic-stats: 72h × 340 entities × US = 4127 rows in 8.3s`.

### 7.2 S3-B · `scoring/tos.py`

CLI: `python -m discover_intel tos --db X [--market US] [--dry-run]`.

- **Reads:** `topic_stats` + `item_entities` + `taxonomy` (for `in_et_lane`) + `scoring.yaml`.
- **Component computation** (all normalised 0-1 as rank-percentile within the market's candidate set at scoring time, then weighted):
  - **`momentum` (0.30):** `pct(new_items_6h / max(1, mean(new_items_per_6h prior_48h)))`. Blended 50/50 with `pct(discover_visibility_24h / max(1, discover_visibility_prior_72h/3))` when Discover data exists for the entity.
  - **`headroom` (0.25):** lookup table on `competitor_hosts_24h` from `scoring.yaml:headroom_curve`. Peak at 3-6 hosts (=1.0), 0-1 → 0.4, 7-10 → 0.6, >10 → 0.2.
  - **`timing` (0.20):** `pct(avg_time_on_feed_min) × exp(-hours_since_first_seen / 18)`. Decay constant from `scoring.yaml`.
  - **`format_match` (0.15):** `1.0` if `winning_format ∈ producible_formats`. `0.5` if `winning_format` is NULL/unknown. `0.0` if `winning_format ∈ penalty_formats (trivia, quote)` **and** no news-hook signal (entity absent from breaking-news formats in last 6h).
  - **`lane_fit` (0.10):** `1.0` if any `item_entities.taxonomy_id` for this entity has `in_et_lane=1` on the linked `taxonomy` row. Else `0.3`. Rule-based, never learned.
- **TOS:** `100 × Σ(w_i × c_i)`. Publish threshold and watchlist threshold both in `scoring.yaml`.
- **`suggested_format`:** `winning_format` if in `producible_formats`, else "news" as safe default.
- **`evidence_json`:** top-3 Discover titles for the entity (from matched `discover_articles`, ordered by `visibility DESC`), plus the competitor hosts publishing in last 24h, plus the beat queries (`sources.kind='gnews_query'` sources) that fired for this entity. Serialised as JSON string.
- **Writes:** `INSERT OR REPLACE INTO topic_scores`.
- **Idempotent per `scored_at`:** re-running at the same second produces the same rows; different seconds produce new rows (history preserved).
- **Summary log:** `tos: 340 entities scored, 47 publish (>=60), 62 watchlist (45-60), 231 below in 4.1s`.

### 7.3 S3-C · `scoring/drs.py`

CLI: two forms. Both take an optional `--db` (defaults to `data/warehouse.db`) which is used for `timeliness` (needs `topic_scores` lookup) and `originality` (needs `items` for same-entity title comparison). Other components don't require the DB.

- `python -m discover_intel drs --title "..." --image-width 1600 --author "..." --published-at 2026-09-24T15:00:00Z [--url https://...] [--body-file path] [--db data/warehouse.db]`
- `python -m discover_intel drs --json draft.json [--db data/warehouse.db]` (same fields as JSON dict)

If `--db` points at a missing or empty warehouse, `timeliness` defaults to 0.5 and `originality` defaults to 1.0 (with reasons logged in `findings_json`) — DRS still returns a score. This keeps DRS usable during Sprint 1-only bootstraps.

**Six components** (each 0-1, then weighted):

- **`headline` (0.25):**
  - Length 40 ≤ chars ≤ 110 (else 0)
  - Contains ≥1 named entity (via spaCy NER on the headline) AND ≥1 number or concrete fact
  - **Fails (0)** if any pattern in `config/clickbait_patterns.txt` matches
- **`image` (0.25):**
  - `--image-width` ≥ 1200 (else 0)
  - Reject 1:1 aspect (logo). Accept ≈16:9 or ≈4:3.
  - If `--url` given, HEAD-check the URL for `<meta name="max-image-preview" content="large">` in the HTML head. Bonus if present. `httpx` HEAD (10s timeout, rate-limited via Sprint 1 TokenBucket).
- **`eeat` (0.20):**
  - Named `--author` present (author != "" and not "Staff" boilerplate)
  - `--published-at` valid ISO
  - If `--body-file`, count links: ≥1 external citation
  - YMYL topic (lane matches `ymyl_lanes` in scoring.yaml) → author required strictly, else `eeat = 0`
- **`originality` (0.15):**
  - `1 − max(rapidfuzz.token_set_ratio / 100)` of the headline against `items.title` on the same entity in last 48h
  - If no comparable competitor titles found, `originality = 1.0`
- **`timeliness` (0.10):**
  - `1.0` if entity has current TOS ≥ 45 (query `topic_scores` for latest run for this entity)
  - Decays to 0 at 36h after entity's peak (peak = when TOS was maximum in last 168h)
  - `0.5` if entity not found in topic_scores at all
- **`technical` (0.05):**
  - Only checkable with `--url`. Default 0.5 if no URL.
  - With `--url`: check canonical is set (parse HTML head), no interstitial redirects, indexable (no `noindex` meta).

**DRS:** `100 × Σ(w_i × c_i)`. Gate: `DRS ≥ 70` per `scoring.yaml:drs.gate`.

**Findings:** per-component `{component: {value: 0.85, reasons: ["headline: 87 chars ✓", "has entity 'Fed' ✓", "has number '25 bps' ✓", "no clickbait patterns hit ✓"]}}`. Stored as JSON, printed as a human-readable table on stdout.

Writes: `INSERT OR REPLACE INTO article_scores`. Also prints:
```
DRS: 82 (PASS ≥70)
  headline    0.90  (40-110 chars ✓, entity present ✓, number present ✓, clickbait-clean ✓)
  image       1.00  (1600×900 ≥1200 ✓, aspect 16:9 ✓)
  eeat        0.75  (author "Jane Doe" ✓, date ✓, 2 body links ✓)
  originality 0.68  (max fuzzy 0.32 vs competitor "Fed hints 25bp cut on Sept 24")
  timeliness  0.95  (entity TOS 78 ≥45, hours from peak: 2)
  technical   0.50  (no --url given)
```

### 7.4 S3-D-1 · `delivery/slack_digest.py`

CLI: `python -m discover_intel digest --db X [--top 15] [--out data/digests/] [--dry-run]`.

- **Reads:** most recent `topic_scores` batch (`WHERE scored_at = (SELECT MAX(scored_at) FROM topic_scores)`), top-N by `tos DESC`, filtered `tos ≥ scoring.yaml:tos.thresholds.publish`.
- **Renders Markdown** via jinja2 template. For each topic:
  ```markdown
  ## <entity>  ·  TOS <score>

  **Suggested format:** <suggested_format>

  **Why:** <top Discover title from evidence_json> (<top host>). Also winning on
  <N> competitor hosts; beat queries firing: <up to 2 firing queries>.

  **Headline pattern:** <template from scoring.yaml:suggested_headline_patterns>
  ```
- **Writes:** `data/digests/<UTC-timestamp>.md` (e.g. `2026-09-24T11:00Z.md`). Fixed UTC 11:00 and 17:00 per fork 2B.
- **Also writes:** `data/digests/latest.md` (overwrite each run) — easy access to current digest.
- **`--dry-run`:** renders to stdout, doesn't write files.
- **Summary log:** `digest: wrote data/digests/2026-09-24T11:00Z.md — 15 topics, TOS range 63-89`.

### 7.5 S3-D-2 · `delivery/dashboard.py`

CLI: `python -m discover_intel dashboard --db X [--port 8501]`. Long-running Streamlit process. **No Task Scheduler entry** — launched manually.

Wrapping: `python -m streamlit run <path-to-dashboard.py> -- --db X --port 8501`.

**Five tabs** (Streamlit `st.tabs()`):

1. **Opportunities.** Filter: latest `topic_scores` where `tos ≥ scoring.yaml:tos.thresholds.watchlist` (45). Sortable dataframe columns: `entity | tos | suggested_format | discover_visibility | new_items_24h | evidence_preview`. Row expansion shows full `evidence_json` pretty-printed.
2. **Feed composition.** Two plotly charts:
   - **Host share:** bar chart of `items` counts per `host` in last 24h (top 30 hosts).
   - **Per-post efficiency:** for each host, avg `discover_articles.visibility` / distinct matched `items` (only where >0 matches exist).
3. **Competitor velocity.** Plotly line chart of items/hour per host, last 7 days. Y-axis = item count, X-axis = time. Legend selectable (Streamlit multiselect).
4. **Lane coverage.** Two side-by-side plotly bar charts:
   - **Items published per lane** (from `item_entities` filtered to `taxonomy_id LIKE 'lane:%'`).
   - **Discover visibility captured per lane** (join through `item_outcomes` to `discover_articles.visibility`).
   Diff between the two = "under/over-invested lanes."
5. **Scorecard (S4-early per fork F1A):**
   - **Market precision:** for the last 7 daily digests, % of digest topics that appeared in `discover_articles` (any tool) within 48h of `topic_scores.scored_at`. Displayed as a running line chart + latest-run headline number.
   - **ET conversion:** for `items.host = 'economictimes.indiatimes.com'` matched to a digest topic (via `item_outcomes` → `topic_scores`), average `gsc_discover.impressions` and `.clicks` vs the average for ET items *not* on the digest. Displays as two-column comparison. If `gsc_discover` is empty, shows: *"GSC not populated — run `discover_intel gsc` after prerequisites are done. See README."*

**Charts:** plotly (cleaner tooltips than Streamlit's built-ins). Data loaded per tab render — no caching layer; queries are cheap on this size warehouse.

### 7.6 Failure model

Same as Sprint 1/2:
- Per-entity/per-topic errors logged and skipped; scoring continues.
- Every module writes a summary line even on partial failure.
- TOS: if a specific component computation fails (rare, e.g., division by zero when `topic_stats` is empty), that component becomes 0.0 and the failure reason is included in `evidence_json`. TOS never crashes the entire run.
- DRS: if `--url` HEAD fails, `technical` and `image.max-image-preview` fall back to defaults; the score still computes.

## 8. Ops

### 8.1 Three new PowerShell wrappers (Sprint 1/2 shape)

| Wrapper | Log file | Command |
|---|---|---|
| `scripts\run-build-topic-stats.ps1` | `logs\build-topic-stats.log` | `python -m discover_intel build-topic-stats --db data\warehouse.db --window-hours 72` |
| `scripts\run-tos.ps1` | `logs\tos.log` | `python -m discover_intel tos --db data\warehouse.db` |
| `scripts\run-digest.ps1` | `logs\digest.log` | `python -m discover_intel digest --db data\warehouse.db --top 15 --out data\digests` |

DRS has no wrapper — invoked per-draft. Dashboard has no wrapper — launched manually.

### 8.2 Three new Task Scheduler entries

Appended to `scripts\register-tasks.ps1`. Total: 7 (Sprint 1) + 4 (Sprint 2) + 3 (Sprint 3) = **14 tasks**.

| Task name | Cadence | UTC time / offset | Wrapper |
|---|---|---|---|
| `DiscoverIntel_BuildTopicStats` | every **2 h** | +45 min offset from resolver | `run-build-topic-stats.ps1` |
| `DiscoverIntel_TOS`             | every **2 h** | +60 min offset (top of next hour) | `run-tos.ps1` |
| `DiscoverIntel_Digest`          | **twice daily** | 11:00 UTC and 17:00 UTC | `run-digest.ps1` (single task, two triggers) |

Chain in the same 2-hour window (starting from Sprint 2's :00 resolver):
`ResolveUrls (:00) → MatchOutcomes (:15) → TagEntities (:30) → BuildTopicStats (:45) → TOS (:00 of next hour) → Digest fires at fixed UTC.`

### 8.3 First-time setup addition

```powershell
# Reinstall to pick up new pyproject.toml v0.3 deps (streamlit, plotly, jinja2)
pip install -e ".[dev]"

# Reapply schema (adds v3 tables if missing)
python -m discover_intel init-db --db data\warehouse.db

# Reinstall scheduled tasks (adds 3 new ones)
.\scripts\register-tasks.ps1
```

Optional environment variable:
```powershell
setx STREAMLIT_PORT "8501"    # dashboard port override
```

## 9. Configuration content

### 9.1 `config/scoring.yaml`

```yaml
tos:
  weights: { momentum: 0.30, headroom: 0.25, timing: 0.20, format_match: 0.15, lane_fit: 0.10 }
  thresholds: { publish: 60.0, watchlist: 45.0 }
  headroom_curve:
    "0": 0.40; "1": 0.40; "2": 0.80; "3": 1.00; "4": 1.00; "5": 1.00; "6": 1.00
    "7": 0.60; "8": 0.60; "9": 0.60; "10": 0.60
    default: 0.20
  timing: { freshness_decay_hours: 18.0 }
  format_match:
    producible: [news, analysis, atmosphere, service]
    unknown_value: 0.5
    penalty_formats: [trivia, quote]
    penalty_value: 0.0
  lane_fit: { in_lane_value: 1.0, out_of_lane_value: 0.3 }
  suggested_headline_patterns:
    news:       "{entity}: {fact}"
    analysis:   "Why {entity}'s {topic} matters for {audience}"
    atmosphere: "Inside {entity}: {angle}"
    service:    "How {entity} affects {your_thing}: what to do"
    default:    "{entity}: {angle}"

drs:
  weights: { headline: 0.25, image: 0.25, eeat: 0.20, originality: 0.15, timeliness: 0.10, technical: 0.05 }
  gate: 70.0
  headline:
    min_chars: 40
    max_chars: 110
    require_entity_and_fact: true
    clickbait_patterns_file: config/clickbait_patterns.txt
  image:
    min_width_px: 1200
    reject_square_aspect_ratio: true
    check_max_image_preview_large: true
  eeat:
    ymyl_lanes: [personal_finance_benefits, finance_markets, health_medicine]
    require_author_ymyl: true
  originality:
    fuzzy_threshold_max: 0.85
  timeliness:
    entity_tos_floor: 45.0
    decay_hours_from_peak: 36.0
  technical:
    without_url_default: 0.5
```

(Actual YAML syntax normalised — the `"0": 0.40; "1": 0.40; ...` block is shorthand; will be written as one-key-per-line in the real file.)

### 9.2 `config/clickbait_patterns.txt`

Seed derived from PRD § 7.5 + common Discover-penalised patterns:

```
you won'?t believe
you won'?t guess
this one (weird|simple|crazy) trick
what happened next
you'?ll never guess
this (man|woman|kid|couple) (found|did|discovered)
these (\d+) things? (will|can) shock
number \d+ will (shock|surprise|blow)
\.\.\.\s*$
^[^.!?]+\?\s*$
guess what
here'?s why (you|everyone)
```

Loaded by DRS at startup; compiled with `re.IGNORECASE`. Editorial adds/removes lines without code changes.

## 10. Dependencies (delta on `pyproject.toml`)

Additions:
```toml
[project.dependencies]
# ... Sprint 1+2 deps unchanged ...
"streamlit>=1.40,<2.0",
"plotly>=5.24,<6.0",
"jinja2>=3.1.4,<4.0",
```

## 11. Testing (Sprint 3)

Same discipline as Sprint 1/2 — no network in tests, fixture-based.

- **`test_build_topic_stats.py`** — DB fixture seeds `items` + `item_entities` + `item_outcomes` + `discover_articles` with known counts; verify aggregation SQL produces expected rows.
- **`test_tos.py`** — synthetic `topic_stats` rows spanning momentum/headroom/timing edge cases; verify each component formula independently, then combined TOS. Verify `evidence_json` content.
- **`test_drs.py`** — hand-crafted headlines covering pass/fail for every component:
  - Clean headline: `"Fed cuts rates by 25 bps as Powell signals slower path"` → high score.
  - Clickbait: `"You won't believe what happened next..."` → headline=0.
  - Short: `"Fed cut"` → headline=0 (< 40 chars).
  - Long: 130-char title → headline=0.
- **`test_slack_digest.py`** — populate `topic_scores`; run digest; parse output Markdown; assert top-N entries present with TOS scores + evidence.
- **`test_dashboard.py`** — data-loading functions tested as pure functions of the DB; smoke test that imports `dashboard.py` and calls tab-render functions with a canned DB.
- **`test_scoring_yaml.py`** — verify all keys present, TOS weights sum to 1.0, DRS weights sum to 1.0, headroom curve values in [0,1], gate/threshold values sensible.

Runtime: full Sprint 3 test suite < 20s.

## 12. Acceptance criteria (Sprint 3)

1. **`python -m discover_intel build-topic-stats --db data\warehouse.db`** — populates `topic_stats` (row count depends on tagged item volume; on a warehouse with Sprint 2 output, expect hundreds of rows).
2. **`python -m discover_intel tos --db data\warehouse.db`** — populates `topic_scores`. Summary line prints counts by threshold tier.
3. **`python -m discover_intel drs --title "Fed cuts rates by 25 bps as Powell signals slower path" --image-width 1600 --author "Jane Doe" --published-at 2026-09-24T15:00:00Z --db data\warehouse.db`** — prints DRS output, writes to `article_scores`, DRS should be ≥70.
4. **`python -m discover_intel drs --title "You won't believe what happened next..." --image-width 1600 --author "Jane Doe" --published-at 2026-09-24T15:00:00Z --db data\warehouse.db`** — DRS < 70 (headline component = 0 due to clickbait pattern).
5. **`python -m discover_intel digest --db data\warehouse.db`** — writes `data\digests\<UTC>.md` + `data\digests\latest.md`. Contains up to 15 topics ≥ TOS 60.
6. **`python -m discover_intel dashboard --db data\warehouse.db`** — starts Streamlit on localhost:8501. All 5 tabs render; Scorecard tab shows N/A for ET conversion if `gsc_discover` is empty.
7. **`python -m discover_intel db-stats --db data\warehouse.db`** — shows non-zero counts for `topic_stats`, `topic_scores`, `article_scores`.
8. **`.\scripts\register-tasks.ps1`** — installs all 14 tasks; `Get-ScheduledTask -TaskName "DiscoverIntel_*"` shows them all `Ready`.
9. **`pytest tests\ -q`** — all Sprint 1 + Sprint 2 + Sprint 3 tests pass in < 60s.

## 13. Deferred (Sprint 4 or later)

- **Slack webhook integration.** Digest module has a webhook branch reserved; fires only when `SLACK_WEBHOOK_US` env is set. Not built in Sprint 3.
- **Feedback loop from Scorecard into scoring weights.** Weights stay static in `scoring.yaml`; human decision after ≥4 weekly scorecards.
- **Historical scorecard reports.** Sprint 3's dashboard shows the latest scorecard; Sprint 4 will add weekly scorecard artifacts (`data/scorecards/YYYY-WW.md`).

## 14. Open questions still to resolve (non-blocking)

1. **First real TOS runs will need tuning.** The headroom curve, timing decay, and threshold values (publish=60, watchlist=45) are educated guesses. Sprint 3 ships them as-is; first real digest will surface which entities look right and which don't. Weights adjust via `scoring.yaml` edits.
2. **Suggested headline patterns are placeholders.** Editorial should own the template list; Sprint 3 seeds them from format-typical shapes. Update via `scoring.yaml` when editorial has preferred patterns.
3. **Streamlit dashboard styling.** Uses Streamlit's default theme. If editorial wants ET-branded colors, that's a mini-task via `.streamlit/config.toml`.
4. **YMYL lane list.** Seeded from Sprint 2's lane slugs (`personal_finance_benefits`, `finance_markets`, `health_medicine`). Editorial can expand via `scoring.yaml` if additional lanes need YMYL strictness.
