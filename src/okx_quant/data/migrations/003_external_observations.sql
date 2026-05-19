-- ============================================================
-- Migration 003: external feature observations
-- Stores non-OKX, non-1m-aligned research features separately from
-- canonical_candles and joins them into replay by as-of timestamp + TTL.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS external_datasets (
    dataset_id       TEXT PRIMARY KEY,
    provider         TEXT NOT NULL,
    frequency        TEXT NOT NULL,
    value_kind       TEXT NOT NULL
        CHECK (value_kind IN ('scalar', 'ohlcv', 'event', 'mixed')),
    max_age_seconds  INTEGER NOT NULL CHECK (max_age_seconds > 0),
    source_url       TEXT,
    attribution      TEXT,
    active           BOOLEAN NOT NULL DEFAULT TRUE,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS external_observations (
    dataset_id      TEXT NOT NULL REFERENCES external_datasets(dataset_id) ON DELETE CASCADE,
    observed_at     TIMESTAMPTZ NOT NULL,
    published_at    TIMESTAMPTZ,
    value_num       DOUBLE PRECISION,
    value_text      TEXT,
    fields          JSONB NOT NULL DEFAULT '{}'::jsonb,
    quality_status  TEXT NOT NULL DEFAULT 'raw'
        CHECK (quality_status IN ('raw', 'validated', 'corrected', 'suspect')),
    raw_payload     JSONB,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dataset_id, observed_at)
);

SELECT create_hypertable(
    'external_observations', 'observed_at',
    chunk_time_interval => INTERVAL '1 year',
    if_not_exists => TRUE,
    migrate_data => TRUE
);

CREATE INDEX IF NOT EXISTS idx_external_observations_lookup
    ON external_observations (dataset_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_external_observations_published
    ON external_observations (dataset_id, published_at DESC)
    WHERE published_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS external_fetch_jobs (
    job_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id     TEXT NOT NULL REFERENCES external_datasets(dataset_id) ON DELETE CASCADE,
    provider       TEXT NOT NULL,
    start_at       TIMESTAMPTZ,
    end_at         TIMESTAMPTZ,
    status         TEXT NOT NULL
        CHECK (status IN ('running', 'success', 'failed', 'partial')),
    rows_fetched   INTEGER NOT NULL DEFAULT 0 CHECK (rows_fetched >= 0),
    rows_inserted  INTEGER NOT NULL DEFAULT 0 CHECK (rows_inserted >= 0),
    rows_updated   INTEGER NOT NULL DEFAULT 0 CHECK (rows_updated >= 0),
    rows_skipped   INTEGER NOT NULL DEFAULT 0 CHECK (rows_skipped >= 0),
    error_message  TEXT,
    details        JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_external_fetch_jobs_dataset_started
    ON external_fetch_jobs (dataset_id, started_at DESC);

CREATE TABLE IF NOT EXISTS external_ingestion_checkpoints (
    dataset_id      TEXT NOT NULL REFERENCES external_datasets(dataset_id) ON DELETE CASCADE,
    direction       TEXT NOT NULL DEFAULT 'forward'
        CHECK (direction IN ('forward', 'backfill')),
    cursor_time     TIMESTAMPTZ,
    request_count   INTEGER NOT NULL DEFAULT 0 CHECK (request_count >= 0),
    row_count       INTEGER NOT NULL DEFAULT 0 CHECK (row_count >= 0),
    status          TEXT NOT NULL DEFAULT 'idle'
        CHECK (status IN ('idle', 'running', 'success', 'failed')),
    last_error      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dataset_id, direction)
);
