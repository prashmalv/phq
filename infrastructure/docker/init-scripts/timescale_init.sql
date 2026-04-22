-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ─── Events Table (core hypertable) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id              BIGSERIAL,
    event_id        UUID NOT NULL DEFAULT gen_random_uuid(),
    source          VARCHAR(50) NOT NULL,         -- 'twitter','facebook','news','fir','govt'
    source_url      TEXT,
    content         TEXT NOT NULL,
    content_hi      TEXT,                          -- Hindi original if translated
    author_handle   VARCHAR(200),
    author_verified BOOLEAN DEFAULT FALSE,
    language        VARCHAR(10),
    event_type      VARCHAR(100),                  -- 'violence','stampede','protest','accident'
    sentiment       SMALLINT,                      -- -1 negative, 0 neutral, 1 positive
    sentiment_score FLOAT,
    credibility     FLOAT DEFAULT 0.5,             -- 0.0 – 1.0
    district        VARCHAR(100),
    tehsil          VARCHAR(100),
    city            VARCHAR(200),
    state           VARCHAR(100) DEFAULT 'Uttar Pradesh',
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    tags            TEXT[],
    entities        JSONB,                         -- {persons:[], orgs:[], locations:[]}
    raw_data        JSONB,
    occurred_at     TIMESTAMPTZ NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, occurred_at)
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('events', 'occurred_at', if_not_exists => TRUE);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_events_district       ON events (district, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type     ON events (event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_source         ON events (source, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_tags           ON events USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_events_entities       ON events USING GIN (entities);

-- ─── Continuous Aggregate: daily event counts by district ────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_district_events
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', occurred_at) AS day,
    district,
    event_type,
    COUNT(*) AS event_count,
    AVG(sentiment_score) AS avg_sentiment
FROM events
GROUP BY day, district, event_type
WITH NO DATA;

-- ─── Query Audit Log ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS query_audit (
    id          BIGSERIAL PRIMARY KEY,
    officer_id  VARCHAR(100) NOT NULL,
    query_text  TEXT NOT NULL,
    query_lang  VARCHAR(10),
    answer_text TEXT,
    db_sources  TEXT[],                            -- which DBs were queried
    latency_ms  INTEGER,
    queried_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Alert Rules ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_rules (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    keywords    TEXT[],
    district    VARCHAR(100),
    event_type  VARCHAR(100),
    threshold   INTEGER DEFAULT 5,                 -- N posts in window triggers alert
    window_mins INTEGER DEFAULT 30,
    active      BOOLEAN DEFAULT TRUE,
    created_by  VARCHAR(100),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Cached Answers (CAG) ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cached_answers (
    id            BIGSERIAL PRIMARY KEY,
    query_hash    VARCHAR(64) UNIQUE NOT NULL,      -- SHA256 of normalized query
    query_text    TEXT NOT NULL,
    answer_json   JSONB NOT NULL,
    hit_count     INTEGER DEFAULT 0,
    generated_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at    TIMESTAMPTZ DEFAULT NOW() + INTERVAL '6 hours'
);
