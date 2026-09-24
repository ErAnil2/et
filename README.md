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
   → writes `config\sources_{web,gnews,youtube}.csv`. Real counts: **24 web + 50 gnews + 94 youtube**.

3. `python -m discover_intel feeds --db data\warehouse.db --kind web,gnews_site,gnews_query,gnews_section --dry-run`
   → prints per-source URLs. Manually verify ≥ 95% look sane.

4. `python -m discover_intel feeds --db data\warehouse.db --kind web,gnews_site,gnews_query,gnews_section`
   → real run; ends in < 5 min. Prints one summary line.

5. `python -m discover_intel import-discover --db data\warehouse.db --file "C:\Users\Anil.Kumar6\Downloads\DiscoverTrends_2026-09-23_1547.csv"`
   → writes **320 rows** into `discover_articles`, `observed_at = 2026-09-23T15:47:00Z`.

6. Re-run (5). Expected: `0 new, 320 dup`.

7. `python -m discover_intel gsc --db data\warehouse.db --dry-run`
   → validates env vars, prints the planned query. (Real run works after the two
   GSC prerequisites are done.)

8. `python -m discover_intel db-stats --db data\warehouse.db`
   → prints `sources=N items=M feed_polls=P discover_articles=320 discover_snapshots=0 gsc_discover=0`.

9. `.\scripts\register-tasks.ps1` → registers 7 tasks;
   `Get-ScheduledTask -TaskName "DiscoverIntel_*"` shows them all `Ready`.

10. `pytest tests\ -q` — all tests pass in < 30s.

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

---

## Sprint 2 (Analysis)

Sprint 2 layers derived analytics onto the Sprint 1 warehouse: URL resolution,
outcome matching, entity/lane/format tagging, and TOI Discover-attributed
traffic as a second market-truth signal.

**Spec:** `docs/superpowers/specs/2026-09-24-sprint-2-analysis-design.md`.
**Plan:** `docs/superpowers/plans/2026-09-24-sprint-2-analysis.md`.

### Sprint 2 first-time setup

```powershell
# 1. Reinstall to pick up the new deps declared in pyproject.toml v0.2
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
# Optional: LLM fallback via Claude Code SDK
pip install -e ".[llm]"

# 2. Download spaCy model (~50 MB, one-time)
python -m spacy download en_core_web_md

# 3. Persist TOI GA environment variables
setx TOI_GA_SA_JSON "C:\Users\Anil.Kumar6\Desktop\My Inteligence System\ga4-mcp-504403-c72f94fdfd37 (2).json"
setx TOI_GA_PROPERTY_ID "230487101"

# 4. Reapply the schema (idempotent — adds v2 tables if missing)
python -m discover_intel init-db --db data\warehouse.db

# 5. Reinstall scheduled tasks (adds 4 new ones)
.\scripts\register-tasks.ps1
```

**Prerequisites for TOI GA (off-code, one-time):**

1. Enable **Google Analytics Data API** in Google Cloud project `ga4-mcp-504403`
   (Console → APIs & Services → Library).
2. Add `claude-ga-mcp@ga4-mcp-504403.iam.gserviceaccount.com` as **Viewer** on
   GA4 property `230487101` (analytics.google.com → Admin → Property Access
   Management).

Until both are done, `discover_intel toi-ga` will 403 with a remediation message.

### Sprint 2 acceptance smoke commands

1. `python -m discover_intel resolve-urls --db data\warehouse.db --limit 500`
   → fills `items.canonical_url` for Google News URLs. ≥90% within 3 runs.

2. `python -m discover_intel match-outcomes --db data\warehouse.db --since 72`
   → prints `known-host match rate: NN.N%`. Target ≥ 70%.

3. `python -m discover_intel tag-entities --db data\warehouse.db --source both --limit 5000`
   → populates `item_entities`.

4. `python -m discover_intel toi-ga --db data\warehouse.db --dry-run`
   → validates env vars, prints planned request.

5. `python -m discover_intel db-stats --db data\warehouse.db`
   → now shows non-zero counts for `item_outcomes` and `item_entities`.

6. `.\scripts\register-tasks.ps1` → installs all 11 tasks (7 Sprint 1 + 4 Sprint 2).

7. `pytest tests\ -q` → all tests pass.

---

## Sprint 3 (Scoring & Delivery)

Sprint 3 layers scoring + delivery onto the Sprint 2 tagged warehouse:
hourly topic aggregation (S3-A), TOS ranking (S3-B), pre-publish DRS
(S3-C), twice-daily Markdown digest (S3-D-1), and a 5-tab Streamlit
dashboard (S3-D-2).

**Spec:** `docs/superpowers/specs/2026-09-24-sprint-3-scoring-delivery-design.md`.
**Plan:** `docs/superpowers/plans/2026-09-24-sprint-3-scoring-delivery.md`.

### Sprint 3 first-time setup

```powershell
# 1. Reinstall to pick up v0.3 deps (streamlit, plotly, jinja2)
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 2. Reapply schema (idempotent - adds v3 tables if missing)
python -m discover_intel init-db --db data\warehouse.db

# 3. Reinstall scheduled tasks (adds 3 new ones)
.\scripts\register-tasks.ps1
```

**No new external prerequisites** — Sprint 3 uses only the warehouse
and configuration files (`config/scoring.yaml`, `config/clickbait_patterns.txt`).
Tune scoring weights and thresholds in `config/scoring.yaml` without
touching Python.

### Sprint 3 acceptance smoke commands

1. `python -m discover_intel build-topic-stats --db data\warehouse.db` → populates `topic_stats`.

2. `python -m discover_intel tos --db data\warehouse.db` → populates `topic_scores`. Prints counts per threshold tier.

3. `python -m discover_intel drs --title "Fed cuts rates by 25 bps as Powell signals slower path" --image-width 1600 --author "Jane Doe" --published-at 2026-09-24T15:00:00Z --db data\warehouse.db` → prints DRS score (≥60 expected); writes to `article_scores`.

4. `python -m discover_intel drs --title "You won't believe what happened next..." --image-width 1600 --author "Jane Doe" --published-at 2026-09-24T15:00:00Z --db data\warehouse.db` → DRS < 70 (headline component = 0 due to clickbait pattern).

5. `python -m discover_intel digest --db data\warehouse.db` → writes `data\digests\<UTC>.md` + `data\digests\latest.md`. Up to 15 topics ≥ TOS 60.

6. `python -m discover_intel dashboard --db data\warehouse.db` → launches Streamlit on http://localhost:8501; 5 tabs render.

7. `python -m discover_intel db-stats --db data\warehouse.db` → shows non-zero counts for topic_stats, topic_scores, article_scores.

8. `.\scripts\register-tasks.ps1` → installs all 14 tasks; `Get-ScheduledTask -TaskName "DiscoverIntel_*"` shows them all `Ready`.

9. `pytest tests\ -q` — all Sprint 1 + 2 + 3 tests pass.

### Tuning knobs

- **`config/scoring.yaml`** — TOS weights, DRS weights, thresholds (publish, watchlist, DRS gate), headroom curve, timing decay, producible formats, YMYL lanes, suggested headline patterns.
- **`config/clickbait_patterns.txt`** — one regex per line; DRS headline check reads at startup.

---

## Sprint 4 (Scorecard)

Sprint 4 adds a weekly measurement scorecard: three metrics — market
precision, ET conversion, coverage trends — materialised as Markdown
artifacts (`data/scorecards/YYYY-Www.md`) and persisted to a new
`scorecards` table for query.

**Spec:** `docs/superpowers/specs/2026-09-24-sprint-4-scorecard-design.md`.

### Sprint 4 first-time setup

```powershell
# 1. Reapply schema (idempotent — adds scorecards table + bumps user_version to 4)
python -m discover_intel init-db --db data\warehouse.db

# 2. Reinstall scheduled tasks (adds 1 more)
.\scripts\register-tasks.ps1
```

No new deps, no new env vars.

### Sprint 4 acceptance smoke commands

1. `python -m discover_intel scorecard --db data\warehouse.db --week 2026-W39 --dry-run` → renders Markdown to stdout, no DB write.

2. `python -m discover_intel scorecard --db data\warehouse.db --week 2026-W39` → writes `data\scorecards\2026-W39.md` + `data\scorecards\latest.md`, inserts a `scorecards` row.

3. Re-run (2) — same iso_week — `INSERT OR REPLACE` overwrites, still 1 row.

4. `python -m discover_intel db-stats --db data\warehouse.db` → lists `scorecards=N`.

5. `.\scripts\register-tasks.ps1` → installs all 15 tasks; `Get-ScheduledTask -TaskName "DiscoverIntel_*"` shows them Ready.

6. `pytest tests\ -q` — all Sprint 1 + 2 + 3 + 4 tests pass.
