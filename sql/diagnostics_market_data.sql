-- ============================================================
-- Quant Strategy Market Data Diagnostics
-- For PostgreSQL / TimescaleDB / pgAdmin
-- ============================================================

-- ============================================================
-- 00. Connection sanity check
-- 確認 pgAdmin / Python 是否連到同一個 DB
-- ============================================================

SELECT
    current_database() AS current_database,
    current_user AS current_user,
    inet_server_addr() AS server_addr,
    inet_server_port() AS server_port,
    now() AS checked_at;


-- ============================================================
-- 01. 檢查 Binance BTC / ETH market instruments
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
-- 02. 檢查 market_klines 資料覆蓋範圍
-- 用來確認 Binance BTCUSDT / ETHUSDT 1m 是否已經抓進 DB
-- ============================================================

SELECT
    i.exchange,
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
    i.inst_id,
    i.normalized_symbol,
    k.bar
ORDER BY
    i.normalized_symbol,
    k.bar;


-- ============================================================
-- 03. 查看 market_klines 最新 100 筆 OHLCV
-- 可將 normalized_symbol 改成 BTCUSDT 或 ETHUSDT
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
-- 04. 查看指定日期 OHLCV
-- 這裡以 BTCUSDT / 2024-01-01 為例
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
-- 05. 檢查 market_klines 是否有 1m 缺口
-- 同時檢查 BTCUSDT / ETHUSDT
-- 若結果為空，代表沒有非 1m 的 gap
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
-- 06. 檢查 canonical_candles 覆蓋範圍
-- 這是目前 backtest 實際會讀到的 OHLCV layer
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
-- 07. 檢查 canonical_candles 的 BTC / ETH 是否時間對齊
-- Pairs trading 需要 BTC 與 ETH 同時存在
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
-- 08. canonicalize Binance BTCUSDT / ETHUSDT 到 legacy canonical_candles
-- 注意：這是寫入 SQL。
-- 用途：讓 backtest 讀 BTC-USDT-SWAP / ETH-USDT-SWAP。
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


WITH symbol_map AS (
    SELECT *
    FROM (
        VALUES
            ('BTCUSDT', 'BTC-USDT-SWAP'),
            ('ETHUSDT', 'ETH-USDT-SWAP')
    ) AS v(binance_inst_id, canonical_inst_id)
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
    updated_at = NOW();


-- ============================================================
-- 09. 檢查 market_funding_rates 覆蓋範圍
-- 這是新的 multi-exchange funding table
-- ============================================================

SELECT
    i.exchange,
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
    i.inst_id,
    i.normalized_symbol
ORDER BY
    i.normalized_symbol;


-- ============================================================
-- 10. 查看最新 100 筆 market_funding_rates
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
-- 11. 檢查 funding interval 分布
-- 常見為 8h，但不要硬寫死
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
-- 12. mirror market_funding_rates 到 legacy funding_rates
-- 注意：這是寫入 SQL。
-- 用途：讓目前的 backtest load_funding(... backend='postgres') 有機會讀到。
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
ON CONFLICT (source, inst_id, ts) DO UPDATE SET
    funding_rate = EXCLUDED.funding_rate,
    realized_rate = EXCLUDED.realized_rate,
    mark_price = EXCLUDED.mark_price,
    funding_interval_hours = EXCLUDED.funding_interval_hours,
    next_funding_ts = EXCLUDED.next_funding_ts,
    raw_payload = EXCLUDED.raw_payload;


-- ============================================================
-- 13. 檢查 legacy funding_rates 覆蓋範圍
-- 這是目前 backtest funding loader 預期讀取的 legacy table
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
-- 14. 查看 legacy funding_rates 最新 100 筆
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
-- 15. 檢查 ingestion checkpoint
-- 用來看 ingestion 抓到哪裡、有沒有 failed
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
-- 16. 檢查 ingestion jobs
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
-- 17. 可選：刪除錯誤的 backward funding checkpoint
-- 注意：這是 DELETE，只有真的需要重跑時再執行
-- ============================================================

-- DELETE FROM ingestion_checkpoints
-- WHERE source = 'binance'
--   AND dataset = 'funding_rate'
--   AND inst_id IN ('BTCUSDT', 'ETHUSDT')
--   AND direction = 'backward';


-- ============================================================
-- 18. 建立 diagnostics schema / views
-- 跑一次後，以後可以直接 SELECT 這些 views
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


-- ============================================================
-- 19. 建好 views 後的快速查詢
-- ============================================================

SELECT *
FROM diagnostics.v_market_klines_coverage
WHERE exchange = 'binance'
  AND normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
ORDER BY normalized_symbol, bar;


SELECT *
FROM diagnostics.v_canonical_coverage
WHERE inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
ORDER BY inst_id, bar, source_primary;


SELECT *
FROM diagnostics.v_market_funding_coverage
WHERE exchange = 'binance'
  AND normalized_symbol IN ('BTCUSDT', 'ETHUSDT')
ORDER BY normalized_symbol;


SELECT *
FROM diagnostics.v_legacy_funding_coverage
WHERE source = 'binance'
  AND inst_id IN ('BTC-USDT-SWAP', 'ETH-USDT-SWAP')
ORDER BY inst_id;