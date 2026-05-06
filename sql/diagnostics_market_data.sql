-- ============================================================
-- Quant Strategy Market Data Diagnostics
-- File: sql/diagnostics_market_data.sql
-- Purpose:
--   1) Inspect PostgreSQL/TimescaleDB connection.
--   2) Check market_klines / canonical_candles / funding coverage.
--   3) Create reusable diagnostics views.
--
-- Safety:
--   This file is intended to be safe for daily diagnostics.
--   It only uses SELECT and CREATE OR REPLACE VIEW.
--   It does NOT INSERT / UPDATE / DELETE market data.
--
-- Usage in pgAdmin:
--   Query Tool -> Open File -> select this file.
--   Highlight one section at a time and press Execute.
-- ============================================================

-- ============================================================
-- 00. Connection sanity check
-- ============================================================

SELECT
    current_database() AS current_database,
    current_user AS current_user,
    inet_server_addr() AS server_addr,
    inet_server_port() AS server_port,
    now() AS checked_at;


-- ============================================================
-- 01. List key tables
-- ============================================================

SELECT
    table_schema,
    table_name,
    table_type
FROM information_schema.tables
WHERE table_schema IN ('public', 'diagnostics')
  AND table_name IN (
      'market_instruments',
      'market_klines',
      'market_funding_rates',
      'instruments',
      'canonical_candles',
      'funding_rates',
      'ingestion_checkpoints',
      'ingestion_jobs'
  )
ORDER BY table_schema, table_name;


-- ============================================================
-- 02. Check Binance BTC / ETH market instruments
-- ============================================================

SELECT
    instrument_id,
    exchange,
    market_type,
    inst_id,
    normalized_symbol,
    base_asset,
    quote_asset,
    settlement_asset,
    contract_type,
    is_active,
    inserted_at,
    updated_at
FROM market_instruments
WHERE exchange = 'binance'
  AND normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
ORDER BY normalized_symbol, inst_id;


-- ============================================================
-- 03. Check market_klines coverage
-- This is the multi-exchange market-data layer.
-- ============================================================

SELECT
    i.exchange,
    i.market_type,
    i.inst_id,
    i.normalized_symbol,
    k.bar,
    MIN(k.ts) AS first_ts,
    MAX(k.ts) AS last_ts,
    COUNT(*) AS row_count
FROM market_klines k
JOIN market_instruments i
  ON i.instrument_id = k.instrument_id
WHERE i.exchange = 'binance'
  AND i.normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
  AND k.bar = '1m'
GROUP BY
    i.exchange,
    i.market_type,
    i.inst_id,
    i.normalized_symbol,
    k.bar
ORDER BY
    i.normalized_symbol,
    k.bar;


-- ============================================================
-- 04. View latest OHLCV rows from market_klines
-- Change normalized_symbol to BTCUSDT or ETHUSDT as needed.
-- ============================================================

SELECT
    i.exchange,
    i.inst_id,
    i.normalized_symbol,
    k.bar,
    k.ts,
    k.open,
    k.high,
    k.low,
    k.close,
    k.volume,
    k.quote_volume,
    k.data_source
FROM market_klines k
JOIN market_instruments i
  ON i.instrument_id = k.instrument_id
WHERE i.exchange = 'binance'
  AND i.normalized_symbol = 'BTCUSDT'
  AND k.bar = '1m'
ORDER BY k.ts DESC
LIMIT 100;


-- ============================================================
-- 05. View one day of OHLCV from market_klines
-- Example: Binance BTCUSDT on 2024-01-01.
-- Expected row_count for a full 1m day: 1440.
-- ============================================================

SELECT
    i.exchange,
    i.inst_id,
    i.normalized_symbol,
    k.ts,
    k.open,
    k.high,
    k.low,
    k.close,
    k.volume,
    k.quote_volume
FROM market_klines k
JOIN market_instruments i
  ON i.instrument_id = k.instrument_id
WHERE i.exchange = 'binance'
  AND i.normalized_symbol = 'BTCUSDT'
  AND k.bar = '1m'
  AND k.ts >= '2024-01-01T00:00:00Z'
  AND k.ts <  '2024-01-02T00:00:00Z'
ORDER BY k.ts ASC;


-- ============================================================
-- 06. Check 1m gaps in market_klines
-- Empty result means no non-1m gaps in the selected period.
-- ============================================================

WITH ordered AS (
    SELECT
        i.normalized_symbol,
        k.ts,
        LEAD(k.ts) OVER (
            PARTITION BY i.normalized_symbol
            ORDER BY k.ts
        ) AS next_ts
    FROM market_klines k
    JOIN market_instruments i
      ON i.instrument_id = k.instrument_id
    WHERE i.exchange = 'binance'
      AND i.normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
      AND k.bar = '1m'
      AND k.ts >= '2024-01-01T00:00:00Z'
)
SELECT
    normalized_symbol,
    ts,
    next_ts,
    next_ts - ts AS gap
FROM ordered
WHERE next_ts IS NOT NULL
  AND next_ts - ts <> INTERVAL '1 minute'
ORDER BY normalized_symbol, ts;


-- ============================================================
-- 07. Check duplicate market_klines rows
-- Primary key should prevent duplicates; this should return no rows.
-- ============================================================

SELECT
    i.exchange,
    i.inst_id,
    i.normalized_symbol,
    k.bar,
    k.ts,
    COUNT(*) AS row_count
FROM market_klines k
JOIN market_instruments i
  ON i.instrument_id = k.instrument_id
WHERE i.exchange = 'binance'
  AND i.normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
  AND k.bar = '1m'
GROUP BY
    i.exchange,
    i.inst_id,
    i.normalized_symbol,
    k.bar,
    k.ts
HAVING COUNT(*) > 1
ORDER BY i.normalized_symbol, k.ts;


-- ============================================================
-- 08. Check canonical_candles coverage
-- This is the current layer used by backend='postgres' backtests.
-- ============================================================

SELECT
    inst_id,
    bar,
    source_primary,
    MIN(ts) AS first_ts,
    MAX(ts) AS last_ts,
    COUNT(*) AS row_count
FROM canonical_candles
WHERE inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
  AND bar = '1m'
GROUP BY
    inst_id,
    bar,
    source_primary
ORDER BY
    inst_id,
    source_primary;


-- ============================================================
-- 09. Check canonical BTC / ETH alignment
-- Pairs trading requires both legs to exist at matching timestamps.
-- ============================================================

WITH btc AS (
    SELECT ts
    FROM canonical_candles
    WHERE inst_id = 'BTC-USDT-SWAP'
      AND bar = '1m'
      AND ts >= '2024-01-01T00:00:00Z'
),
eth AS (
    SELECT ts
    FROM canonical_candles
    WHERE inst_id = 'ETH-USDT-SWAP'
      AND bar = '1m'
      AND ts >= '2024-01-01T00:00:00Z'
)
SELECT
    COUNT(*) AS aligned_rows,
    MIN(btc.ts) AS first_aligned_ts,
    MAX(btc.ts) AS last_aligned_ts
FROM btc
JOIN eth
  ON eth.ts = btc.ts;


-- ============================================================
-- 10. Check canonical 1m gaps
-- Empty result means no non-1m gaps in the selected period.
-- ============================================================

WITH ordered AS (
    SELECT
        inst_id,
        ts,
        LEAD(ts) OVER (
            PARTITION BY inst_id
            ORDER BY ts
        ) AS next_ts
    FROM canonical_candles
    WHERE inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
      AND bar = '1m'
      AND ts >= '2024-01-01T00:00:00Z'
)
SELECT
    inst_id,
    ts,
    next_ts,
    next_ts - ts AS gap
FROM ordered
WHERE next_ts IS NOT NULL
  AND next_ts - ts <> INTERVAL '1 minute'
ORDER BY inst_id, ts;


-- ============================================================
-- 11. Check market_funding_rates coverage
-- This is the new multi-exchange funding table.
-- ============================================================

SELECT
    i.exchange,
    i.market_type,
    i.inst_id,
    i.normalized_symbol,
    MIN(f.funding_time) AS first_funding_time,
    MAX(f.funding_time) AS last_funding_time,
    COUNT(*) AS row_count
FROM market_funding_rates f
JOIN market_instruments i
  ON i.instrument_id = f.instrument_id
WHERE i.exchange = 'binance'
  AND i.normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
GROUP BY
    i.exchange,
    i.market_type,
    i.inst_id,
    i.normalized_symbol
ORDER BY
    i.normalized_symbol;


-- ============================================================
-- 12. View latest market_funding_rates rows
-- Change normalized_symbol to BTCUSDT or ETHUSDT as needed.
-- ============================================================

SELECT
    i.exchange,
    i.inst_id,
    i.normalized_symbol,
    f.funding_time,
    f.funding_rate,
    f.funding_rate * 100 AS funding_rate_pct,
    f.funding_rate_raw,
    f.realized_rate,
    f.mark_price,
    f.funding_interval_hours,
    f.data_source
FROM market_funding_rates f
JOIN market_instruments i
  ON i.instrument_id = f.instrument_id
WHERE i.exchange = 'binance'
  AND i.normalized_symbol = 'BTCUSDT'
ORDER BY f.funding_time DESC
LIMIT 100;


-- ============================================================
-- 13. Check funding interval distribution
-- Most Binance perp rows are commonly 8h, but do not hard-code that assumption.
-- ============================================================

SELECT
    i.exchange,
    i.normalized_symbol,
    f.funding_interval_hours,
    COUNT(*) AS row_count
FROM market_funding_rates f
JOIN market_instruments i
  ON i.instrument_id = f.instrument_id
WHERE i.exchange = 'binance'
  AND i.normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
GROUP BY
    i.exchange,
    i.normalized_symbol,
    f.funding_interval_hours
ORDER BY
    i.normalized_symbol,
    f.funding_interval_hours;


-- ============================================================
-- 14. Check legacy funding_rates coverage
-- This is the current layer expected by load_funding(... backend='postgres').
-- ============================================================

SELECT
    source,
    inst_id,
    MIN(ts) AS first_ts,
    MAX(ts) AS last_ts,
    COUNT(*) AS row_count
FROM funding_rates
WHERE source = 'binance'
  AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
GROUP BY
    source,
    inst_id
ORDER BY
    inst_id;


-- ============================================================
-- 15. View latest legacy funding_rates rows
-- ============================================================

SELECT
    ts,
    source,
    inst_id,
    funding_rate,
    funding_rate * 100 AS funding_rate_pct,
    realized_rate,
    mark_price,
    funding_interval_hours,
    next_funding_ts
FROM funding_rates
WHERE source = 'binance'
  AND inst_id = 'BTC-USDT-SWAP'
ORDER BY ts DESC
LIMIT 100;


-- ============================================================
-- 16. Check ingestion checkpoints
-- Useful for seeing where ingestion stopped and whether it failed.
-- ============================================================

SELECT
    source,
    dataset,
    inst_id,
    direction,
    cursor_time,
    request_count,
    row_count,
    status,
    last_error,
    updated_at
FROM ingestion_checkpoints
ORDER BY updated_at DESC;


-- ============================================================
-- 17. Check ingestion jobs
-- ============================================================

SELECT
    job_type,
    source,
    inst_id,
    bar,
    start_ts,
    end_ts,
    status,
    rows_fetched,
    rows_inserted,
    rows_updated,
    rows_skipped,
    error_message,
    started_at,
    finished_at
FROM ingestion_jobs
ORDER BY started_at DESC
LIMIT 50;


-- ============================================================
-- 18. Create diagnostics schema and views
-- Run once. After that, use sections 19+ for quick checks.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS diagnostics;

CREATE OR REPLACE VIEW diagnostics.v_market_klines_coverage AS
SELECT
    i.exchange,
    i.market_type,
    i.inst_id,
    i.normalized_symbol,
    k.bar,
    MIN(k.ts) AS first_ts,
    MAX(k.ts) AS last_ts,
    COUNT(*) AS row_count
FROM market_klines k
JOIN market_instruments i
  ON i.instrument_id = k.instrument_id
GROUP BY
    i.exchange,
    i.market_type,
    i.inst_id,
    i.normalized_symbol,
    k.bar;

CREATE OR REPLACE VIEW diagnostics.v_canonical_coverage AS
SELECT
    inst_id,
    bar,
    source_primary,
    MIN(ts) AS first_ts,
    MAX(ts) AS last_ts,
    COUNT(*) AS row_count
FROM canonical_candles
GROUP BY
    inst_id,
    bar,
    source_primary;

CREATE OR REPLACE VIEW diagnostics.v_market_funding_coverage AS
SELECT
    i.exchange,
    i.market_type,
    i.inst_id,
    i.normalized_symbol,
    MIN(f.funding_time) AS first_funding_time,
    MAX(f.funding_time) AS last_funding_time,
    COUNT(*) AS row_count
FROM market_funding_rates f
JOIN market_instruments i
  ON i.instrument_id = f.instrument_id
GROUP BY
    i.exchange,
    i.market_type,
    i.inst_id,
    i.normalized_symbol;

CREATE OR REPLACE VIEW diagnostics.v_legacy_funding_coverage AS
SELECT
    source,
    inst_id,
    MIN(ts) AS first_ts,
    MAX(ts) AS last_ts,
    COUNT(*) AS row_count
FROM funding_rates
GROUP BY
    source,
    inst_id;

CREATE OR REPLACE VIEW diagnostics.v_ingestion_checkpoint_latest AS
SELECT
    source,
    dataset,
    inst_id,
    direction,
    cursor_time,
    request_count,
    row_count,
    status,
    last_error,
    updated_at
FROM ingestion_checkpoints;


-- ============================================================
-- 19. Quick check: market_klines BTC / ETH coverage
-- ============================================================

SELECT *
FROM diagnostics.v_market_klines_coverage
WHERE exchange = 'binance'
  AND normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
  AND bar = '1m'
ORDER BY normalized_symbol, bar;


-- ============================================================
-- 20. Quick check: canonical_candles BTC / ETH coverage
-- ============================================================

SELECT *
FROM diagnostics.v_canonical_coverage
WHERE inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
  AND bar = '1m'
ORDER BY inst_id, source_primary;


-- ============================================================
-- 21. Quick check: market funding coverage
-- ============================================================

SELECT *
FROM diagnostics.v_market_funding_coverage
WHERE exchange = 'binance'
  AND normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
ORDER BY normalized_symbol;


-- ============================================================
-- 22. Quick check: legacy funding coverage
-- ============================================================

SELECT *
FROM diagnostics.v_legacy_funding_coverage
WHERE source = 'binance'
  AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
ORDER BY inst_id;


-- ============================================================
-- 23. Quick check: checkpoint status
-- ============================================================

SELECT *
FROM diagnostics.v_ingestion_checkpoint_latest
ORDER BY updated_at DESC;
