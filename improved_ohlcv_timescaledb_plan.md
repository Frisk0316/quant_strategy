# Improved Plan: PostgreSQL / TimescaleDB OHLCV Data Pipeline

## 0. Context

The current backtest system reads `1H` Parquet files for only BTC and ETH.  
The next version should support minute-level OHLCV data for the CMC top 15 non-stablecoin crypto perpetual swap pairs on OKX, stored in PostgreSQL + TimescaleDB.

Original requirements:

- Minute-level OHLCV data.
- OKX USDT-margined perpetual SWAP only.
- CMC top 15 non-stablecoin crypto instruments.
- Default bars: `1m`, `5m`, `15m`, `1H`.
- Gap recovery.
- One-click update.
- Manual cross-exchange validation.
- Pair add / remove / list / status management.
- Strategy-driven pair discovery.
- Existing Parquet backtest path should remain compatible.
- Validation is manual-only, not automatic.

This improved plan keeps the original goal but upgrades the database design so that the system becomes:

- Auditable.
- Re-runnable.
- Multi-source compatible.
- Safer for long-term storage.
- Better suited for futures / perpetual swap research.
- Easier to debug when backfills or updates fail.

---

## 1. Key Improvements Over the Original Plan

The previous schema had only one main `candles` hypertable with a `source` column but a unique index on `(inst_id, bar, ts)`. That design prevents storing OKX, Binance, and Bybit versions of the same candle at the same timestamp.

The improved design separates data into two layers:

```text
raw_candles        # Exchange-native data from OKX / Binance / Bybit
canonical_candles  # Cleaned, validated, strategy-ready candles used by backtests
```

Major upgrades:

| Area | Original Design | Improved Design |
|---|---|---|
| Multi-exchange data | One `candles` table with `source` column | Separate `raw_candles` and `canonical_candles` |
| Unique key | `(inst_id, bar, ts)` | Raw: `(source, inst_id, bar, ts)`; canonical: `(inst_id, bar, ts)` |
| Volume | Single `vol` field | `vol_contract`, `vol_base`, `vol_quote` |
| Bar tracking | `tracked_bars TEXT[]` in `instruments` | Separate `instrument_bars` table |
| Instrument metadata | Minimal | Adds exchange, inst_type, quote, settle, tick_size, lot_size, contract_value |
| Quality log | Append-only simple log | Trackable `data_quality_events` with status, severity, job_id, JSON details |
| Job tracking | None | `ingestion_jobs` table for backfill/update/validation auditing |
| Multi-timeframe data | Store all bars directly | Store canonical `1m`; use continuous aggregates for `5m`, `15m`, `1H` |
| Large imports | `executemany` chunks | Optional `COPY` into staging + upsert |
| Compression | Manual only | Compression policy for old chunks |

---

## 2. Target Instruments

Default OKX USDT-margined perpetual SWAP instruments:

```text
BTC-USDT-SWAP
ETH-USDT-SWAP
BNB-USDT-SWAP
SOL-USDT-SWAP
XRP-USDT-SWAP
ADA-USDT-SWAP
DOGE-USDT-SWAP
TON-USDT-SWAP
TRX-USDT-SWAP
LINK-USDT-SWAP
AVAX-USDT-SWAP
MATIC-USDT-SWAP
DOT-USDT-SWAP
SHIB-USDT-SWAP
LTC-USDT-SWAP
```

Default canonical bars:

```text
1m
5m
15m
1H
```

Recommended policy:

- Store canonical `1m` directly.
- Derive canonical `5m`, `15m`, and `1H` from canonical `1m`.
- Store exchange-native `5m`, `15m`, and `1H` in `raw_candles` only when needed for validation or exchange comparison.

---

## 3. Target Architecture

```text
Exchange APIs
  ├── OKX public REST
  ├── Binance public futures REST
  └── Bybit public linear REST
        ↓
Raw ingestion layer
        ↓
raw_candles hypertable
        ↓
Gap detection / retry / quality events
        ↓
Canonicalization
        ↓
canonical_candles hypertable
        ↓
Continuous aggregates
  ├── canonical_candles_5m
  ├── canonical_candles_15m
  └── canonical_candles_1h
        ↓
Backtesting data loader
        ↓
Strategies / reports / pair discovery
```

---

## 4. Database Migration

Create:

```text
src/okx_quant/data/migrations/001_ohlcv_pipeline_v2.sql
```

### 4.1 Extension

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

`pgcrypto` is used for `gen_random_uuid()` in job tracking.

---

## 5. Core Reference Tables

### 5.1 Bar Intervals

```sql
CREATE TABLE IF NOT EXISTS bar_intervals (
    bar           TEXT PRIMARY KEY,
    interval_ms   INTEGER NOT NULL,
    pg_interval   INTERVAL NOT NULL,

    CONSTRAINT ck_bar_intervals_positive
        CHECK (interval_ms > 0)
);

INSERT INTO bar_intervals (bar, interval_ms, pg_interval)
VALUES
    ('1m',  60000,   INTERVAL '1 minute'),
    ('5m',  300000,  INTERVAL '5 minutes'),
    ('15m', 900000,  INTERVAL '15 minutes'),
    ('1H',  3600000, INTERVAL '1 hour')
ON CONFLICT (bar) DO NOTHING;
```

Reason:

- Avoids inconsistent bar labels such as `1h`, `60m`, `60M`, `1H`.
- Gives gap detection a reliable source of interval duration.
- Makes CLI and config validation easier.

---

## 6. Instrument Registry

### 6.1 Instruments

```sql
CREATE TABLE IF NOT EXISTS instruments (
    inst_id          TEXT PRIMARY KEY,          -- Example: BTC-USDT-SWAP
    exchange         TEXT NOT NULL DEFAULT 'okx',
    inst_type        TEXT NOT NULL DEFAULT 'SWAP',
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
    notes            TEXT,

    CONSTRAINT ck_instruments_inst_type
        CHECK (inst_type IN ('SPOT', 'SWAP', 'FUTURES', 'OPTION')),

    CONSTRAINT ck_instruments_exchange
        CHECK (exchange IN ('okx', 'binance', 'bybit', 'coinbase', 'kraken', 'other'))
);
```

Reason:

Perpetual swap backtests eventually need:

- Contract value.
- Tick size.
- Lot size.
- Minimum order size.
- Quote currency.
- Settlement currency.
- Listed / delisted dates.

These fields are not strictly necessary for OHLCV storage, but they are important for realistic PnL, fee, slippage, and position sizing.

---

### 6.2 Instrument Bars

```sql
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
```

Reason:

`first_candle_ts` and `last_candle_ts` should be tracked per `(inst_id, bar)`, not per instrument.

Example:

```text
BTC-USDT-SWAP 1m  last_candle_ts = 2026-05-04 08:59:00 UTC
BTC-USDT-SWAP 1H  last_candle_ts = 2026-05-04 08:00:00 UTC
```

---

## 7. Raw Candles

### 7.1 Raw Candle Table

```sql
CREATE TABLE IF NOT EXISTS raw_candles (
    ts              TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL,             -- okx, binance, bybit
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

    CONSTRAINT ck_raw_candles_source
        CHECK (source IN ('okx', 'binance', 'bybit', 'coinbase', 'kraken', 'manual', 'other')),

    CONSTRAINT ck_raw_candles_ohlc_valid
        CHECK (
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
    'raw_candles',
    'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_candles
ON raw_candles (source, inst_id, bar, ts);

CREATE INDEX IF NOT EXISTS idx_raw_candles_lookup
ON raw_candles (inst_id, bar, source, ts DESC);
```

Reason:

This table stores exchange-native candles without overwriting other exchanges' data.

For OKX SWAP candles:

- `vol_contract`: OKX `vol`.
- `vol_base`: OKX `volCcy`.
- `vol_quote`: OKX `volCcyQuote`.
- `is_closed`: OKX `confirm = 1`.

For Binance / Bybit, map available fields as close as possible.

---

## 8. Canonical Candles

### 8.1 Canonical Candle Table

```sql
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
    quality_status  TEXT NOT NULL DEFAULT 'raw',
    version         INTEGER NOT NULL DEFAULT 1,

    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_canonical_candles_status
        CHECK (quality_status IN ('raw', 'validated', 'corrected', 'suspect')),

    CONSTRAINT ck_canonical_candles_ohlc_valid
        CHECK (
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
    'canonical_candles',
    'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_canonical_candles
ON canonical_candles (inst_id, bar, ts);

CREATE INDEX IF NOT EXISTS idx_canonical_candles_lookup
ON canonical_candles (inst_id, bar, ts DESC);
```

Reason:

Backtests should load from `canonical_candles`, not `raw_candles`.

The `quality_status` field allows the strategy layer to decide whether to use or avoid suspicious data.

---

## 9. Data Quality Events

### 9.1 Quality Event Table

```sql
CREATE TABLE IF NOT EXISTS data_quality_events (
    id               BIGSERIAL PRIMARY KEY,
    logged_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at      TIMESTAMPTZ,

    status           TEXT NOT NULL DEFAULT 'open',
    severity         TEXT NOT NULL DEFAULT 'warning',

    inst_id          TEXT NOT NULL,
    bar              TEXT NOT NULL REFERENCES bar_intervals(bar),
    source           TEXT,

    issue_type       TEXT NOT NULL, -- gap, outlier_flagged, outlier_replaced, fetch_failed, validation_failed

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
    notes            TEXT,

    CONSTRAINT ck_quality_status
        CHECK (status IN ('open', 'resolved', 'ignored')),

    CONSTRAINT ck_quality_severity
        CHECK (severity IN ('info', 'warning', 'critical')),

    CONSTRAINT ck_quality_issue_type
        CHECK (
            issue_type IN (
                'gap',
                'outlier_flagged',
                'outlier_replaced',
                'fetch_failed',
                'validation_failed',
                'schema_violation',
                'incomplete_candle'
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_quality_events_open
ON data_quality_events (inst_id, bar, status, severity, logged_at DESC);

CREATE INDEX IF NOT EXISTS idx_quality_events_job
ON data_quality_events (job_id);
```

Reason:

This replaces the simpler `data_quality_log`.

Benefits:

- Can track whether a problem is still open.
- Can group issues by `job_id`.
- Can store extra structured details in `JSONB`.
- Can support `manage_pairs.py status`.

---

## 10. Ingestion Jobs

### 10.1 Job Tracking Table

```sql
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    job_type        TEXT NOT NULL, -- backfill, update_all, validate, canonicalize, repair_gap
    source          TEXT NOT NULL,

    inst_id         TEXT,
    bar             TEXT REFERENCES bar_intervals(bar),

    start_ts        TIMESTAMPTZ,
    end_ts          TIMESTAMPTZ,

    status          TEXT NOT NULL DEFAULT 'running', -- running, success, failed, partial

    rows_fetched    INTEGER NOT NULL DEFAULT 0,
    rows_inserted   INTEGER NOT NULL DEFAULT 0,
    rows_updated    INTEGER NOT NULL DEFAULT 0,
    rows_skipped    INTEGER NOT NULL DEFAULT 0,

    gaps_found      INTEGER NOT NULL DEFAULT 0,
    outliers_found  INTEGER NOT NULL DEFAULT 0,

    error_message   TEXT,
    details         JSONB,

    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,

    CONSTRAINT ck_ingestion_jobs_type
        CHECK (job_type IN ('backfill', 'update_all', 'validate', 'canonicalize', 'repair_gap', 'discover_pairs')),

    CONSTRAINT ck_ingestion_jobs_status
        CHECK (status IN ('running', 'success', 'failed', 'partial'))
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_lookup
ON ingestion_jobs (job_type, status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_inst_bar
ON ingestion_jobs (inst_id, bar, started_at DESC);
```

Reason:

Without this table, large historical imports are hard to debug.

Example use:

```text
Which pair failed during last night's update?
Which time window had persistent gaps?
How many rows were inserted during the last backfill?
Did validation replace or only flag outliers?
```

---

## 11. Optional Futures / Derivatives Tables

These are not required for OHLCV backtesting but are recommended for future strategy research.

### 11.1 Funding Rates

```sql
CREATE TABLE IF NOT EXISTS funding_rates (
    ts              TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL DEFAULT 'okx',
    inst_id         TEXT NOT NULL REFERENCES instruments(inst_id),
    funding_rate    DOUBLE PRECISION NOT NULL,
    next_funding_ts TIMESTAMPTZ,
    raw_payload     JSONB,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable(
    'funding_rates',
    'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_funding_rates
ON funding_rates (source, inst_id, ts);
```

### 11.2 Open Interest

```sql
CREATE TABLE IF NOT EXISTS open_interest (
    ts              TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL DEFAULT 'okx',
    inst_id         TEXT NOT NULL REFERENCES instruments(inst_id),
    oi_contract     DOUBLE PRECISION,
    oi_base         DOUBLE PRECISION,
    oi_quote        DOUBLE PRECISION,
    raw_payload     JSONB,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable(
    'open_interest',
    'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_open_interest
ON open_interest (source, inst_id, ts);
```

### 11.3 Mark / Index Prices

```sql
CREATE TABLE IF NOT EXISTS mark_prices (
    ts              TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL DEFAULT 'okx',
    inst_id         TEXT NOT NULL REFERENCES instruments(inst_id),
    mark_price      DOUBLE PRECISION NOT NULL,
    index_price     DOUBLE PRECISION,
    raw_payload     JSONB,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable(
    'mark_prices',
    'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_mark_prices
ON mark_prices (source, inst_id, ts);
```

---

## 12. Continuous Aggregates

Recommended canonical policy:

- Store `1m` in `canonical_candles`.
- Build `5m`, `15m`, `1H` from `1m` using TimescaleDB continuous aggregates.
- Use exchange-native higher timeframe bars only for validation.

### 12.1 5-Minute Aggregate

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS canonical_candles_5m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '5 minutes', ts) AS ts,
    inst_id,
    '5m'::TEXT AS bar,
    first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, ts) AS close,
    sum(vol_contract) AS vol_contract,
    sum(vol_base) AS vol_base,
    sum(vol_quote) AS vol_quote,
    min(quality_status) AS quality_status
FROM canonical_candles
WHERE bar = '1m'
GROUP BY inst_id, time_bucket(INTERVAL '5 minutes', ts)
WITH NO DATA;
```

### 12.2 15-Minute Aggregate

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS canonical_candles_15m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '15 minutes', ts) AS ts,
    inst_id,
    '15m'::TEXT AS bar,
    first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, ts) AS close,
    sum(vol_contract) AS vol_contract,
    sum(vol_base) AS vol_base,
    sum(vol_quote) AS vol_quote,
    min(quality_status) AS quality_status
FROM canonical_candles
WHERE bar = '1m'
GROUP BY inst_id, time_bucket(INTERVAL '15 minutes', ts)
WITH NO DATA;
```

### 12.3 1-Hour Aggregate

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS canonical_candles_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 hour', ts) AS ts,
    inst_id,
    '1H'::TEXT AS bar,
    first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, ts) AS close,
    sum(vol_contract) AS vol_contract,
    sum(vol_base) AS vol_base,
    sum(vol_quote) AS vol_quote,
    min(quality_status) AS quality_status
FROM canonical_candles
WHERE bar = '1m'
GROUP BY inst_id, time_bucket(INTERVAL '1 hour', ts)
WITH NO DATA;
```

### 12.4 Refresh Policies

```sql
SELECT add_continuous_aggregate_policy(
    'canonical_candles_5m',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes'
);

SELECT add_continuous_aggregate_policy(
    'canonical_candles_15m',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes'
);

SELECT add_continuous_aggregate_policy(
    'canonical_candles_1h',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour'
);
```

---

## 13. Compression

Enable compression for long-term historical data.

```sql
ALTER TABLE raw_candles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'source,inst_id,bar',
    timescaledb.compress_orderby = 'ts DESC'
);

ALTER TABLE canonical_candles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'inst_id,bar',
    timescaledb.compress_orderby = 'ts DESC'
);

SELECT add_compression_policy('raw_candles', INTERVAL '30 days');
SELECT add_compression_policy('canonical_candles', INTERVAL '30 days');
```

Do not compress very recent chunks because:

- `update_all.py` may need to insert missing recent candles.
- `validate.py --replace` may update recent outliers.
- Gap repair may need to rewrite recent windows.

---

## 14. File Structure

### 14.1 New Files

```text
src/okx_quant/data/
    migrations/
        001_ohlcv_pipeline_v2.sql

    candle_store.py
    canonicalizer.py
    gap_detector.py
    job_logger.py

    exchange_clients/
        okx_public.py
        binance_public.py
        bybit_public.py

    validators/
        cross_exchange.py

scripts/market_data/
    __init__.py
    init_db.py
    backfill.py
    update_all.py
    validate.py
    manage_pairs.py
    discover_pairs.py
    repair_gaps.py
```

### 14.2 Files to Modify

```text
config/settings.yaml
src/okx_quant/core/config.py
backtesting/data_loader.py
pyproject.toml
```

---

## 15. Core Python Interfaces

### 15.1 `src/okx_quant/data/candle_store.py`

```python
class CandleStore:
    @classmethod
    async def from_dsn(cls, dsn: str, min_size: int = 2, max_size: int = 10) -> "CandleStore":
        ...

    async def close(self) -> None:
        ...

    # Instrument registry

    async def register_instrument(
        self,
        inst_id: str,
        base_ccy: str,
        quote_ccy: str = "USDT",
        settle_ccy: str = "USDT",
        exchange: str = "okx",
        inst_type: str = "SWAP",
        contract_value: float | None = None,
        tick_size: float | None = None,
        lot_size: float | None = None,
        min_size: float | None = None,
    ) -> None:
        ...

    async def register_instrument_bar(self, inst_id: str, bar: str) -> None:
        ...

    async def set_instrument_active(self, inst_id: str, active: bool) -> None:
        ...

    async def set_instrument_bar_active(self, inst_id: str, bar: str, active: bool) -> None:
        ...

    async def get_active_instrument_bars(self) -> list[dict]:
        ...

    # Job tracking

    async def start_job(
        self,
        job_type: str,
        source: str,
        inst_id: str | None = None,
        bar: str | None = None,
        start_ts=None,
        end_ts=None,
        details: dict | None = None,
    ) -> str:
        ...

    async def finish_job(
        self,
        job_id: str,
        status: str,
        rows_fetched: int = 0,
        rows_inserted: int = 0,
        rows_updated: int = 0,
        rows_skipped: int = 0,
        gaps_found: int = 0,
        outliers_found: int = 0,
        error_message: str | None = None,
        details: dict | None = None,
    ) -> None:
        ...

    # Raw candles

    async def upsert_raw_candles(
        self,
        rows: list[dict],
        source: str,
        inst_id: str,
        bar: str,
    ) -> dict:
        """
        Expected row keys:
        - ts_ms
        - open
        - high
        - low
        - close
        - vol_contract
        - vol_base
        - vol_quote
        - is_closed
        - raw_payload
        """
        ...

    async def get_raw_candles(
        self,
        source: str,
        inst_id: str,
        bar: str,
        start=None,
        end=None,
    ):
        ...

    # Canonical candles

    async def upsert_canonical_candles(
        self,
        rows: list[dict],
        inst_id: str,
        bar: str,
        source_primary: str = "okx",
        quality_status: str = "raw",
    ) -> dict:
        ...

    async def canonicalize_from_raw(
        self,
        source: str,
        inst_id: str,
        bar: str,
        start=None,
        end=None,
    ) -> dict:
        """
        Copies clean closed candles from raw_candles into canonical_candles.
        Usually source='okx'.
        """
        ...

    async def get_canonical_candles(
        self,
        inst_id: str,
        bar: str,
        start=None,
        end=None,
        include_suspect: bool = False,
    ):
        """
        Returns tz-aware UTC DatetimeIndex with:
        [open, high, low, close, vol_contract, vol_base, vol_quote]
        """
        ...

    async def get_last_canonical_ts(self, inst_id: str, bar: str) -> int | None:
        ...

    async def update_instrument_bar_bounds(self, inst_id: str, bar: str) -> None:
        ...

    # Gap detection

    async def detect_gaps(
        self,
        inst_id: str,
        bar: str,
        start,
        end,
        table: str = "canonical_candles",
    ) -> list[tuple]:
        ...

    async def log_quality_event(
        self,
        inst_id: str,
        bar: str,
        issue_type: str,
        severity: str = "warning",
        status: str = "open",
        source: str | None = None,
        window_start=None,
        window_end=None,
        affected_count: int | None = None,
        field: str | None = None,
        observed_value: float | None = None,
        reference_value: float | None = None,
        z_score: float | None = None,
        action_taken: str | None = None,
        retry_count: int = 0,
        job_id: str | None = None,
        details: dict | None = None,
        notes: str | None = None,
    ) -> None:
        ...
```

---

## 16. Gap Detection SQL

```sql
SELECT gs.ts
FROM generate_series(
    $1::timestamptz,
    $2::timestamptz,
    $3::interval
) AS gs(ts)
LEFT JOIN canonical_candles c
    ON c.ts = gs.ts
    AND c.inst_id = $4
    AND c.bar = $5
WHERE c.ts IS NULL
ORDER BY 1;
```

Recommended behavior:

- Detect gaps after each backfill chunk.
- Retry missing windows up to 3 times.
- Use exponential backoff.
- If still missing, log `data_quality_events.issue_type = 'gap'`.
- Do not silently ignore persistent gaps.

---

## 17. Exchange Clients

### 17.1 `okx_public.py`

```python
class OKXPublicClient:
    def get_history_candles(
        self,
        inst_id: str,
        bar: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Returns rows normalized to:
        {
            "ts_ms": int,
            "open": float,
            "high": float,
            "low": float,
            "close": float,
            "vol_contract": float,
            "vol_base": float,
            "vol_quote": float,
            "is_closed": bool,
            "raw_payload": dict,
        }
        """
        ...
```

### 17.2 `binance_public.py`

```python
class BinancePublicClient:
    def get_klines(
        self,
        symbol: str,
        interval: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 500,
        market_type: str = "futures",
    ) -> list[dict]:
        """
        market_type:
        - "spot"    -> api.binance.com
        - "futures" -> fapi.binance.com
        """
        ...
```

### 17.3 `bybit_public.py`

```python
class BybitPublicClient:
    def get_kline(
        self,
        symbol: str,
        interval: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 200,
        category: str = "linear",
    ) -> list[dict]:
        """
        interval map:
        - 1m  -> "1"
        - 5m  -> "5"
        - 15m -> "15"
        - 1H  -> "60"
        """
        ...
```

---

## 18. Cross-Exchange Validation

### 18.1 `validators/cross_exchange.py`

```python
SYMBOL_MAP: dict[str, dict] = {
    "BTC-USDT-SWAP": {
        "binance": "BTCUSDT",
        "binance_type": "futures",
        "bybit": "BTCUSDT",
        "bybit_cat": "linear",
    },
    # Add remaining instruments.
}

INTERVAL_MAP = {
    "1m":  {"binance": "1m",  "bybit": "1"},
    "5m":  {"binance": "5m",  "bybit": "5"},
    "15m": {"binance": "15m", "bybit": "15"},
    "1H":  {"binance": "1h",  "bybit": "60"},
}
```

```python
class CrossExchangeValidator:
    def __init__(
        self,
        store: CandleStore,
        sigma_threshold: float = 3.0,
        replace_outliers: bool = False,
    ):
        ...

    async def validate_window(
        self,
        inst_id: str,
        bar: str,
        start,
        end,
        replace: bool = False,
        job_id: str | None = None,
    ) -> dict:
        """
        1. Load canonical candles.
        2. Fetch same window from Binance and Bybit if available.
        3. Compare OHLC fields.
        4. Compute robust reference median.
        5. Flag values whose deviation is too large.
        6. Optionally replace canonical values.
        7. Log events to data_quality_events.
        """
        ...
```

### 18.2 Validation Algorithm

For each timestamp and field:

```text
reference = median([okx_value, binance_value, bybit_value])
scale = robust_std_or_mad(values)

z = abs(okx_value - reference) / scale
```

If:

```text
z > sigma_threshold
```

Then:

- Log `outlier_flagged`.
- If `--replace` is set:
  - Replace canonical value with reference median.
  - Set `quality_status = 'corrected'`.
  - Log `outlier_replaced`.

Important:

- If Binance or Bybit does not support a pair, skip that source gracefully.
- If only one external source is available, validate with lower confidence.
- If no external source is available, do not fail the entire validation job.

---

## 19. Data Flows

## A. Database Initialization

Script:

```text
scripts/market_data/init_db.py
```

CLI:

```bash
python scripts/market_data/init_db.py
```

Steps:

1. Read `config/settings.yaml`.
2. Connect to TimescaleDB.
3. Apply `001_ohlcv_pipeline_v2.sql`.
4. Insert default `bar_intervals`.
5. Seed `instruments`.
6. Seed `instrument_bars`.
7. Print summary.

Expected output:

```text
Initialized OHLCV database.
Seeded instruments: 15
Seeded instrument bars: 60
```

---

## B. Historical Backfill

Script:

```text
scripts/market_data/backfill.py
```

CLI:

```bash
python scripts/market_data/backfill.py     --inst BTC-USDT-SWAP     --bar 1m     --start 2024-01-01     --end 2026-05-04
```

Steps:

1. Start `ingestion_jobs` row with `job_type = 'backfill'`.
2. Register instrument and instrument bar if missing.
3. Fetch OKX historical candles in chunks.
4. Normalize to `raw_candles` row shape.
5. Upsert into `raw_candles`.
6. Canonicalize from OKX raw candles into `canonical_candles`.
7. Detect gaps in `canonical_candles`.
8. Retry gap windows up to 3 times.
9. Log persistent gaps to `data_quality_events`.
10. Update `instrument_bars.first_candle_ts` and `last_candle_ts`.
11. Finish job with success / partial / failed status.

Important:

- `--source okx` should be default.
- Backfill should prioritize `1m`.
- Higher timeframe raw bars may be fetched only when `--raw-bars 5m 15m 1H` is explicitly requested.
- Avoid automatic validation during backfill. Validation remains manual.

---

## C. One-Click Update

Script:

```text
scripts/market_data/update_all.py
```

CLI:

```bash
python scripts/market_data/update_all.py
```

Optional:

```bash
python scripts/market_data/update_all.py --concurrency 1
```

Steps:

1. Start `ingestion_jobs` row with `job_type = 'update_all'`.
2. Query active `(inst_id, bar)` from `instrument_bars`.
3. For each active pair/bar:
   - Get `last_candle_ts`.
   - Start from `last_candle_ts + interval`.
   - Skip if already up to date.
   - Fetch OKX candles.
   - Upsert into `raw_candles`.
   - Canonicalize into `canonical_candles`.
   - Detect gaps.
   - Retry missing windows.
   - Log persistent issues.
   - Update bounds.
4. Print per-pair summary table.
5. Finish job.

Recommended default:

```text
--concurrency 1
```

Reason:

Public market data APIs have rate limits. Start safely, then increase concurrency only after adding rate limiters.

---

## D. Manual Cross-Exchange Validation

Script:

```text
scripts/market_data/validate.py
```

CLI:

```bash
python scripts/market_data/validate.py     --inst BTC-USDT-SWAP     --bar 1H     --window-days 7
```

With replacement:

```bash
python scripts/market_data/validate.py     --inst BTC-USDT-SWAP     --bar 1H     --window-days 7     --replace
```

Steps:

1. Start `ingestion_jobs` row with `job_type = 'validate'`.
2. Load canonical candles for the selected window.
3. Fetch same window from Binance and Bybit.
4. Compare OHLC fields.
5. Log outliers to `data_quality_events`.
6. If `--replace`, update canonical candles and set `quality_status = 'corrected'`.
7. Finish job.

Manual-only rule:

- `backfill.py` and `update_all.py` should not automatically replace outliers.
- Validation should be intentionally triggered by the user.

---

## E. Gap Repair

Script:

```text
scripts/market_data/repair_gaps.py
```

CLI:

```bash
python scripts/market_data/repair_gaps.py     --inst BTC-USDT-SWAP     --bar 1m     --start 2026-05-01     --end 2026-05-04
```

Steps:

1. Detect gaps in selected window.
2. Group consecutive missing timestamps into ranges.
3. Fetch missing ranges from OKX.
4. Upsert raw candles.
5. Canonicalize.
6. Re-run gap detection.
7. Mark resolved events as `status = 'resolved'` if fixed.
8. Create new quality events for persistent gaps.

---

## F. Pair Management

Script:

```text
scripts/market_data/manage_pairs.py
```

### Add Pairs

```bash
python scripts/market_data/manage_pairs.py add     --inst-ids BNB-USDT-SWAP SOL-USDT-SWAP     --bars 1m 5m 15m 1H
```

Optional backfill:

```bash
python scripts/market_data/manage_pairs.py add     --inst-ids BNB-USDT-SWAP SOL-USDT-SWAP     --bars 1m     --backfill-days 30
```

Behavior:

- Inserts into `instruments`.
- Inserts into `instrument_bars`.
- Does not delete existing data.
- If `--backfill-days` is provided, triggers backfill for the requested range.

### Remove Pair

```bash
python scripts/market_data/manage_pairs.py remove     --inst-id SHIB-USDT-SWAP
```

Behavior:

- Sets `instruments.is_active = FALSE`.
- Sets `instrument_bars.is_active = FALSE`.
- Stamps `archived_at`.
- Does not delete candle data.

### Purge Pair

```bash
python scripts/market_data/manage_pairs.py purge     --inst-id SHIB-USDT-SWAP     --confirm SHIB-USDT-SWAP
```

Behavior:

- Hard-deletes raw candles, canonical candles, instrument bars, and instrument row.
- Should require explicit confirmation.

### List Pairs

```bash
python scripts/market_data/manage_pairs.py list
```

Expected table:

```text
inst_id         active  bars              first_1m              last_1m
BTC-USDT-SWAP   yes     1m,5m,15m,1H      2024-01-01 00:00      2026-05-04 08:59
ETH-USDT-SWAP   yes     1m,5m,15m,1H      2024-01-01 00:00      2026-05-04 08:59
```

### Pair Status

```bash
python scripts/market_data/manage_pairs.py status     --inst-id BTC-USDT-SWAP
```

Expected output:

```text
BTC-USDT-SWAP

Bars:
  1m   first: 2024-01-01 00:00 UTC   last: 2026-05-04 08:59 UTC
  5m   derived from 1m
  15m  derived from 1m
  1H   derived from 1m

Quality:
  open gaps: 0
  unresolved outliers: 2
  last update job: success
  last validation job: partial
```

---

## G. Strategy-Based Discovery

Script:

```text
scripts/market_data/discover_pairs.py
```

### Pairs Trading

```bash
python scripts/market_data/discover_pairs.py     --strategy pairs_trading     --bar 1H     --lookback-days 90     --top-n 10     --p-value 0.05
```

Steps:

1. Load canonical close prices for all active SWAP instruments.
2. Align timestamps.
3. Drop pairs with insufficient overlap.
4. Compute log prices.
5. Run Engle-Granger cointegration test.
6. Estimate OU half-life.
7. Sort by p-value and half-life.
8. Print top N.
9. Optionally save to CSV.

Expected output:

```text
base_pair                      p_value   half_life   overlap
BTC-USDT-SWAP / ETH-USDT-SWAP  0.012     18.4        0.98
```

### Funding Carry

```bash
python scripts/market_data/discover_pairs.py     --strategy funding_carry     --min-apr 0.12     --top-n 10
```

Recommended improvement:

- Store funding history in `funding_rates`.
- Use historical average funding, not only current live funding.
- Rank by annualized funding, volatility, and liquidity.

---

## 20. Backtest Integration

File:

```text
backtesting/data_loader.py
```

Keep existing Parquet behavior as default.

```python
def load_candles(
    inst_id: str,
    bar: str = "1m",
    data_dir: str = "data/ticks",
    start=None,
    end=None,
    backend: str = "parquet",
    dsn: str | None = None,
    include_suspect: bool = False,
) -> pd.DataFrame:
    if backend == "postgres":
        return _load_candles_pg(
            inst_id=inst_id,
            bar=bar,
            dsn=dsn,
            start=start,
            end=end,
            include_suspect=include_suspect,
        )

    return _load_candles_parquet(
        inst_id=inst_id,
        bar=bar,
        data_dir=data_dir,
        start=start,
        end=end,
    )
```

Postgres behavior:

```python
def _load_candles_pg(
    inst_id: str,
    bar: str,
    dsn: str,
    start=None,
    end=None,
    include_suspect: bool = False,
) -> pd.DataFrame:
    """
    Uses CandleStore.get_canonical_candles().
    Returns a DataFrame compatible with the old Parquet loader.

    Output columns:
    - open
    - high
    - low
    - close
    - vol

    For backward compatibility:
    - vol should map to vol_quote if available.
    - fallback to vol_base.
    - fallback to vol_contract.
    """
    ...
```

Important compatibility rule:

- Existing tests should still pass with `backend="parquet"`.
- PostgreSQL backend should be opt-in at first.
- Later, switch default in `settings.yaml`.

---

## 21. Config Changes

File:

```text
config/settings.yaml
```

Add:

```yaml
storage:
  candle_backend: parquet
  timescale_dsn: "postgresql://quant:changeme@localhost:5432/okx_quant"

market_data:
  source_primary: okx

  canonical:
    base_bar: 1m
    derived_bars: [5m, 15m, 1H]

  bars: [1m, 5m, 15m, 1H]

  instruments:
    - BTC-USDT-SWAP
    - ETH-USDT-SWAP
    - BNB-USDT-SWAP
    - SOL-USDT-SWAP
    - XRP-USDT-SWAP
    - ADA-USDT-SWAP
    - DOGE-USDT-SWAP
    - TON-USDT-SWAP
    - TRX-USDT-SWAP
    - LINK-USDT-SWAP
    - AVAX-USDT-SWAP
    - MATIC-USDT-SWAP
    - DOT-USDT-SWAP
    - SHIB-USDT-SWAP
    - LTC-USDT-SWAP

  validation:
    manual_only: true
    sigma_threshold: 3.0
    replace_outliers_default: false
    sources: [binance, bybit]

  ingestion:
    default_concurrency: 1
    max_retries: 3
    retry_backoff_seconds: [1, 3, 9]
    chunk_days:
      1m: 7
      5m: 30
      15m: 60
      1H: 180
```

---

## 22. Pydantic Config Updates

File:

```text
src/okx_quant/core/config.py
```

Add:

```python
from typing import Literal
from pydantic import BaseModel


class MarketDataCanonicalConfig(BaseModel):
    base_bar: str = "1m"
    derived_bars: list[str] = ["5m", "15m", "1H"]


class MarketDataValidationConfig(BaseModel):
    manual_only: bool = True
    sigma_threshold: float = 3.0
    replace_outliers_default: bool = False
    sources: list[str] = ["binance", "bybit"]


class MarketDataIngestionConfig(BaseModel):
    default_concurrency: int = 1
    max_retries: int = 3
    retry_backoff_seconds: list[int] = [1, 3, 9]
    chunk_days: dict[str, int] = {
        "1m": 7,
        "5m": 30,
        "15m": 60,
        "1H": 180,
    }


class MarketDataConfig(BaseModel):
    source_primary: str = "okx"
    canonical: MarketDataCanonicalConfig = MarketDataCanonicalConfig()
    bars: list[str] = ["1m", "5m", "15m", "1H"]
    instruments: list[str] = []
    validation: MarketDataValidationConfig = MarketDataValidationConfig()
    ingestion: MarketDataIngestionConfig = MarketDataIngestionConfig()
```

Modify `StorageConfig`:

```python
class StorageConfig(BaseModel):
    candle_backend: Literal["parquet", "postgres"] = "parquet"
    timescale_dsn: str = "postgresql://quant:changeme@localhost:5432/okx_quant"
```

---

## 23. Dependency Changes

File:

```text
pyproject.toml
```

Add:

```toml
dependencies = [
    "asyncpg>=0.29",
    "click>=8.1",
]
```

If using rich CLI tables:

```toml
dependencies = [
    "rich>=13.0",
]
```

If using pair discovery:

```toml
dependencies = [
    "statsmodels>=0.14",
]
```

---

## 24. Implementation Sequence for Codex

| Phase | Files | Goal |
|---|---|---|
| 1 | `001_ohlcv_pipeline_v2.sql` | Create improved schema |
| 2 | `config.py`, `settings.yaml` | Add market data config |
| 3 | `candle_store.py`, `job_logger.py` | Build async DB layer |
| 4 | `okx_public.py` | Fetch and normalize OKX candles |
| 5 | `init_db.py` | Apply schema and seed instruments |
| 6 | `backfill.py` | Historical backfill into raw + canonical |
| 7 | `gap_detector.py`, `repair_gaps.py` | Detect and repair missing candles |
| 8 | `update_all.py` | One-click incremental update |
| 9 | `binance_public.py`, `bybit_public.py`, `cross_exchange.py`, `validate.py` | Manual validation |
| 10 | `manage_pairs.py` | Add / remove / list / status |
| 11 | `discover_pairs.py` | Strategy-driven discovery |
| 12 | `data_loader.py` | Add PostgreSQL backend |
| 13 | Tests | Unit + integration tests |

---

## 25. Verification Checklist

### 25.1 Start Database

```bash
docker compose -f docker/docker-compose.yml up -d timescaledb
```

### 25.2 Apply Schema

```bash
python scripts/market_data/init_db.py
```

### 25.3 Smoke Backfill

```bash
python scripts/market_data/backfill.py     --inst BTC-USDT-SWAP     --bar 1m     --start 2026-04-27     --end 2026-05-04
```

### 25.4 List Pairs

```bash
python scripts/market_data/manage_pairs.py list
```

### 25.5 Check Pair Status

```bash
python scripts/market_data/manage_pairs.py status     --inst BTC-USDT-SWAP
```

### 25.6 One-Click Update

```bash
python scripts/market_data/update_all.py
```

### 25.7 Manual Validation

```bash
python scripts/market_data/validate.py     --inst BTC-USDT-SWAP     --bar 1H     --window-days 7
```

### 25.8 Manual Validation With Replacement

```bash
python scripts/market_data/validate.py     --inst BTC-USDT-SWAP     --bar 1H     --window-days 7     --replace
```

### 25.9 Gap Repair

```bash
python scripts/market_data/repair_gaps.py     --inst BTC-USDT-SWAP     --bar 1m     --start 2026-05-01     --end 2026-05-04
```

### 25.10 Pair Discovery

```bash
python scripts/market_data/discover_pairs.py     --strategy pairs_trading     --bar 1H     --lookback-days 90     --top-n 5
```

### 25.11 Backtest Compatibility

```bash
pytest tests/unit/test_backtesting.py -v
```

### 25.12 PostgreSQL Backend Test

```bash
python - <<'PY'
from backtesting.data_loader import load_candles

df = load_candles(
    inst_id="BTC-USDT-SWAP",
    bar="1m",
    backend="postgres",
    dsn="postgresql://quant:changeme@localhost:5432/okx_quant",
    start="2026-05-01",
    end="2026-05-04",
)

print(df.head())
print(df.tail())
print(df.shape)
PY
```

---

## 26. Testing Plan

### 26.1 Unit Tests

Create tests for:

```text
tests/unit/data/test_bar_intervals.py
tests/unit/data/test_candle_store.py
tests/unit/data/test_gap_detector.py
tests/unit/data/test_canonicalizer.py
tests/unit/data/test_cross_exchange_validator.py
```

Test cases:

- Insert instrument.
- Insert instrument bars.
- Upsert raw candles.
- Upsert canonical candles.
- Duplicate upserts are idempotent.
- OHLC invalid values are rejected.
- Gap detection works.
- Quality events are logged.
- Job lifecycle works.
- Missing Binance / Bybit pair does not fail validation.
- `include_suspect=False` excludes suspect candles.

### 26.2 Integration Tests

Create:

```text
tests/integration/test_market_data_pipeline.py
```

Test with small local TimescaleDB container:

1. Apply migration.
2. Insert one instrument.
3. Insert `1m` candles.
4. Detect no gaps.
5. Delete one candle.
6. Detect one gap.
7. Repair gap.
8. Verify canonical data is complete.

---

## 27. Known Risks and Mitigations

### 27.1 OKX Rate Limits

Risk:

- Historical `1m` data for 15 pairs across multiple years creates many requests.

Mitigation:

- Use conservative concurrency.
- Use chunked backfills.
- Store raw responses idempotently.
- Resume from last successful job.
- Prefer `1m` first, then derive higher timeframes.

---

### 27.2 Compressed Chunks Are Harder to Update

Risk:

- Older chunks may need repair or correction.

Mitigation:

- Compress only chunks older than 30 days.
- Add maintenance command to decompress selected chunks if repair is required.
- Avoid automatic replacement of old data unless explicitly requested.

---

### 27.3 Binance / Bybit Symbol Coverage

Risk:

- Not every OKX SWAP pair exists on Binance or Bybit.

Mitigation:

- Keep `SYMBOL_MAP`.
- Skip missing sources gracefully.
- Validation should return `partial`, not `failed`, when one source is missing.

---

### 27.4 Incomplete Latest Candle

Risk:

- Latest live candle may not be closed.

Mitigation:

- Respect `is_closed`.
- Canonicalize only closed candles by default.
- Add `--include-open-candle` only for live dashboards, not backtests.

---

### 27.5 Volume Semantics Differ Across Exchanges

Risk:

- `vol` may mean contract volume, base volume, or quote volume depending on source and instrument type.

Mitigation:

- Store `vol_contract`, `vol_base`, and `vol_quote`.
- For strategy liquidity filters, prefer `vol_quote`.
- Keep `raw_payload` for audit.

---

### 27.6 `asyncio.run()` in Backtest Loader

Risk:

- Works in sync scripts, but may fail in an existing async event loop.

Mitigation:

- Keep sync wrapper for backtest scripts.
- Provide async variant for FastAPI or async research notebooks:

```python
async def load_candles_async(...):
    ...
```

---

## 28. Recommended Minimum Viable Build

If implementation time is limited, build in this order:

### P0

- `instruments`
- `instrument_bars`
- `raw_candles`
- `canonical_candles`
- `ingestion_jobs`
- `data_quality_events`
- OKX backfill
- OKX update_all
- PostgreSQL backtest loader

### P1

- Gap repair.
- Manual validation with Binance / Bybit.
- Pair management CLI.
- Continuous aggregates.

### P2

- Funding rates.
- Open interest.
- Mark prices.
- Pair discovery.
- Rich CLI output.
- Compression policies.
- Advanced validation.

---

## 29. Final Codex Instruction

Implement this as a backward-compatible market data upgrade.

Do not remove the existing Parquet loader.  
Add PostgreSQL as an optional backend first.

Required behavior:

1. Raw exchange candles must be stored in `raw_candles`.
2. Backtests must read from `canonical_candles` or continuous aggregates.
3. Do not overwrite exchange-specific raw data.
4. Use `(source, inst_id, bar, ts)` as the raw candle unique key.
5. Use `(inst_id, bar, ts)` as the canonical candle unique key.
6. Store `vol_contract`, `vol_base`, and `vol_quote`.
7. Track first and last candle timestamps in `instrument_bars`.
8. Every backfill, update, validation, and repair job must create an `ingestion_jobs` record.
9. Every persistent gap, fetch failure, validation failure, or outlier must create a `data_quality_events` record.
10. Validation must be manual-only.
11. Replacement of outliers must require an explicit `--replace` flag.
12. Existing unit tests using Parquet must continue to pass.
13. New PostgreSQL tests should be added without breaking the current backtesting workflow.

---

## 30. Summary

The improved design turns the original OHLCV plan into a production-grade research data pipeline.

Core principle:

```text
raw_candles are for audit.
canonical_candles are for backtests.
instrument_bars are for update state.
ingestion_jobs are for debugging.
data_quality_events are for trust.
```

This structure makes the system suitable for long-term minute-level crypto SWAP backtesting while keeping enough flexibility for validation, repair, funding strategies, and future expansion.
