-- Per-venue instrument specs. Keyed by (exchange, canonical symbol).
-- ct_val is the contract multiplier used by PnL/notional/sizing; it is a
-- property of the execution venue, not of the price-data source. See ADR-0007.
CREATE TABLE IF NOT EXISTS venue_instrument_specs (
    exchange    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    ct_val      DOUBLE PRECISION NOT NULL CHECK (ct_val > 0),
    lot_size    DOUBLE PRECISION NOT NULL CHECK (lot_size > 0),
    tick_size   DOUBLE PRECISION NOT NULL CHECK (tick_size > 0),
    min_size    DOUBLE PRECISION NOT NULL CHECK (min_size > 0),
    source      TEXT NOT NULL DEFAULT 'db',   -- provenance label; 'db' = verified upstream
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (exchange, symbol)
);
