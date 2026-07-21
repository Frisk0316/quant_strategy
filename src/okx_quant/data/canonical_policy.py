"""Canonical candle source-priority policy shared by DB writers and stores."""
from __future__ import annotations

SOURCE_PRIORITY = {
    "manual": 100,
    "binance": 90,
    "okx": 80,
    "bybit": 70,
    "coinbase": 60,
    "kraken": 60,
    "other": 0,
}


def source_priority(source: str | None) -> int:
    return SOURCE_PRIORITY.get(str(source or "other").lower(), 0)


def should_replace_canonical(
    existing_source: str | None,
    existing_quality: str | None,
    incoming_source: str,
    incoming_quality: str = "raw",
) -> bool:
    """Return whether an incoming canonical candle may replace an existing one."""
    incoming = str(incoming_source or "other").lower()
    existing = str(existing_source or "other").lower()
    incoming_status = str(incoming_quality or "raw").lower()
    existing_status = str(existing_quality or "raw").lower()
    if incoming == "manual" or incoming_status != "raw":
        return True
    if existing_status == "suspect":
        return True
    if existing_status != "raw":
        return False
    incoming_priority = source_priority(incoming)
    existing_priority = source_priority(existing)
    return incoming_priority > existing_priority or incoming == existing


def source_priority_case(source_sql: str) -> str:
    """SQL CASE expression matching SOURCE_PRIORITY."""
    return f"""CASE {source_sql}
        WHEN 'manual' THEN 100
        WHEN 'binance' THEN 90
        WHEN 'okx' THEN 80
        WHEN 'bybit' THEN 70
        WHEN 'coinbase' THEN 60
        WHEN 'kraken' THEN 60
        ELSE 0
    END"""


def canonical_conflict_where(existing_table: str = "canonical_candles") -> str:
    """Shared ON CONFLICT DO UPDATE WHERE policy for canonical_candles."""
    incoming_priority = source_priority_case("EXCLUDED.source_primary")
    existing_priority = source_priority_case(f"{existing_table}.source_primary")
    return f"""
        EXCLUDED.source_primary = 'manual'
        OR EXCLUDED.quality_status != 'raw'
        OR {existing_table}.quality_status = 'suspect'
        OR (
            {existing_table}.quality_status = 'raw'
            AND (
                {incoming_priority}
                >
                {existing_priority}
                OR EXCLUDED.source_primary = {existing_table}.source_primary
            )
        )
    """


def venue_canonical_conflict_where() -> str:
    """Refresh raw/suspect venue rows only when their candle values changed."""
    return """
        venue_canonical_candles.quality_status IN ('raw', 'suspect')
        AND ROW(
            venue_canonical_candles.open,
            venue_canonical_candles.high,
            venue_canonical_candles.low,
            venue_canonical_candles.close,
            venue_canonical_candles.vol_contract,
            venue_canonical_candles.vol_base,
            venue_canonical_candles.vol_quote,
            venue_canonical_candles.quality_status
        ) IS DISTINCT FROM ROW(
            EXCLUDED.open,
            EXCLUDED.high,
            EXCLUDED.low,
            EXCLUDED.close,
            EXCLUDED.vol_contract,
            EXCLUDED.vol_base,
            EXCLUDED.vol_quote,
            EXCLUDED.quality_status
        )
    """
