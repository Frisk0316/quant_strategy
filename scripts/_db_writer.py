"""Shared helper: upsert downloaded OHLCV candles into TimescaleDB.

Used by `download_okx_data.py` and `download_binance_data.py` so a single download
command writes both the local parquet (offline cache) and the canonical DB layer
that powers backtests and the Market Data Coverage panel.

Design choices:
- Writes both `raw_candles` (for provenance / multi-exchange tracking) and
  `canonical_candles` (the backtest-ready strategy layer).
- Keeps every source in `raw_candles`, but applies source priority in
  `canonical_candles`: manual > binance > okx > bybit > coinbase/kraken > other.
  Lower-priority downloads fill gaps but do not replace higher-priority rows.
- Skips DB writes silently when no DSN is provided so existing parquet-only
  workflows keep working.
- Auto-creates the `instruments` and `instrument_bars` rows the canonical FK
  needs; uses sane defaults that can be edited later by the instrument registry.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from typing import Any, Iterable, Optional

import pandas as pd

try:
    from okx_quant.data.canonical_policy import (
        canonical_conflict_where,
        should_replace_canonical as _should_replace_canonical,
        source_priority as _source_priority,
        venue_canonical_conflict_where,
    )
except ModuleNotFoundError:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    src_root = os.path.join(repo_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)
    from okx_quant.data.canonical_policy import (
        canonical_conflict_where,
        should_replace_canonical as _should_replace_canonical,
        source_priority as _source_priority,
        venue_canonical_conflict_where,
    )

_VALID_SOURCES = {"okx", "binance", "bybit", "coinbase", "kraken", "manual", "other"}
# Only sources that the `instruments.exchange` CHECK constraint accepts.
_VALID_EXCHANGES = {"okx", "binance", "bybit", "coinbase", "kraken", "other"}


def resolve_dsn(explicit: Optional[str] = None) -> Optional[str]:
    """Return the first usable DSN among the CLI flag, DATABASE_URL, or config."""
    if explicit:
        return explicit
    env = os.environ.get("DATABASE_URL")
    if env:
        return env
    try:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        if repo_root not in sys.path:
            sys.path.insert(0, os.path.join(repo_root, "src"))
        from okx_quant.core.config import load_config  # type: ignore
        cfg = load_config(require_secrets=False)
        dsn = getattr(getattr(cfg, "storage", None), "timescale_dsn", None)
        return dsn or None
    except Exception:
        return None


def _split_instrument(inst_id: str) -> tuple[str, str, str, str]:
    """Return (base_ccy, quote_ccy, settle_ccy, inst_type) inferred from inst_id."""
    parts = inst_id.upper().split("-")
    base = parts[0] if parts else inst_id
    quote = parts[1] if len(parts) > 1 else "USDT"
    inst_type = "SPOT"
    if len(parts) >= 3:
        tail = parts[-1]
        if tail in {"SWAP", "PERP"}:
            inst_type = "SWAP"
        elif tail == "FUTURES":
            inst_type = "FUTURES"
        elif tail == "OPTION":
            inst_type = "OPTION"
    return base, quote, quote, inst_type


def _to_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    out: list[dict] = []
    for _, row in df.iterrows():
        ts = row.get("ts")
        if isinstance(ts, pd.Timestamp):
            ts_value = ts.to_pydatetime()
        else:
            ts_value = pd.to_datetime(ts, utc=True, errors="coerce")
            ts_value = ts_value.to_pydatetime() if pd.notna(ts_value) else None
        if ts_value is None:
            continue
        # Make sure ts is tz-aware (asyncpg requires tz for TIMESTAMPTZ).
        if ts_value.tzinfo is None:
            from datetime import timezone
            ts_value = ts_value.replace(tzinfo=timezone.utc)

        def _f(v: Any) -> Optional[float]:
            try:
                f = float(v)
            except (TypeError, ValueError):
                return None
            return None if math.isnan(f) or math.isinf(f) else f

        rec = {
            "ts": ts_value,
            "open": _f(row.get("open")),
            "high": _f(row.get("high")),
            "low": _f(row.get("low")),
            "close": _f(row.get("close")),
            "vol_contract": _f(row.get("vol")) if "vol" in row else None,
            "vol_base": _f(row.get("vol_base")) if "vol_base" in row else None,
            "vol_quote": _f(row.get("vol_ccy", row.get("vol_quote"))),
        }
        # OHLC must be positive and consistent (matches DB check constraint).
        if any(v is None or v <= 0 for v in (rec["open"], rec["high"], rec["low"], rec["close"])):
            continue
        if rec["high"] < max(rec["open"], rec["close"], rec["low"]):
            continue
        if rec["low"] > min(rec["open"], rec["close"], rec["high"]):
            continue
        out.append(rec)
    return out


async def _ensure_instrument(conn: Any, inst_id: str, bar: str, source: str) -> None:
    base, quote, settle, inst_type = _split_instrument(inst_id)
    exchange = source if source in _VALID_EXCHANGES else "other"
    await conn.execute(
        """
        INSERT INTO instruments (inst_id, exchange, inst_type, base_ccy, quote_ccy, settle_ccy)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (inst_id) DO NOTHING
        """,
        inst_id, exchange, inst_type, base, quote, settle,
    )
    # instrument_bars requires that the bar exists in bar_intervals (FK).  Skip
    # silently when the bar isn't pre-registered so we don't fail the download.
    bar_known = await conn.fetchval(
        "SELECT 1 FROM bar_intervals WHERE bar = $1", bar,
    )
    if bar_known:
        await conn.execute(
            """
            INSERT INTO instrument_bars (inst_id, bar)
            VALUES ($1, $2)
            ON CONFLICT (inst_id, bar) DO NOTHING
            """,
            inst_id, bar,
        )


async def _upsert_async(
    dsn: str,
    inst_id: str,
    bar: str,
    source: str,
    records: list[dict],
) -> tuple[int, int]:
    import asyncpg

    conn = await asyncpg.connect(dsn)
    raw_written = canonical_written = 0
    try:
        await _ensure_instrument(conn, inst_id, bar, source)

        raw_rows = [
            (
                rec["ts"], source, inst_id, bar,
                rec["open"], rec["high"], rec["low"], rec["close"],
                rec["vol_contract"], rec["vol_base"], rec["vol_quote"],
                True, json.dumps({"source": source}),
            )
            for rec in records
        ]
        if raw_rows:
            chunk_size = 1000
            for i in range(0, len(raw_rows), chunk_size):
                chunk = raw_rows[i : i + chunk_size]
                await conn.executemany(
                    """
                INSERT INTO raw_candles
                    (ts, source, inst_id, bar, open, high, low, close,
                     vol_contract, vol_base, vol_quote, is_closed, raw_payload)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb)
                ON CONFLICT (source, inst_id, bar, ts) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    vol_contract = EXCLUDED.vol_contract,
                    vol_base = EXCLUDED.vol_base,
                    vol_quote = EXCLUDED.vol_quote,
                    ingested_at = NOW()
                """,
                    chunk,
                )
            raw_written = len(raw_rows)

        canonical_rows = [
            (
                rec["ts"], inst_id, bar,
                rec["open"], rec["high"], rec["low"], rec["close"],
                rec["vol_contract"], rec["vol_base"], rec["vol_quote"],
                source, "raw",
            )
            for rec in records
        ]
        if canonical_rows:
            chunk_size = 1000
            for i in range(0, len(canonical_rows), chunk_size):
                chunk = canonical_rows[i : i + chunk_size]
                cols = [list(col) for col in zip(*chunk)]
                await conn.fetch(
                    f"""
                INSERT INTO venue_canonical_candles
                    (ts, inst_id, bar, open, high, low, close,
                     vol_contract, vol_base, vol_quote, source_primary, quality_status)
                SELECT *
                FROM unnest(
                    $1::timestamptz[],
                    $2::text[],
                    $3::text[],
                    $4::double precision[],
                    $5::double precision[],
                    $6::double precision[],
                    $7::double precision[],
                    $8::double precision[],
                    $9::double precision[],
                    $10::double precision[],
                    $11::text[],
                    $12::text[]
                )
                ON CONFLICT (source_primary, inst_id, bar, ts) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    vol_contract = EXCLUDED.vol_contract,
                    vol_base = EXCLUDED.vol_base,
                    vol_quote = EXCLUDED.vol_quote,
                    quality_status = EXCLUDED.quality_status,
                    updated_at = NOW(),
                    version = venue_canonical_candles.version + 1
                WHERE {venue_canonical_conflict_where()}
                RETURNING 1
                """,
                    *cols,
                )
                changed = await conn.fetch(
                    f"""
                INSERT INTO canonical_candles
                    (ts, inst_id, bar, open, high, low, close,
                     vol_contract, vol_base, vol_quote, source_primary, quality_status)
                SELECT *
                FROM unnest(
                    $1::timestamptz[],
                    $2::text[],
                    $3::text[],
                    $4::double precision[],
                    $5::double precision[],
                    $6::double precision[],
                    $7::double precision[],
                    $8::double precision[],
                    $9::double precision[],
                    $10::double precision[],
                    $11::text[],
                    $12::text[]
                )
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
                    updated_at = NOW()
                WHERE
                    {canonical_conflict_where()}
                RETURNING 1
                """,
                    *cols,
                )
                canonical_written += len(changed)
    finally:
        await conn.close()
    return raw_written, canonical_written


def upsert_candles_to_db(
    df: pd.DataFrame,
    inst_id: str,
    bar: str,
    source: str,
    dsn: Optional[str] = None,
) -> dict:
    """Synchronous entry point used by download scripts.

    Returns a status dict with `written` row counts and `skipped` reason when
    DB writes were not performed. Never raises on connection errors — callers
    log the result and continue, so a missing DB does not block downloads.
    """
    resolved_dsn = resolve_dsn(dsn)
    if not resolved_dsn:
        return {"status": "skipped", "reason": "no DSN available", "written": 0}
    if source not in _VALID_SOURCES:
        return {"status": "skipped", "reason": f"invalid source '{source}'", "written": 0}

    records = _to_records(df)
    if not records:
        return {"status": "skipped", "reason": "no valid OHLC rows", "written": 0}

    try:
        raw_n, canonical_n = asyncio.run(
            _upsert_async(resolved_dsn, inst_id, bar, source, records)
        )
    except Exception as exc:
        return {"status": "error", "reason": str(exc), "written": 0}
    return {
        "status": "ok",
        "written": canonical_n,
        "raw_written": raw_n,
        "canonical_written": canonical_n,
    }


__all__ = ["upsert_candles_to_db", "resolve_dsn"]
