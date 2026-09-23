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
