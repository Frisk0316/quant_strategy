-- ============================================================
-- 1m OHLCV Query Reference
-- File: sql/query_ohlcv_1m.sql
-- Purpose:
--   Common queries for canonical_candles (1m bar).
--   All 15 USDT perpetual instruments, source: Binance Futures.
--
-- Instruments:
--   ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, LTC,
--   MATIC (→ POLUSDT on Binance), SHIB (→ 1000SHIBUSDT),
--   SOL, TON, TRX, XRP   — all suffixed -USDT-SWAP
--
-- Coverage:
--   BTC / ETH / BNB / SOL / XRP / ADA / DOGE / LINK / AVAX / DOT / LTC / SHIB
--     2024-01-01 ~ present  (~1,238,000 rows each)
--   TON  2024-03-01 ~ present  (~1,151,000 rows)
--   TRX  2024-09-05 ~ present  (~880,000 rows)
--   MATIC 2024-09-13 ~ present  (~869,000 rows)  [Binance renamed to POL]
--
-- Safety:  SELECT only.  No INSERT / UPDATE / DELETE.
--
-- Usage:
--   psql:     \i sql/query_ohlcv_1m.sql
--   DBeaver / TablePlus / pgAdmin:
--     Open file → highlight one section → Execute
-- ============================================================


-- ============================================================
-- 00. All-instruments coverage snapshot
-- ============================================================

SELECT
    inst_id,
    COUNT(*)       AS rows,
    MIN(ts)::date  AS first,
    MAX(ts)::date  AS last,
    MAX(ts)::date - MIN(ts)::date AS days
FROM canonical_candles
WHERE bar = '1m'
GROUP BY inst_id
ORDER BY inst_id;


-- ============================================================
-- 01. Single instrument — time range
-- Edit inst_id / ts range as needed.
-- ============================================================

SELECT
    ts,
    open,
    high,
    low,
    close,
    vol_base,
    vol_quote
FROM canonical_candles
WHERE inst_id = 'BTC-USDT-SWAP'
  AND bar    = '1m'
  AND ts >= '2026-05-01'
  AND ts <  '2026-05-10'
ORDER BY ts;


-- ============================================================
-- 02. Single instrument — latest N candles
-- ============================================================

SELECT
    ts,
    open,
    high,
    low,
    close,
    vol_base,
    vol_quote
FROM canonical_candles
WHERE inst_id = 'BTC-USDT-SWAP'
  AND bar    = '1m'
ORDER BY ts DESC
LIMIT 100;


-- ============================================================
-- 03. Single instrument — one full day (1440 rows expected)
-- ============================================================

SELECT
    ts,
    open,
    high,
    low,
    close,
    vol_base,
    vol_quote,
    source_primary
FROM canonical_candles
WHERE inst_id = 'BTC-USDT-SWAP'
  AND bar    = '1m'
  AND ts >= '2026-05-09 00:00:00+00'
  AND ts <  '2026-05-10 00:00:00+00'
ORDER BY ts;


-- ============================================================
-- 04. Snapshot — all instruments at a single timestamp
-- ============================================================

SELECT
    inst_id,
    close,
    vol_base,
    source_primary
FROM canonical_candles
WHERE bar = '1m'
  AND ts  = '2026-05-09 08:00:00+00'
ORDER BY inst_id;


-- ============================================================
-- 05. Two instruments side-by-side (e.g. BTC vs ETH)
-- ============================================================

SELECT
    ts,
    MAX(CASE WHEN inst_id = 'BTC-USDT-SWAP' THEN close END) AS btc_close,
    MAX(CASE WHEN inst_id = 'ETH-USDT-SWAP' THEN close END) AS eth_close,
    MAX(CASE WHEN inst_id = 'SOL-USDT-SWAP' THEN close END) AS sol_close
FROM canonical_candles
WHERE bar    = '1m'
  AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP', 'SOL-USDT-SWAP')
  AND ts >= '2026-05-09 00:00:00+00'
  AND ts <  '2026-05-10 00:00:00+00'
GROUP BY ts
ORDER BY ts;


-- ============================================================
-- 06. OHLCV aggregated to 5m (on the fly, no separate table needed)
-- ============================================================

SELECT
    date_trunc('hour', ts) + INTERVAL '5 min' * FLOOR(EXTRACT(MINUTE FROM ts) / 5) AS ts_5m,
    FIRST_VALUE(open)  OVER w AS open,
    MAX(high)          OVER w AS high,
    MIN(low)           OVER w AS low,
    LAST_VALUE(close)  OVER w AS close,
    SUM(vol_base)      OVER w AS vol_base,
    SUM(vol_quote)     OVER w AS vol_quote
FROM canonical_candles
WHERE inst_id = 'BTC-USDT-SWAP'
  AND bar    = '1m'
  AND ts >= '2026-05-09 00:00:00+00'
  AND ts <  '2026-05-10 00:00:00+00'
WINDOW w AS (
    PARTITION BY date_trunc('hour', ts) + INTERVAL '5 min' * FLOOR(EXTRACT(MINUTE FROM ts) / 5)
    ORDER BY ts
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
)
ORDER BY ts_5m;


-- ============================================================
-- 07. Gap detection — missing 1m candles in a period
-- Empty result = no gaps.
-- ============================================================

WITH expected AS (
    SELECT generate_series(
        '2026-05-01 00:00:00+00'::timestamptz,
        '2026-05-09 23:59:00+00'::timestamptz,
        INTERVAL '1 minute'
    ) AS ts
)
SELECT e.ts AS missing_ts
FROM expected e
LEFT JOIN canonical_candles c
       ON c.ts      = e.ts
      AND c.inst_id = 'BTC-USDT-SWAP'
      AND c.bar     = '1m'
WHERE c.ts IS NULL
ORDER BY e.ts;


-- ============================================================
-- 08. Gap detection — find all gap windows (faster than row-by-row)
-- Returns (gap_start, gap_end, gap_size) per instrument.
-- ============================================================

WITH ordered AS (
    SELECT
        inst_id,
        ts,
        LEAD(ts) OVER (PARTITION BY inst_id ORDER BY ts) AS next_ts
    FROM canonical_candles
    WHERE bar    = '1m'
      AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
      AND ts >= '2024-01-01'
)
SELECT
    inst_id,
    ts              AS gap_start,
    next_ts         AS gap_end,
    next_ts - ts    AS gap_size
FROM ordered
WHERE next_ts IS NOT NULL
  AND next_ts - ts <> INTERVAL '1 minute'
ORDER BY inst_id, ts;


-- ============================================================
-- 09. Data quality — check source breakdown per instrument
-- ============================================================

SELECT
    inst_id,
    source_primary,
    quality_status,
    COUNT(*)       AS rows,
    MIN(ts)::date  AS first,
    MAX(ts)::date  AS last
FROM canonical_candles
WHERE bar = '1m'
GROUP BY inst_id, source_primary, quality_status
ORDER BY inst_id, source_primary;


-- ============================================================
-- 10. Alignment check — how many timestamps all 15 instruments share
-- Useful before running multi-leg strategies.
-- ============================================================

SELECT
    ts,
    COUNT(DISTINCT inst_id) AS instrument_count
FROM canonical_candles
WHERE bar    = '1m'
  AND ts >= '2024-09-13'       -- earliest date all 15 overlap
GROUP BY ts
HAVING COUNT(DISTINCT inst_id) < 15
ORDER BY ts
LIMIT 50;


-- ============================================================
-- 11. Daily OHLCV rolled up from 1m (no separate 1D table needed)
-- ============================================================

SELECT
    inst_id,
    ts::date                                              AS date,
    (array_agg(open  ORDER BY ts))[1]                    AS open,
    MAX(high)                                             AS high,
    MIN(low)                                              AS low,
    (array_agg(close ORDER BY ts DESC))[1]               AS close,
    SUM(vol_base)                                         AS vol_base,
    SUM(vol_quote)                                        AS vol_quote
FROM canonical_candles
WHERE inst_id = 'BTC-USDT-SWAP'
  AND bar    = '1m'
  AND ts >= '2026-04-01'
  AND ts <  '2026-05-01'
GROUP BY inst_id, ts::date
ORDER BY date;


-- ============================================================
-- 12. instrument_bars — registered coverage bounds
-- ============================================================

SELECT
    inst_id,
    bar,
    first_candle_ts::date AS first,
    last_candle_ts::date  AS last,
    last_checked_at::date AS checked
FROM instrument_bars
WHERE bar = '1m'
ORDER BY inst_id;


-- ============================================================
-- 13. Ingestion checkpoints — where each symbol last stopped
-- ============================================================

SELECT
    source,
    dataset,
    inst_id,
    direction,
    cursor_time::date  AS cursor_date,
    status,
    row_count,
    updated_at::date   AS updated
FROM ingestion_checkpoints
WHERE dataset = 'klines_1m'
ORDER BY source, inst_id, direction;


-- ============================================================
-- 14. market_instruments — Binance → canonical mapping
-- ============================================================

SELECT
    exchange,
    inst_id            AS binance_symbol,
    canonical_inst_id  AS canonical_inst_id,
    is_active
FROM market_instruments
WHERE exchange = 'binance'
ORDER BY inst_id;
