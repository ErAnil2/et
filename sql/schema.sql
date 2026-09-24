PRAGMA user_version = 3;

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

-- ============================================================================
-- Sprint 2 additions (added 2026-09-24). CREATE TABLE IF NOT EXISTS so
-- Sprint-1 warehouses upgrade cleanly — only the new tables get created.
-- ============================================================================

-- Written by S2-B analysis/match_outcomes.py.
-- One row per (item, discover_observation) match. Best-match cascade fills
-- match_type/score. INSERT OR IGNORE keeps the first (best) stage.
CREATE TABLE IF NOT EXISTS item_outcomes (
  item_id       TEXT NOT NULL REFERENCES items(item_id),
  obs_id        TEXT NOT NULL REFERENCES discover_articles(obs_id),
  match_type    TEXT NOT NULL CHECK (match_type IN ('url','canonical','title_exact','title_fuzzy')),
  match_score   REAL NOT NULL,
  matched_at    TEXT NOT NULL,
  PRIMARY KEY (item_id, obs_id)
);
CREATE INDEX IF NOT EXISTS idx_item_outcomes_obs  ON item_outcomes(obs_id);
CREATE INDEX IF NOT EXISTS idx_item_outcomes_type ON item_outcomes(match_type);

-- Seeded from config/lane_keywords.yaml + config/format_rules.yaml on startup.
-- Kind='lane' | 'format' | 'entity_type'. Slug taxonomy_id like 'lane:tech_ai'.
CREATE TABLE IF NOT EXISTS taxonomy (
  taxonomy_id   TEXT PRIMARY KEY,
  kind          TEXT NOT NULL CHECK (kind IN ('lane','format','entity_type')),
  label         TEXT NOT NULL,
  parent_id     TEXT,
  in_et_lane    INTEGER NOT NULL DEFAULT 1
);

-- Written by S2-C analysis/tag_entities.py. Serves both items and discover
-- observations through a source_key prefix ('item:<item_id>' or 'obs:<obs_id>').
CREATE TABLE IF NOT EXISTS item_entities (
  entry_id      TEXT PRIMARY KEY,
  source_key    TEXT NOT NULL,
  entity        TEXT NOT NULL,
  entity_type   TEXT,
  taxonomy_id   TEXT,
  confidence    REAL NOT NULL,
  tagged_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_item_entities_source ON item_entities(source_key);
CREATE INDEX IF NOT EXISTS idx_item_entities_ent    ON item_entities(entity);
CREATE INDEX IF NOT EXISTS idx_item_entities_tax    ON item_entities(taxonomy_id);

-- ============================================================================
-- Sprint 3 additions (added 2026-09-24). CREATE TABLE IF NOT EXISTS so
-- warehouses upgrade cleanly — only the new tables get created.
-- ============================================================================

-- Written by S3-A analysis/build_topic_stats.py. Rolling 72h snapshot per
-- (hour_bucket, market, entity). INSERT OR REPLACE on compound PK.
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

-- Written by S3-B scoring/tos.py. One row per scoring run per (market, entity).
-- History preserved for Sprint 4 scorecard.
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
