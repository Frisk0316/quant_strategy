-- ============================================================
-- Mirror Binance market_funding_rates into legacy funding_rates
-- File: sql/mirror_funding_to_legacy.sql
-- Purpose:
--   Copy Binance funding data from the new multi-exchange market_funding_rates
--   table into the legacy funding_rates table, so the current
--   load_funding(... backend='postgres') path can read it.
--
-- Safety:
--   This script is idempotent.
--   It uses ON CONFLICT DO UPDATE and can be rerun after new ingestion.
--
-- Current mappings:
--   Binance BTCUSDT -> BTC-USDT-SWAP
--   Binance ETHUSDT -> ETH-USDT-SWAP
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
-- 02. Mirror funding into legacy funding_rates
-- ============================================================

WITH symbol_map AS (
    SELECT *
    FROM (
        VALUES
            ('BTCUSDT', 'BTC-USDT-SWAP'),
            ('ETHUSDT', 'ETH-USDT-SWAP')
    ) AS v(binance_inst_id, canonical_inst_id)
),
funding_with_next AS (
    SELECT
        f.instrument_id,
        f.funding_time,
        f.funding_rate,
        f.realized_rate,
        f.mark_price,
        f.funding_interval_hours,
        f.raw_payload,
        LEAD(f.funding_time) OVER (
            PARTITION BY f.instrument_id
            ORDER BY f.funding_time
        ) AS next_funding_ts
    FROM market_funding_rates f
),
source_rows AS (
    SELECT
        f.funding_time AS ts,
        i.exchange AS source,
        m.canonical_inst_id AS inst_id,
        f.funding_rate,
        f.realized_rate,
        f.mark_price,
        f.funding_interval_hours,
        f.next_funding_ts,
        f.raw_payload
    FROM funding_with_next f
    JOIN market_instruments i
      ON i.instrument_id = f.instrument_id
    JOIN symbol_map m
      ON m.binance_inst_id = i.inst_id
    WHERE i.exchange = 'binance'
      AND i.market_type = 'linear_perpetual'
)
INSERT INTO funding_rates (
    ts,
    source,
    inst_id,
    funding_rate,
    realized_rate,
    mark_price,
    funding_interval_hours,
    next_funding_ts,
    raw_payload
)
SELECT
    ts,
    source,
    inst_id,
    funding_rate,
    realized_rate,
    mark_price,
    funding_interval_hours,
    next_funding_ts,
    raw_payload
FROM source_rows
ON CONFLICT (source, inst_id, ts) DO UPDATE SET
    funding_rate = EXCLUDED.funding_rate,
    realized_rate = EXCLUDED.realized_rate,
    mark_price = EXCLUDED.mark_price,
    funding_interval_hours = EXCLUDED.funding_interval_hours,
    next_funding_ts = EXCLUDED.next_funding_ts,
    raw_payload = EXCLUDED.raw_payload;

COMMIT;


-- ============================================================
-- 03. Verify legacy funding coverage after mirror
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
-- 04. View latest mirrored funding rows
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
  AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
ORDER BY ts DESC, inst_id
LIMIT 100;
