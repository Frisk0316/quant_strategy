-- ============================================================
-- Migration 002: Bridge market_instruments → canonical instruments
-- Adds canonical_inst_id column so market_klines data can be
-- promoted to canonical_candles using a configurable exchange
-- preference order (e.g. okx > binance > bybit).
-- Run via: python scripts/market_data/init_db.py
-- ============================================================

ALTER TABLE market_instruments
    ADD COLUMN IF NOT EXISTS canonical_inst_id TEXT REFERENCES instruments(inst_id);

CREATE INDEX IF NOT EXISTS idx_market_instruments_canonical
    ON market_instruments (canonical_inst_id, exchange, is_active);
