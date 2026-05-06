-- ============================================================
-- Canonicalize Binance USDT perpetual OHLCV into legacy canonical_candles
-- File: sql/canonicalize_binance_to_legacy.sql
-- Purpose:
--   Copy Binance market_klines into legacy canonical_candles so the current
--   backtest backend='postgres' path can read BTC-USDT-SWAP / ETH-USDT-SWAP.
--
-- Safety:
--   This script is idempotent.
--   It uses ON CONFLICT DO UPDATE and can be rerun after new ingestion.
--
-- Current mappings:
--   Binance BTCUSDT -> BTC-USDT-SWAP
--   Binance ETHUSDT -> ETH-USDT-SWAP
--
-- Usage in pgAdmin:
--   Query Tool -> Open File -> select this file -> Execute.
-- ============================================================

BEGIN;

-- ============================================================
-- 01. Ensure legacy instruments exist
-- ============================================================

INSERT INTO instruments (
    inst_id,
    exchange,
    inst_type,
    base_ccy,
    quote_ccy,
    settle_ccy,
    contract_value,
    tick_size,
    lot_size,
    min_size
)
VALUES
    (
        'BTC-USDT-SWAP',
        'binance',
        'SWAP',
        'BTC',
        'USDT',
        'USDT',
        0.01,
        0.1,
        0.01,
        0.01
    ),
    (
        'ETH-USDT-SWAP',
        'binance',
        'SWAP',
        'ETH',
        'USDT',
        'USDT',
        0.01,
        0.01,
        0.01,
        0.01
    )
ON CONFLICT (inst_id) DO NOTHING;


-- ============================================================
-- 02. Canonicalize Binance market_klines into canonical_candles
-- ============================================================

WITH symbol_map AS (
    SELECT *
    FROM (
        VALUES
            ('BTCUSDT', 'BTC-USDT-SWAP'),
            ('ETHUSDT', 'ETH-USDT-SWAP')
    ) AS v(binance_inst_id, canonical_inst_id)
),
source_rows AS (
    SELECT
        k.ts,
        m.canonical_inst_id AS inst_id,
        k.bar,
        k.open,
        k.high,
        k.low,
        k.close,
        NULL::DOUBLE PRECISION AS vol_contract,
        k.volume AS vol_base,
        k.quote_volume AS vol_quote,
        'binance' AS source_primary,
        'raw' AS quality_status,
        1 AS version,
        NOW() AS ingested_at,
        NOW() AS updated_at
    FROM market_klines k
    JOIN market_instruments i
      ON i.instrument_id = k.instrument_id
    JOIN symbol_map m
      ON m.binance_inst_id = i.inst_id
    WHERE i.exchange = 'binance'
      AND i.market_type = 'linear_perpetual'
      AND k.bar = '1m'
      AND k.ts >= '2024-01-01T00:00:00Z'
)
INSERT INTO canonical_candles (
    ts,
    inst_id,
    bar,
    open,
    high,
    low,
    close,
    vol_contract,
    vol_base,
    vol_quote,
    source_primary,
    quality_status,
    version,
    ingested_at,
    updated_at
)
SELECT
    ts,
    inst_id,
    bar,
    open,
    high,
    low,
    close,
    vol_contract,
    vol_base,
    vol_quote,
    source_primary,
    quality_status,
    version,
    ingested_at,
    updated_at
FROM source_rows
ON CONFLICT (inst_id, bar, ts) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    vol_contract = EXCLUDED.vol_contract,
    vol_base = EXCLUDED.vol_base,
    vol_quote = EXCLUDED.vol_quote,
    source_primary = EXCLUDED.source_primary,
    quality_status = EXCLUDED.quality_status,
    version = EXCLUDED.version,
    updated_at = NOW();

COMMIT;


-- ============================================================
-- 03. Verify canonical coverage after canonicalization
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
-- 04. Verify BTC / ETH alignment after canonicalization
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
