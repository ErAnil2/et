# Discover Intelligence System — Sprint 4 (Scorecard) Design

**Date:** 2026-09-24
**Owner:** Anil Kumar (etaitools@timesinternet.in) — ET Growth / SEO
**Status:** Design approved, ready for implementation plan
**Scope:** Sprint 4 — weekly measurement scorecard. Single module (`analysis/scorecard.py`) that materialises three metrics on a schedule and persists them.
**Depends on:** Sprints 1-3.
**PRD:** `C:\Users\Anil.Kumar6\Downloads\PRD.md` (§ 7.4 + § 12).

---

## 1. Purpose

Materialise a weekly measurement report on how the intelligence system is performing against reality. Three metrics per week per market:

- **Market precision** — % of digest topics that appeared in Discover exports within 48h for any publisher. Answers "did TOS correctly predict what would win?"
- **ET conversion** — for ET articles matched to digest topics, GSC Discover impressions/clicks (`country='usa'`) vs ET articles not on the digest. Answers "did on-digest topics produce better ET Discover traffic?"
- **Coverage trends** — per-lane distinct entity counts this week vs prior week. Answers "which lanes gained or lost tagged activity?"

Sprint 4 is the smallest sprint by code volume. Most of the compute already exists (Sprint 3 dashboard data loaders). Sprint 4 wraps them in a scheduled job that writes Markdown artifacts and persists history for query.

## 2. Resolved decisions

Two forks resolved with the user:

1. **A: Markdown files + new `scorecards` DB table.** Matches Sprint 3's digest pattern (`data/digests/*.md`). DB table gives future sprints a query surface for trend charts. `scorecards` row per weekly run with `iso_week` as part of PK — re-running overwrites.
2. **B: Add coverage trends (in addition to PRD's 2 metrics).** Coverage trends adds ~20% code but produces the "which lanes gained/lost activity" view that helps editorial decide `in_et_lane` flips.

## 3. Non-goals

- **No feedback loop into `scoring.yaml`.** Per PRD § 8; weight changes stay human decisions after ≥4 weekly scorecards.
- **No email/Slack notification of scorecards.** Human reads `data/scorecards/latest.md` or the Sprint 3 dashboard Scorecard tab.
- **No automatic historical backfill.** `--week YYYY-Www` invokes a specific week; the default run scores the previous ISO week.
- **No web UI beyond the Sprint 3 dashboard.** The dashboard's Scorecard tab already surfaces market precision + ET conversion. Sprint 4 adds a coverage-trends chart to that tab and the ability to view historical scorecards from `data/scorecards/`.
- **No new external prerequisites.** Sprint 4 reads the warehouse only.

## 4. Repo additions

```
discover-intel/
├─ sql/schema.sql                             # + scorecards table; user_version 3→4
├─ src/discover_intel/
│   └─ analysis/
│       └─ scorecard.py                       # NEW — S4 compute + persist + render
├─ src/discover_intel/delivery/
│   ├─ dashboard.py                           # + coverage_trends_data(conn, ...) function
│   └─ scorecard_template.md.j2               # NEW — jinja2 template for the weekly artifact
├─ src/discover_intel/cli.py                  # + scorecard subcommand
├─ scripts/
│   ├─ run-scorecard.ps1                      # NEW
│   ├─ register-tasks.ps1                     # extend: 1 more scheduled task
│   └─ unregister-tasks.ps1                   # extend: 1 more name
├─ data/scorecards/                           # NEW — Markdown output (gitignored via data/)
└─ tests/                                     # + tests for schema v4, coverage, scorecard, E2E
```

**Key layout decisions:**

- **`scorecard.py` lives in `analysis/`** to match PRD S4 nomenclature. It reads Sprint 3's `delivery/dashboard.py` data loaders (they're pure functions of a Connection) — no circular imports because scorecard imports from delivery, not the other way around.
- **Template file lives in `delivery/`** next to `digest_template.md.j2`. Both are human-readable artifacts.
- **`coverage_trends_data()` is added to `delivery/dashboard.py`** so the dashboard's Scorecard tab can render the same chart. Sprint 4's `scorecard.py` calls it.

## 5. Data model

`PRAGMA user_version = 4`. One new table.

```sql
PRAGMA user_version = 4;

-- Written by S4 analysis/scorecard.py. One row per weekly run per market.
-- PK on (iso_week, market) so re-running the same week overwrites (backfill-friendly).
CREATE TABLE IF NOT EXISTS scorecards (
  iso_week             TEXT NOT NULL,     -- 'YYYY-Www', e.g. '2026-W39'
  market               TEXT NOT NULL,     -- 'US'
  computed_at          TEXT NOT NULL,     -- ISO UTC
  window_start         TEXT NOT NULL,     -- ISO UTC (Monday 00:00Z of iso_week)
  window_end           TEXT NOT NULL,     -- ISO UTC (Sunday 23:59:59Z of iso_week)
  digest_topics_count  INTEGER NOT NULL DEFAULT 0,
  market_precision     REAL,              -- 0-100; NULL if 0 digests in window
  et_conversion_json   TEXT NOT NULL,     -- {gsc_populated: bool, ...}
  coverage_trends_json TEXT NOT NULL,     -- [{"lane": "...", "entity_count": N, "prior_entity_count": N, "delta": D}, ...]
  markdown_path        TEXT NOT NULL,     -- relative path to the artifact file
  PRIMARY KEY (iso_week, market)
);
CREATE INDEX IF NOT EXISTS idx_scorecards_computed ON scorecards(computed_at DESC);
```

**Non-obvious decisions:**

- **PK is `(iso_week, market)`.** Backfilling a missed week is normal ops; the `INSERT OR REPLACE` handles it. Multiple markets get separate rows (UK later).
- **JSON columns for `et_conversion` and `coverage_trends`.** Both have variable-shape payloads (ET conversion has the `gsc_populated` flag branch; coverage trends is a list of lanes). Simpler than a normalised child table for read-only measurement data.
- **`markdown_path`** — relative to repo root so absolute paths don't leak into DB.

## 6. Component contract

### 6.1 `analysis/scorecard.py`

CLI: `python -m discover_intel scorecard --db X [--week YYYY-Www] [--market US] [--out data/scorecards] [--dry-run]`.

- **`--week` default:** the ISO week ending yesterday UTC. So a Monday 06:00 UTC run scores the just-completed week.
- **Reads:**
  - Sprint 3's `market_precision_data(conn)` — filter rows to the window.
  - Sprint 3's `et_conversion_data(conn)` — returns dict with `gsc_populated` flag.
  - New `coverage_trends_data(conn, window_start, window_end)`.
- **Computes:**
  - `digest_topics_count` from `topic_scores` where `scored_at` in window AND `tos >= 60`.
  - `market_precision` (%) = matched-in-Discover-within-48h / total_digest_topics × 100. NULL when denominator is 0.
  - `et_conversion` — passthrough of the dict from `et_conversion_data`. Includes `on_digest_avg_impressions/clicks` and `off_digest_avg_impressions/clicks` when GSC is populated.
  - `coverage_trends` — for each lane in `taxonomy` (kind='lane'): `entity_count_this_week`, `entity_count_prior_week`, `delta` = this - prior.
- **Persistence:** `INSERT OR REPLACE INTO scorecards` with the compound PK.
- **Rendering:** jinja2 template → `data/scorecards/<iso_week>.md` + `data/scorecards/latest.md`.
- **`--dry-run`:** prints Markdown to stdout, doesn't write files or DB.
- **Summary log:** `scorecard: 2026-W39 US -- 15 digest topics, market_precision=82.3%, gsc_populated=false, 8 lanes covered`.
- **Failure model:** per Sprint 1-3 discipline. Empty warehouse → all metrics degrade gracefully (0 topics, NULL precision, gsc_populated=false, empty coverage). Never crashes on missing data.

### 6.2 `delivery/dashboard.py::coverage_trends_data()`

Added next to `market_precision_data` and `et_conversion_data`. Signature:

```python
def coverage_trends_data(
    conn: sqlite3.Connection,
    window_start: str,        # ISO UTC
    window_end: str,          # ISO UTC
) -> pd.DataFrame:
    """Per-lane distinct-entity counts this window vs prior-equal-length window.

    Returns columns: [lane, entity_count, prior_entity_count, delta].
    """
```

SQL joins `item_entities` → `taxonomy` (kind='lane') → `items` (via source_key prefix). Counts distinct entities per lane in the two windows separately and diffs them.

**Reused by:** the Sprint 3 dashboard's Scorecard tab (extended with a coverage-trends bar chart).

### 6.3 `delivery/scorecard_template.md.j2` (excerpt)

```markdown
# US Discover Scorecard — {{ iso_week }}

**Window:** {{ window_start }} → {{ window_end }}
**Computed:** {{ computed_at }}

## Market precision

{{ digest_topics_count }} topics were in the digest this week (TOS ≥ 60).

{% if market_precision is not none -%}
**{{ '%.1f' | format(market_precision) }}%** appeared in DiscoverTrends/TOI-GA within 48 hours.

Baseline for a random topic is ≥5-10% (varies by publisher volume);
Sprint-1 success criterion is ≥2× that baseline.
{%- else -%}
No digests were produced this week — precision is undefined.
{%- endif %}

## ET conversion

{% if et_conversion.gsc_populated -%}
On-digest ET articles: avg **{{ et_conversion.on_digest_avg_impressions|int }}** impressions,
**{{ et_conversion.on_digest_avg_clicks|int }}** clicks.

Off-digest ET articles: avg **{{ et_conversion.off_digest_avg_impressions|int }}** impressions,
**{{ et_conversion.off_digest_avg_clicks|int }}** clicks.
{%- else -%}
**N/A — GSC not populated.** Enable the GSC job to compute ET conversion; see README.
{%- endif %}

## Coverage trends

Per-lane distinct entities this week vs prior week:

| Lane | This week | Prior week | Δ |
|---|---|---|---|
{% for row in coverage_trends -%}
| {{ row.lane }} | {{ row.entity_count }} | {{ row.prior_entity_count }} | {{ row.delta }} |
{% endfor %}
```

## 7. Ops

**PowerShell wrapper** `scripts/run-scorecard.ps1` — same shape as Sprint 3 wrappers. Uses `[DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")`, per-module log at `logs/scorecard.log`, exit-code line.

**Task Scheduler entry** in `register-tasks.ps1`:

| Task name | Cadence | UTC time | Wrapper |
|---|---|---|---|
| `DiscoverIntel_Scorecard` | **weekly** | Monday 06:00 UTC (per PRD § 10) | `run-scorecard.ps1` |

Total scheduled tasks after Sprint 4 = **15** (7+4+3+1).

`unregister-tasks.ps1`'s `$names` array grows by 1.

## 8. Testing

- **`test_schema_v4.py`** — new `scorecards` table + `user_version=4`. Sprint 1/2/3 tests bumped from `== 3` to `== 4`.
- **`test_coverage_trends.py`** — DB-fixture with seeded items + entities + lane taxonomy; verify per-lane counts + prior-window diff.
- **`test_scorecard.py`** — seed `topic_scores` + `discover_articles` + `gsc_discover`; verify all three metrics compute; verify persistence into `scorecards` + Markdown rendering.
- **`test_e2e_sprint4.py`** — full CLI on empty warehouse: writes an "empty week" Markdown, writes a `scorecards` row with `market_precision=NULL`, `et_conversion.gsc_populated=false`, empty coverage_trends. All CLIs return exit 0.
- **`test_readme_sprint4.py`** — README mentions `scorecard` command + `data/scorecards/`.

## 9. Acceptance criteria

1. `python -m discover_intel init-db --db data\warehouse.db` — creates `scorecards` table; `user_version=4`.
2. `python -m discover_intel scorecard --db data\warehouse.db` (empty warehouse) — writes `data\scorecards\<iso_week>.md` containing "No digests were produced this week" text; writes a `scorecards` row with NULL market_precision.
3. Same command with seeded data — computes all three metrics; Markdown includes the coverage-trends table.
4. Re-run — overwrites the same week's row (INSERT OR REPLACE); does not create duplicates.
5. `python -m discover_intel db-stats` — lists `scorecards=N` alongside the 12 prior tables.
6. `.\scripts\register-tasks.ps1` — installs all 15 tasks; `Get-ScheduledTask -TaskName "DiscoverIntel_*"` shows them Ready.
7. `pytest tests\ -q` — all Sprint 1+2+3+4 tests pass.

## 10. Open questions still to resolve (non-blocking)

1. **Weekly cadence timing on Windows.** Windows Task Scheduler `Weekly` trigger uses local time. We convert 06:00 UTC to local when registering. On IST that's 11:30 IST which is a fine business hour; on Eastern that's 01:00 EST/02:00 EDT (fine — Task Scheduler handles overnight).
2. **What's the right precision baseline?** Template mentions ≥5-10% baseline. Real baseline will come from data — first 4 weekly runs will tell us.
3. **Coverage-trends prior window definition.** Spec uses "prior equal-length window immediately before this one" (7-day sliding). Alternative: fixed 4-week average as the baseline. Kept simple for Sprint 4; can revisit.
