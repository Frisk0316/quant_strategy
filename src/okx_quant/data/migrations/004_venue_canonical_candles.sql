-- Additive source-aware canonical layer. The existing canonical_candles table
-- remains the priority-resolved default and continues to own all CAGGs.

CREATE TABLE IF NOT EXISTS venue_canonical_candles (
    ts              TIMESTAMPTZ NOT NULL,
    source_primary  TEXT NOT NULL,
    inst_id         TEXT NOT NULL REFERENCES instruments(inst_id),
    bar             TEXT NOT NULL REFERENCES bar_intervals(bar),
    open            DOUBLE PRECISION NOT NULL,
    high            DOUBLE PRECISION NOT NULL,
    low             DOUBLE PRECISION NOT NULL,
    close           DOUBLE PRECISION NOT NULL,
    vol_contract    DOUBLE PRECISION,
    vol_base        DOUBLE PRECISION,
    vol_quote       DOUBLE PRECISION,
    quality_status  TEXT NOT NULL DEFAULT 'raw'
        CHECK (quality_status IN ('raw', 'validated', 'corrected', 'suspect')),
    version         INTEGER NOT NULL DEFAULT 1,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_venue_canonical_ohlc CHECK (
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
    'venue_canonical_candles', 'ts',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_venue_canonical_candles
    ON venue_canonical_candles (source_primary, inst_id, bar, ts);

CREATE INDEX IF NOT EXISTS idx_venue_canonical_candles_lookup
    ON venue_canonical_candles (inst_id, bar, source_primary, ts DESC);

ALTER TABLE venue_canonical_candles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'source_primary,inst_id,bar',
    timescaledb.compress_orderby = 'ts DESC'
);

SELECT add_compression_policy('venue_canonical_candles', INTERVAL '30 days', if_not_exists => TRUE);

CREATE OR REPLACE VIEW canonical_candles_by_source AS
SELECT
    c.ts, c.inst_id, c.bar, c.open, c.high, c.low, c.close,
    c.vol_contract, c.vol_base, c.vol_quote, c.source_primary,
    c.quality_status, c.version, c.ingested_at, c.updated_at
FROM canonical_candles c
UNION ALL
SELECT
    v.ts, v.inst_id, v.bar, v.open, v.high, v.low, v.close,
    v.vol_contract, v.vol_base, v.vol_quote, v.source_primary,
    v.quality_status, v.version, v.ingested_at, v.updated_at
FROM venue_canonical_candles v
WHERE NOT EXISTS (
    SELECT 1
    FROM canonical_candles c
    WHERE c.inst_id = v.inst_id
      AND c.bar = v.bar
      AND c.ts = v.ts
      AND c.source_primary = v.source_primary
);

