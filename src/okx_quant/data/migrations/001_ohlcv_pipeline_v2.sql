-- ============================================================
-- Migration 001: OHLCV pipeline v2 (raw + canonical two-layer)
-- Run via: python scripts/market_data/init_db.py
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ──────────────────────────────────────────────────────────────
-- Bar interval reference table
-- Provides canonical interval_ms for gap detection and chunk sizing
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bar_intervals (
    bar           TEXT PRIMARY KEY,
    interval_ms   INTEGER NOT NULL CHECK (interval_ms > 0),
    pg_interval   INTERVAL NOT NULL
);

INSERT INTO bar_intervals (bar, interval_ms, pg_interval) VALUES
    ('1m',  60000,   '1 minute'),
    ('3m',  180000,  '3 minutes'),
    ('5m',  300000,  '5 minutes'),
    ('15m', 900000,  '15 minutes'),
    ('30m', 1800000, '30 minutes'),
    ('1H',  3600000, '1 hour'),
    ('2H',  7200000, '2 hours'),
    ('4H',  14400000,'4 hours'),
    ('1D',  86400000,'1 day')
ON CONFLICT (bar) DO NOTHING;

-- ──────────────────────────────────────────────────────────────
-- Instrument registry
-- Stores metadata for all tracked trading pairs
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS instruments (
    inst_id          TEXT PRIMARY KEY,
    exchange         TEXT NOT NULL DEFAULT 'okx'
        CHECK (exchange IN ('okx', 'binance', 'bybit', 'coinbase', 'kraken', 'other')),
    inst_type        TEXT NOT NULL DEFAULT 'SWAP'
        CHECK (inst_type IN ('SPOT', 'SWAP', 'FUTURES', 'OPTION')),
    base_ccy         TEXT NOT NULL,
    quote_ccy        TEXT NOT NULL DEFAULT 'USDT',
    settle_ccy       TEXT NOT NULL DEFAULT 'USDT',
    contract_value   DOUBLE PRECISION,
    tick_size        DOUBLE PRECISION,
    lot_size         DOUBLE PRECISION,
    min_size         DOUBLE PRECISION,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    listed_at        TIMESTAMPTZ,
    delisted_at      TIMESTAMPTZ,
    added_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at      TIMESTAMPTZ,
    notes            TEXT
);

-- ──────────────────────────────────────────────────────────────
-- Per-(inst_id, bar) data coverage tracking
-- Separate from instruments so each bar has its own first/last ts
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS instrument_bars (
    inst_id          TEXT NOT NULL REFERENCES instruments(inst_id) ON DELETE CASCADE,
    bar              TEXT NOT NULL REFERENCES bar_intervals(bar),
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    first_candle_ts  TIMESTAMPTZ,
    last_candle_ts   TIMESTAMPTZ,
    last_checked_at  TIMESTAMPTZ,
    added_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (inst_id, bar)
);

-- ──────────────────────────────────────────────────────────────
-- Raw exchange candles
-- Exchange-native data; unique per (source, inst_id, bar, ts)
-- Allows storing OKX + Binance + Bybit at the same timestamp
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_candles (
    ts              TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL
        CHECK (source IN ('okx', 'binance', 'bybit', 'coinbase', 'kraken', 'manual', 'other')),
    inst_id         TEXT NOT NULL,
    bar             TEXT NOT NULL REFERENCES bar_intervals(bar),
    open            DOUBLE PRECISION NOT NULL,
    high            DOUBLE PRECISION NOT NULL,
    low             DOUBLE PRECISION NOT NULL,
    close           DOUBLE PRECISION NOT NULL,
    vol_contract    DOUBLE PRECISION,
    vol_base        DOUBLE PRECISION,
    vol_quote       DOUBLE PRECISION,
    is_closed       BOOLEAN NOT NULL DEFAULT TRUE,
    raw_payload     JSONB,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_raw_ohlc CHECK (
        high >= low
        AND high >= open
        AND high >= close
        AND low <= open
        AND low <= close
        AND open > 0
        AND high > 0
        AND low > 0
        AND close > 0
    )
);

SELECT create_hypertable(
    'raw_candles', 'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_candles
    ON raw_candles (source, inst_id, bar, ts);

CREATE INDEX IF NOT EXISTS idx_raw_candles_lookup
    ON raw_candles (inst_id, bar, source, ts DESC);

ALTER TABLE raw_candles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'source,inst_id,bar',
    timescaledb.compress_orderby = 'ts DESC'
);

SELECT add_compression_policy('raw_candles', INTERVAL '30 days');

-- ──────────────────────────────────────────────────────────────
-- Canonical strategy-ready candles
-- Cleaned, validated, backtest-safe; unique per (inst_id, bar, ts)
-- quality_status tracks data provenance
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS canonical_candles (
    ts              TIMESTAMPTZ NOT NULL,
    inst_id         TEXT NOT NULL REFERENCES instruments(inst_id),
    bar             TEXT NOT NULL REFERENCES bar_intervals(bar),
    open            DOUBLE PRECISION NOT NULL,
    high            DOUBLE PRECISION NOT NULL,
    low             DOUBLE PRECISION NOT NULL,
    close           DOUBLE PRECISION NOT NULL,
    vol_contract    DOUBLE PRECISION,
    vol_base        DOUBLE PRECISION,
    vol_quote       DOUBLE PRECISION,
    source_primary  TEXT NOT NULL DEFAULT 'okx',
    quality_status  TEXT NOT NULL DEFAULT 'raw'
        CHECK (quality_status IN ('raw', 'validated', 'corrected', 'suspect')),
    version         INTEGER NOT NULL DEFAULT 1,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_canonical_ohlc CHECK (
        high >= low
        AND high >= open
        AND high >= close
        AND low <= open
        AND low <= close
        AND open > 0
        AND high > 0
        AND low > 0
        AND close > 0
    )
);

SELECT create_hypertable(
    'canonical_candles', 'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_candles
    ON canonical_candles (inst_id, bar, ts);

CREATE INDEX IF NOT EXISTS idx_canonical_candles_lookup
    ON canonical_candles (inst_id, bar, ts DESC);

ALTER TABLE canonical_candles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'inst_id,bar',
    timescaledb.compress_orderby = 'ts DESC'
);

SELECT add_compression_policy('canonical_candles', INTERVAL '30 days');

-- ──────────────────────────────────────────────────────────────
-- Continuous aggregates: 5m, 15m, 1H derived from canonical 1m
-- Backtests should query these views for higher timeframes
-- ──────────────────────────────────────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS canonical_candles_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '5 minutes', ts) AS ts,
    inst_id,
    '5m'::TEXT AS bar,
    first(open, ts)    AS open,
    max(high)          AS high,
    min(low)           AS low,
    last(close, ts)    AS close,
    sum(vol_contract)  AS vol_contract,
    sum(vol_base)      AS vol_base,
    sum(vol_quote)     AS vol_quote,
    min(quality_status) AS quality_status
FROM canonical_candles
WHERE bar = '1m'
GROUP BY inst_id, time_bucket(INTERVAL '5 minutes', ts)
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS canonical_candles_15m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '15 minutes', ts) AS ts,
    inst_id,
    '15m'::TEXT AS bar,
    first(open, ts)    AS open,
    max(high)          AS high,
    min(low)           AS low,
    last(close, ts)    AS close,
    sum(vol_contract)  AS vol_contract,
    sum(vol_base)      AS vol_base,
    sum(vol_quote)     AS vol_quote,
    min(quality_status) AS quality_status
FROM canonical_candles
WHERE bar = '1m'
GROUP BY inst_id, time_bucket(INTERVAL '15 minutes', ts)
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS canonical_candles_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 hour', ts) AS ts,
    inst_id,
    '1H'::TEXT AS bar,
    first(open, ts)    AS open,
    max(high)          AS high,
    min(low)           AS low,
    last(close, ts)    AS close,
    sum(vol_contract)  AS vol_contract,
    sum(vol_base)      AS vol_base,
    sum(vol_quote)     AS vol_quote,
    min(quality_status) AS quality_status
FROM canonical_candles
WHERE bar = '1m'
GROUP BY inst_id, time_bucket(INTERVAL '1 hour', ts)
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'canonical_candles_5m',
    start_offset => INTERVAL '7 days',
    end_offset   => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes'
);

SELECT add_continuous_aggregate_policy(
    'canonical_candles_15m',
    start_offset => INTERVAL '7 days',
    end_offset   => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes'
);

SELECT add_continuous_aggregate_policy(
    'canonical_candles_1h',
    start_offset => INTERVAL '30 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);

-- ──────────────────────────────────────────────────────────────
-- Ingestion job tracking
-- Every backfill / update / validate / repair creates a job row
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type        TEXT NOT NULL
        CHECK (job_type IN ('backfill', 'update_all', 'validate', 'canonicalize',
                            'repair_gap', 'discover_pairs')),
    source          TEXT NOT NULL,
    inst_id         TEXT,
    bar             TEXT REFERENCES bar_intervals(bar),
    start_ts        TIMESTAMPTZ,
    end_ts          TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'success', 'failed', 'partial')),
    rows_fetched    INTEGER NOT NULL DEFAULT 0,
    rows_inserted   INTEGER NOT NULL DEFAULT 0,
    rows_updated    INTEGER NOT NULL DEFAULT 0,
    rows_skipped    INTEGER NOT NULL DEFAULT 0,
    gaps_found      INTEGER NOT NULL DEFAULT 0,
    outliers_found  INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    details         JSONB,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_lookup
    ON ingestion_jobs (job_type, status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_inst
    ON ingestion_jobs (inst_id, bar, started_at DESC);

-- ──────────────────────────────────────────────────────────────
-- Data quality events
-- Tracks gaps, outliers, fetch failures; supports status lifecycle
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_events (
    id               BIGSERIAL PRIMARY KEY,
    logged_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at      TIMESTAMPTZ,
    status           TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'resolved', 'ignored')),
    severity         TEXT NOT NULL DEFAULT 'warning'
        CHECK (severity IN ('info', 'warning', 'critical')),
    inst_id          TEXT NOT NULL,
    bar              TEXT NOT NULL REFERENCES bar_intervals(bar),
    source           TEXT,
    issue_type       TEXT NOT NULL
        CHECK (issue_type IN (
            'gap', 'outlier_flagged', 'outlier_replaced',
            'fetch_failed', 'validation_failed',
            'schema_violation', 'incomplete_candle'
        )),
    window_start     TIMESTAMPTZ,
    window_end       TIMESTAMPTZ,
    affected_count   INTEGER,
    field            TEXT,
    observed_value   DOUBLE PRECISION,
    reference_value  DOUBLE PRECISION,
    z_score          DOUBLE PRECISION,
    action_taken     TEXT,
    retry_count      INTEGER NOT NULL DEFAULT 0,
    job_id           UUID,
    details          JSONB,
    notes            TEXT
);

CREATE INDEX IF NOT EXISTS idx_quality_events_open
    ON data_quality_events (inst_id, bar, status, severity, logged_at DESC);

CREATE INDEX IF NOT EXISTS idx_quality_events_job
    ON data_quality_events (job_id);

-- ──────────────────────────────────────────────────────────────
-- Funding rates (P2 / optional; enables funding_carry discovery)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS funding_rates (
    ts              TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL DEFAULT 'okx',
    inst_id         TEXT NOT NULL REFERENCES instruments(inst_id),
    funding_rate    DOUBLE PRECISION NOT NULL,
    realized_rate   DOUBLE PRECISION,
    mark_price      DOUBLE PRECISION,
    funding_interval_hours DOUBLE PRECISION,
    next_funding_ts TIMESTAMPTZ,
    raw_payload     JSONB,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE funding_rates ADD COLUMN IF NOT EXISTS realized_rate DOUBLE PRECISION;
ALTER TABLE funding_rates ADD COLUMN IF NOT EXISTS mark_price DOUBLE PRECISION;
ALTER TABLE funding_rates ADD COLUMN IF NOT EXISTS funding_interval_hours DOUBLE PRECISION;

SELECT create_hypertable(
    'funding_rates', 'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_funding_rates
    ON funding_rates (source, inst_id, ts);

-- Long-running historical ingestion checkpoints.
CREATE TABLE IF NOT EXISTS ingestion_checkpoints (
    source          TEXT NOT NULL,
    dataset         TEXT NOT NULL,
    inst_id         TEXT NOT NULL,
    direction       TEXT NOT NULL DEFAULT 'forward',
    cursor_time_ms  BIGINT,
    cursor_time     TIMESTAMPTZ,
    request_count   BIGINT NOT NULL DEFAULT 0,
    row_count       BIGINT NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'idle',
    last_error      TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source, dataset, inst_id, direction),
    CHECK (dataset IN ('klines_1m', 'funding_rate')),
    CHECK (direction IN ('forward', 'backward')),
    CHECK (status IN ('idle', 'running', 'success', 'failed', 'partial'))
);

-- Multi-exchange canonical market data layer.
-- This layer keeps exchange-native instrument identity separate from the
-- normalized research symbol, so the same BTCUSDT contract on Binance and
-- Bybit remains distinct.
CREATE TABLE IF NOT EXISTS market_instruments (
    instrument_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange          TEXT NOT NULL
        CHECK (exchange IN ('okx', 'binance', 'bybit', 'coinbase', 'kraken', 'other')),
    market_type       TEXT NOT NULL DEFAULT 'linear_perpetual',
    inst_id           TEXT NOT NULL,
    normalized_symbol TEXT NOT NULL,
    base_asset        TEXT NOT NULL,
    quote_asset       TEXT NOT NULL DEFAULT 'USDT',
    settlement_asset  TEXT NOT NULL DEFAULT 'USDT',
    contract_type     TEXT NOT NULL DEFAULT 'perpetual',
    listing_time      TIMESTAMPTZ,
    delisting_time    TIMESTAMPTZ,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    inserted_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (exchange, market_type, inst_id)
);

CREATE INDEX IF NOT EXISTS idx_market_instruments_symbol
    ON market_instruments (normalized_symbol, exchange, is_active);

CREATE TABLE IF NOT EXISTS market_klines (
    instrument_id UUID NOT NULL REFERENCES market_instruments(instrument_id),
    bar           TEXT NOT NULL REFERENCES bar_intervals(bar),
    ts            TIMESTAMPTZ NOT NULL,
    open          DOUBLE PRECISION NOT NULL,
    high          DOUBLE PRECISION NOT NULL,
    low           DOUBLE PRECISION NOT NULL,
    close         DOUBLE PRECISION NOT NULL,
    volume        DOUBLE PRECISION,
    quote_volume  DOUBLE PRECISION,
    data_source   TEXT NOT NULL,
    raw_payload   JSONB,
    inserted_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (instrument_id, bar, ts),
    CONSTRAINT ck_market_klines_ohlc CHECK (
        high >= low
        AND high >= open
        AND high >= close
        AND low <= open
        AND low <= close
        AND open > 0
        AND high > 0
        AND low > 0
        AND close > 0
    )
);

SELECT create_hypertable(
    'market_klines', 'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_market_klines_lookup
    ON market_klines (instrument_id, bar, ts DESC);

CREATE TABLE IF NOT EXISTS market_funding_rates (
    instrument_id          UUID NOT NULL REFERENCES market_instruments(instrument_id),
    funding_time           TIMESTAMPTZ NOT NULL,
    funding_rate           DOUBLE PRECISION NOT NULL,
    funding_rate_raw       TEXT,
    realized_rate          DOUBLE PRECISION,
    mark_price             DOUBLE PRECISION,
    funding_interval_hours DOUBLE PRECISION,
    data_source            TEXT NOT NULL,
    raw_payload            JSONB,
    inserted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (instrument_id, funding_time)
);

SELECT create_hypertable(
    'market_funding_rates', 'funding_time',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_market_funding_rates_lookup
    ON market_funding_rates (instrument_id, funding_time DESC);
