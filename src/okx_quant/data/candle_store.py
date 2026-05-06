"""
Async PostgreSQL/TimescaleDB client for OHLCV data.
Manages raw_candles (exchange-native) and canonical_candles (strategy-ready).
Uses asyncpg connection pool for all operations.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import asyncpg
import pandas as pd
from loguru import logger


# Milliseconds per bar used for gap detection interval lookups
_BAR_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1H": 3_600_000,
    "2H": 7_200_000,
    "4H": 14_400_000,
    "1D": 86_400_000,
}


def _ms_to_utc(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


def _utc_now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


class CandleStore:
    """
    Async wrapper around the TimescaleDB OHLCV hypertables.
    All public methods are coroutines; use from_dsn() to construct.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ──────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────

    @classmethod
    async def from_dsn(
        cls,
        dsn: str,
        min_size: int = 2,
        max_size: int = 10,
    ) -> "CandleStore":
        pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()

    async def __aenter__(self) -> "CandleStore":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ──────────────────────────────────────────────────────────────
    # Instrument registry
    # ──────────────────────────────────────────────────────────────

    async def register_instrument(
        self,
        inst_id: str,
        base_ccy: str,
        quote_ccy: str = "USDT",
        settle_ccy: str = "USDT",
        exchange: str = "okx",
        inst_type: str = "SWAP",
        contract_value: Optional[float] = None,
        tick_size: Optional[float] = None,
        lot_size: Optional[float] = None,
        min_size: Optional[float] = None,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO instruments
                (inst_id, exchange, inst_type, base_ccy, quote_ccy, settle_ccy,
                 contract_value, tick_size, lot_size, min_size)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (inst_id) DO NOTHING
            """,
            inst_id, exchange, inst_type, base_ccy, quote_ccy, settle_ccy,
            contract_value, tick_size, lot_size, min_size,
        )

    async def register_instrument_bar(self, inst_id: str, bar: str) -> None:
        await self._pool.execute(
            """
            INSERT INTO instrument_bars (inst_id, bar)
            VALUES ($1, $2)
            ON CONFLICT (inst_id, bar) DO NOTHING
            """,
            inst_id, bar,
        )

    async def set_instrument_active(self, inst_id: str, active: bool) -> None:
        if active:
            await self._pool.execute(
                "UPDATE instruments SET is_active=$1, archived_at=NULL WHERE inst_id=$2",
                True, inst_id,
            )
        else:
            await self._pool.execute(
                "UPDATE instruments SET is_active=FALSE, archived_at=NOW() WHERE inst_id=$1",
                inst_id,
            )

    async def set_instrument_bar_active(
        self, inst_id: str, bar: str, active: bool
    ) -> None:
        await self._pool.execute(
            "UPDATE instrument_bars SET is_active=$1 WHERE inst_id=$2 AND bar=$3",
            active, inst_id, bar,
        )

    async def get_active_instruments(self) -> list[dict]:
        rows = await self._pool.fetch(
            "SELECT inst_id, base_ccy, is_active FROM instruments WHERE is_active=TRUE ORDER BY inst_id"
        )
        return [dict(r) for r in rows]

    async def get_active_instrument_bars(self) -> list[dict]:
        rows = await self._pool.fetch(
            """
            SELECT ib.inst_id, ib.bar, ib.first_candle_ts, ib.last_candle_ts
            FROM instrument_bars ib
            JOIN instruments i ON i.inst_id = ib.inst_id
            WHERE ib.is_active = TRUE AND i.is_active = TRUE
            ORDER BY ib.inst_id, ib.bar
            """
        )
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────────────────────
    # Job tracking
    # ──────────────────────────────────────────────────────────────

    async def start_job(
        self,
        job_type: str,
        source: str,
        inst_id: Optional[str] = None,
        bar: Optional[str] = None,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        details: Optional[dict] = None,
    ) -> str:
        row = await self._pool.fetchrow(
            """
            INSERT INTO ingestion_jobs
                (job_type, source, inst_id, bar, start_ts, end_ts, details)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            RETURNING job_id::TEXT
            """,
            job_type, source, inst_id, bar, start_ts, end_ts,
            json.dumps(details) if details else None,
        )
        job_id = row["job_id"]
        logger.info("Job started", job_id=job_id, job_type=job_type,
                    inst_id=inst_id, bar=bar)
        return job_id

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
        error_message: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        await self._pool.execute(
            """
            UPDATE ingestion_jobs SET
                status=$2, rows_fetched=$3, rows_inserted=$4, rows_updated=$5,
                rows_skipped=$6, gaps_found=$7, outliers_found=$8,
                error_message=$9, details=$10, finished_at=NOW()
            WHERE job_id=$1::UUID
            """,
            job_id, status, rows_fetched, rows_inserted, rows_updated,
            rows_skipped, gaps_found, outliers_found, error_message,
            json.dumps(details) if details else None,
        )
        logger.info("Job finished", job_id=job_id, status=status,
                    rows_inserted=rows_inserted, gaps_found=gaps_found)

    # ------------------------------------------------------------------
    # Long-running ingestion checkpoints
    # ------------------------------------------------------------------

    async def ensure_ingestion_checkpoint_table(self) -> None:
        """Create the checkpoint table for resumable long-running ingestion."""
        await self._pool.execute(
            "ALTER TABLE funding_rates ADD COLUMN IF NOT EXISTS realized_rate DOUBLE PRECISION"
        )
        await self._pool.execute(
            "ALTER TABLE funding_rates ADD COLUMN IF NOT EXISTS mark_price DOUBLE PRECISION"
        )
        await self._pool.execute(
            "ALTER TABLE funding_rates ADD COLUMN IF NOT EXISTS funding_interval_hours DOUBLE PRECISION"
        )
        await self._pool.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_checkpoints (
                source          TEXT NOT NULL,
                dataset         TEXT NOT NULL,
                inst_id         TEXT NOT NULL,
                direction       TEXT NOT NULL DEFAULT 'forward',
                cursor_time_ms  BIGINT,
                cursor_time     TIMESTAMPTZ,
                request_count   BIGINT NOT NULL DEFAULT 0,
                row_count       BIGINT NOT NULL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'idle',
                last_error      TEXT,
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (source, dataset, inst_id, direction),
                CHECK (dataset IN ('klines_1m', 'funding_rate')),
                CHECK (direction IN ('forward', 'backward')),
                CHECK (status IN ('idle', 'running', 'success', 'failed', 'partial'))
            )
            """
        )

    async def get_checkpoint(
        self,
        source: str,
        dataset: str,
        inst_id: str,
        direction: str,
    ) -> Optional[dict]:
        await self.ensure_ingestion_checkpoint_table()
        row = await self._pool.fetchrow(
            """
            SELECT source, dataset, inst_id, direction, cursor_time_ms, cursor_time,
                   request_count, row_count, status, last_error, updated_at
            FROM ingestion_checkpoints
            WHERE source=$1 AND dataset=$2 AND inst_id=$3 AND direction=$4
            """,
            source, dataset, inst_id, direction,
        )
        return dict(row) if row else None

    async def update_checkpoint(
        self,
        source: str,
        dataset: str,
        inst_id: str,
        direction: str,
        cursor_time_ms: Optional[int],
        status: str,
        request_count_delta: int = 0,
        row_count_delta: int = 0,
        last_error: Optional[str] = None,
    ) -> None:
        await self.ensure_ingestion_checkpoint_table()
        cursor_time = _ms_to_utc(cursor_time_ms) if cursor_time_ms is not None else None
        await self._pool.execute(
            """
            INSERT INTO ingestion_checkpoints
                (source, dataset, inst_id, direction, cursor_time_ms, cursor_time,
                 request_count, row_count, status, last_error, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
            ON CONFLICT (source, dataset, inst_id, direction) DO UPDATE SET
                cursor_time_ms=EXCLUDED.cursor_time_ms,
                cursor_time=EXCLUDED.cursor_time,
                request_count=ingestion_checkpoints.request_count + EXCLUDED.request_count,
                row_count=ingestion_checkpoints.row_count + EXCLUDED.row_count,
                status=EXCLUDED.status,
                last_error=EXCLUDED.last_error,
                updated_at=NOW()
            """,
            source, dataset, inst_id, direction, cursor_time_ms, cursor_time,
            request_count_delta, row_count_delta, status, last_error,
        )

    # ------------------------------------------------------------------
    # Multi-exchange canonical market-data layer
    # ------------------------------------------------------------------

    async def ensure_market_data_schema(self) -> None:
        """Create the multi-exchange canonical market-data tables."""
        await self._pool.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await self._pool.execute(
            """
            CREATE TABLE IF NOT EXISTS market_instruments (
                instrument_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                exchange          TEXT NOT NULL
                    CHECK (exchange IN ('okx', 'binance', 'bybit', 'coinbase', 'kraken', 'other')),
                market_type       TEXT NOT NULL DEFAULT 'linear_perpetual',
                inst_id           TEXT NOT NULL,
                normalized_symbol TEXT NOT NULL,
                base_asset        TEXT NOT NULL,
                quote_asset       TEXT NOT NULL DEFAULT 'USDT',
                settlement_asset  TEXT NOT NULL DEFAULT 'USDT',
                contract_type     TEXT NOT NULL DEFAULT 'perpetual',
                listing_time      TIMESTAMPTZ,
                delisting_time    TIMESTAMPTZ,
                is_active         BOOLEAN NOT NULL DEFAULT TRUE,
                inserted_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (exchange, market_type, inst_id)
            )
            """
        )
        await self._pool.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_market_instruments_symbol
                ON market_instruments (normalized_symbol, exchange, is_active)
            """
        )
        await self._pool.execute(
            """
            CREATE TABLE IF NOT EXISTS market_klines (
                instrument_id UUID NOT NULL REFERENCES market_instruments(instrument_id),
                bar           TEXT NOT NULL REFERENCES bar_intervals(bar),
                ts            TIMESTAMPTZ NOT NULL,
                open          DOUBLE PRECISION NOT NULL,
                high          DOUBLE PRECISION NOT NULL,
                low           DOUBLE PRECISION NOT NULL,
                close         DOUBLE PRECISION NOT NULL,
                volume        DOUBLE PRECISION,
                quote_volume  DOUBLE PRECISION,
                data_source   TEXT NOT NULL,
                raw_payload   JSONB,
                inserted_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (instrument_id, bar, ts),
                CONSTRAINT ck_market_klines_ohlc CHECK (
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
            )
            """
        )
        await self._pool.execute(
            """
            SELECT create_hypertable(
                'market_klines', 'ts',
                chunk_time_interval => INTERVAL '1 month',
                if_not_exists => TRUE
            )
            """
        )
        await self._pool.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_market_klines_lookup
                ON market_klines (instrument_id, bar, ts DESC)
            """
        )
        await self._pool.execute(
            """
            CREATE TABLE IF NOT EXISTS market_funding_rates (
                instrument_id          UUID NOT NULL REFERENCES market_instruments(instrument_id),
                funding_time           TIMESTAMPTZ NOT NULL,
                funding_rate           DOUBLE PRECISION NOT NULL,
                funding_rate_raw       TEXT,
                realized_rate          DOUBLE PRECISION,
                mark_price             DOUBLE PRECISION,
                funding_interval_hours DOUBLE PRECISION,
                data_source            TEXT NOT NULL,
                raw_payload            JSONB,
                inserted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (instrument_id, funding_time)
            )
            """
        )
        await self._pool.execute(
            """
            SELECT create_hypertable(
                'market_funding_rates', 'funding_time',
                chunk_time_interval => INTERVAL '1 month',
                if_not_exists => TRUE
            )
            """
        )
        await self._pool.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_market_funding_rates_lookup
                ON market_funding_rates (instrument_id, funding_time DESC)
            """
        )

    async def register_market_instrument(
        self,
        *,
        exchange: str,
        inst_id: str,
        normalized_symbol: str,
        base_asset: str,
        quote_asset: str = "USDT",
        settlement_asset: str = "USDT",
        market_type: str = "linear_perpetual",
        contract_type: str = "perpetual",
        listing_time: Optional[datetime] = None,
        delisting_time: Optional[datetime] = None,
        is_active: bool = True,
    ) -> str:
        await self.ensure_market_data_schema()
        row = await self._pool.fetchrow(
            """
            INSERT INTO market_instruments
                (exchange, market_type, inst_id, normalized_symbol, base_asset,
                 quote_asset, settlement_asset, contract_type, listing_time,
                 delisting_time, is_active)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            ON CONFLICT (exchange, market_type, inst_id) DO UPDATE SET
                normalized_symbol=EXCLUDED.normalized_symbol,
                base_asset=EXCLUDED.base_asset,
                quote_asset=EXCLUDED.quote_asset,
                settlement_asset=EXCLUDED.settlement_asset,
                contract_type=EXCLUDED.contract_type,
                listing_time=COALESCE(
                    market_instruments.listing_time,
                    EXCLUDED.listing_time
                ),
                delisting_time=EXCLUDED.delisting_time,
                is_active=EXCLUDED.is_active,
                updated_at=NOW()
            RETURNING instrument_id::TEXT
            """,
            exchange, market_type, inst_id, normalized_symbol, base_asset,
            quote_asset, settlement_asset, contract_type, listing_time,
            delisting_time, is_active,
        )
        return str(row["instrument_id"])

    async def upsert_market_klines(
        self,
        rows: list[dict],
        *,
        instrument_id: str,
        bar: str,
        data_source: str,
    ) -> dict:
        if not rows:
            return {"inserted": 0}
        await self.ensure_market_data_schema()
        records = [
            (
                instrument_id,
                bar,
                _ms_to_utc(int(r["ts_ms"])),
                float(r["open"]),
                float(r["high"]),
                float(r["low"]),
                float(r["close"]),
                float(r["vol_base"]) if r.get("vol_base") is not None else (
                    float(r["vol_contract"]) if r.get("vol_contract") is not None else None
                ),
                float(r["vol_quote"]) if r.get("vol_quote") is not None else None,
                data_source,
                json.dumps(r["raw_payload"]) if r.get("raw_payload") else None,
            )
            for r in rows
        ]
        for i in range(0, len(records), 500):
            await self._pool.executemany(
                """
                INSERT INTO market_klines
                    (instrument_id, bar, ts, open, high, low, close,
                     volume, quote_volume, data_source, raw_payload)
                VALUES ($1::UUID,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (instrument_id, bar, ts) DO UPDATE SET
                    open=EXCLUDED.open,
                    high=EXCLUDED.high,
                    low=EXCLUDED.low,
                    close=EXCLUDED.close,
                    volume=EXCLUDED.volume,
                    quote_volume=EXCLUDED.quote_volume,
                    data_source=EXCLUDED.data_source,
                    raw_payload=EXCLUDED.raw_payload,
                    updated_at=NOW()
                """,
                records[i : i + 500],
            )
        return {"inserted": len(rows)}

    async def upsert_market_funding_rates(
        self,
        rows: list[dict],
        *,
        instrument_id: str,
        data_source: str,
    ) -> dict:
        if not rows:
            return {"inserted": 0}
        await self.ensure_market_data_schema()
        records = [
            (
                instrument_id,
                _ms_to_utc(int(r["ts_ms"])),
                float(r["funding_rate"]),
                str(r.get("funding_rate_raw") or r.get("funding_rate")),
                float(r["realized_rate"]) if r.get("realized_rate") is not None else None,
                float(r["mark_price"]) if r.get("mark_price") is not None else None,
                float(r["funding_interval_hours"])
                if r.get("funding_interval_hours") is not None else None,
                data_source,
                json.dumps(r["raw_payload"]) if r.get("raw_payload") else None,
            )
            for r in rows
        ]
        for i in range(0, len(records), 500):
            await self._pool.executemany(
                """
                INSERT INTO market_funding_rates
                    (instrument_id, funding_time, funding_rate, funding_rate_raw,
                     realized_rate, mark_price, funding_interval_hours,
                     data_source, raw_payload)
                VALUES ($1::UUID,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (instrument_id, funding_time) DO UPDATE SET
                    funding_rate=EXCLUDED.funding_rate,
                    funding_rate_raw=EXCLUDED.funding_rate_raw,
                    realized_rate=EXCLUDED.realized_rate,
                    mark_price=EXCLUDED.mark_price,
                    funding_interval_hours=COALESCE(
                        EXCLUDED.funding_interval_hours,
                        market_funding_rates.funding_interval_hours
                    ),
                    data_source=EXCLUDED.data_source,
                    raw_payload=EXCLUDED.raw_payload,
                    updated_at=NOW()
                """,
                records[i : i + 500],
            )
        return {"inserted": len(rows)}

    async def refresh_market_funding_intervals(self, instrument_id: str) -> None:
        await self.ensure_market_data_schema()
        await self._pool.execute(
            """
            WITH ordered AS (
                SELECT
                    instrument_id,
                    funding_time,
                    LEAD(funding_time) OVER (
                        PARTITION BY instrument_id
                        ORDER BY funding_time
                    ) AS next_time
                FROM market_funding_rates
                WHERE instrument_id=$1::UUID
            )
            UPDATE market_funding_rates f
            SET funding_interval_hours = EXTRACT(EPOCH FROM (ordered.next_time - ordered.funding_time)) / 3600.0
            FROM ordered
            WHERE f.instrument_id = ordered.instrument_id
              AND f.funding_time = ordered.funding_time
              AND ordered.next_time IS NOT NULL
            """,
            instrument_id,
        )

    # ──────────────────────────────────────────────────────────────
    # Raw candles
    # ──────────────────────────────────────────────────────────────

    async def upsert_raw_candles(
        self,
        rows: list[dict],
        source: str,
        inst_id: str,
        bar: str,
    ) -> dict:
        """
        Bulk-upsert rows into raw_candles.

        Each row must have: ts_ms (int), open, high, low, close.
        Optional: vol_contract, vol_base, vol_quote, is_closed, raw_payload.
        Returns {inserted, skipped}.
        """
        if not rows:
            return {"inserted": 0, "skipped": 0}

        records = []
        for r in rows:
            records.append((
                _ms_to_utc(r["ts_ms"]),
                source,
                inst_id,
                bar,
                float(r["open"]),
                float(r["high"]),
                float(r["low"]),
                float(r["close"]),
                float(r["vol_contract"]) if r.get("vol_contract") is not None else None,
                float(r["vol_base"])     if r.get("vol_base")     is not None else None,
                float(r["vol_quote"])    if r.get("vol_quote")    is not None else None,
                bool(r.get("is_closed", True)),
                json.dumps(r["raw_payload"]) if r.get("raw_payload") else None,
            ))

        inserted = 0
        chunk_size = 500
        for i in range(0, len(records), chunk_size):
            chunk = records[i : i + chunk_size]
            result = await self._pool.executemany(
                """
                INSERT INTO raw_candles
                    (ts, source, inst_id, bar, open, high, low, close,
                     vol_contract, vol_base, vol_quote, is_closed, raw_payload)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                ON CONFLICT (source, inst_id, bar, ts) DO UPDATE SET
                    open=EXCLUDED.open,
                    high=EXCLUDED.high,
                    low=EXCLUDED.low,
                    close=EXCLUDED.close,
                    vol_contract=EXCLUDED.vol_contract,
                    vol_base=EXCLUDED.vol_base,
                    vol_quote=EXCLUDED.vol_quote,
                    is_closed=EXCLUDED.is_closed,
                    raw_payload=EXCLUDED.raw_payload,
                    ingested_at=NOW()
                """,
                chunk,
            )
            inserted += len(chunk)

        return {"inserted": inserted, "skipped": len(rows) - inserted}

    async def get_raw_candles(
        self,
        source: str,
        inst_id: str,
        bar: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        conditions = ["source=$1", "inst_id=$2", "bar=$3"]
        params: list[Any] = [source, inst_id, bar]
        if start:
            params.append(start)
            conditions.append(f"ts >= ${len(params)}")
        if end:
            params.append(end)
            conditions.append(f"ts < ${len(params)}")
        where = " AND ".join(conditions)
        rows = await self._pool.fetch(
            f"SELECT ts, open, high, low, close, vol_contract, vol_base, vol_quote, is_closed "
            f"FROM raw_candles WHERE {where} ORDER BY ts",
            *params,
        )
        if not rows:
            return pd.DataFrame(columns=["open","high","low","close","vol_contract","vol_base","vol_quote"])
        df = pd.DataFrame([dict(r) for r in rows])
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df.set_index("ts").sort_index()

    # ──────────────────────────────────────────────────────────────
    # Canonical candles
    # ──────────────────────────────────────────────────────────────

    async def canonicalize_from_raw(
        self,
        source: str,
        inst_id: str,
        bar: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> dict:
        """
        Promote closed raw candles from `source` into canonical_candles.
        Uses INSERT ... ON CONFLICT DO NOTHING to avoid overwriting
        already-corrected canonical rows.
        """
        conditions = ["r.source=$1", "r.inst_id=$2", "r.bar=$3", "r.is_closed=TRUE"]
        params: list[Any] = [source, inst_id, bar]
        if start:
            params.append(start)
            conditions.append(f"r.ts >= ${len(params)}")
        if end:
            params.append(end)
            conditions.append(f"r.ts < ${len(params)}")
        where = " AND ".join(conditions)

        result = await self._pool.execute(
            f"""
            INSERT INTO canonical_candles
                (ts, inst_id, bar, open, high, low, close,
                 vol_contract, vol_base, vol_quote, source_primary, quality_status)
            SELECT
                r.ts, r.inst_id, r.bar, r.open, r.high, r.low, r.close,
                r.vol_contract, r.vol_base, r.vol_quote, $1, 'raw'
            FROM raw_candles r
            WHERE {where}
            ON CONFLICT (inst_id, bar, ts) DO NOTHING
            """,
            *params,
        )
        # asyncpg returns "INSERT 0 N" string
        try:
            promoted = int(result.split()[-1])
        except (ValueError, IndexError):
            promoted = 0
        return {"promoted": promoted}

    async def upsert_canonical_candles(
        self,
        rows: list[dict],
        inst_id: str,
        bar: str,
        source_primary: str = "okx",
        quality_status: str = "raw",
    ) -> dict:
        """Direct upsert into canonical_candles (used by validator for corrections)."""
        if not rows:
            return {"inserted": 0}
        await self.ensure_ingestion_checkpoint_table()

        records = [
            (
                _ms_to_utc(r["ts_ms"]),
                inst_id, bar,
                float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
                float(r["vol_contract"]) if r.get("vol_contract") is not None else None,
                float(r["vol_base"])     if r.get("vol_base")     is not None else None,
                float(r["vol_quote"])    if r.get("vol_quote")    is not None else None,
                source_primary, quality_status,
            )
            for r in rows
        ]
        chunk_size = 500
        for i in range(0, len(records), chunk_size):
            chunk = records[i : i + chunk_size]
            await self._pool.executemany(
                """
                INSERT INTO canonical_candles
                    (ts, inst_id, bar, open, high, low, close,
                     vol_contract, vol_base, vol_quote, source_primary, quality_status, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,NOW())
                ON CONFLICT (inst_id, bar, ts) DO UPDATE SET
                    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
                    vol_contract=EXCLUDED.vol_contract, vol_base=EXCLUDED.vol_base,
                    vol_quote=EXCLUDED.vol_quote, source_primary=EXCLUDED.source_primary,
                    quality_status=EXCLUDED.quality_status, updated_at=NOW(),
                    version=canonical_candles.version + 1
                """,
                chunk,
            )
        return {"inserted": len(rows)}

    async def get_canonical_candles(
        self,
        inst_id: str,
        bar: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        include_suspect: bool = False,
    ) -> pd.DataFrame:
        """
        Query canonical_candles. For 5m/15m/1H also checks continuous aggregate views.
        Returns tz-aware UTC DatetimeIndex, cols [open,high,low,close,vol_contract,vol_base,vol_quote].
        """
        view_map = {"5m": "canonical_candles_5m", "15m": "canonical_candles_15m", "1H": "canonical_candles_1h"}
        table = view_map.get(bar, "canonical_candles")

        conditions = ["inst_id=$1", "bar=$2"]
        params: list[Any] = [inst_id, bar]
        if start:
            params.append(start)
            conditions.append(f"ts >= ${len(params)}")
        if end:
            params.append(end)
            conditions.append(f"ts < ${len(params)}")
        if not include_suspect and table == "canonical_candles":
            conditions.append("quality_status != 'suspect'")
        where = " AND ".join(conditions)

        rows = await self._pool.fetch(
            f"SELECT ts, open, high, low, close, vol_contract, vol_base, vol_quote "
            f"FROM {table} WHERE {where} ORDER BY ts",
            *params,
        )
        if not rows and table != "canonical_candles":
            fallback_conditions = list(conditions)
            if not include_suspect:
                fallback_conditions.append("quality_status != 'suspect'")
            fallback_where = " AND ".join(fallback_conditions)
            rows = await self._pool.fetch(
                "SELECT ts, open, high, low, close, vol_contract, vol_base, vol_quote "
                f"FROM canonical_candles WHERE {fallback_where} ORDER BY ts",
                *params,
            )
        if not rows:
            return pd.DataFrame(
                columns=["open","high","low","close","vol_contract","vol_base","vol_quote"]
            )
        df = pd.DataFrame([dict(r) for r in rows])
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        return df.set_index("ts").sort_index()

    async def get_last_canonical_ts(self, inst_id: str, bar: str) -> Optional[int]:
        """Return epoch ms of most recent canonical candle, or None."""
        val = await self._pool.fetchval(
            "SELECT EXTRACT(EPOCH FROM MAX(ts)) * 1000 FROM canonical_candles "
            "WHERE inst_id=$1 AND bar=$2",
            inst_id, bar,
        )
        return int(val) if val is not None else None

    # ------------------------------------------------------------------
    # Funding rates
    # ------------------------------------------------------------------

    async def upsert_funding_rates(
        self,
        rows: list[dict],
        source: str,
        inst_id: str,
    ) -> dict:
        """
        Bulk-upsert funding rates into funding_rates.

        Each row must have ts_ms and funding_rate. Optional fields:
        next_funding_ts_ms, realized_rate, raw_payload.
        """
        if not rows:
            return {"inserted": 0}

        records = []
        for r in rows:
            raw_payload = r.get("raw_payload") or {}
            if r.get("realized_rate") is not None:
                raw_payload = {**raw_payload, "realized_rate": float(r["realized_rate"])}
            records.append((
                _ms_to_utc(int(r["ts_ms"])),
                source,
                inst_id,
                float(r["funding_rate"]),
                float(r["realized_rate"]) if r.get("realized_rate") is not None else None,
                float(r["mark_price"]) if r.get("mark_price") is not None else None,
                float(r["funding_interval_hours"])
                if r.get("funding_interval_hours") is not None else None,
                _ms_to_utc(int(r["next_funding_ts_ms"]))
                if r.get("next_funding_ts_ms") is not None else None,
                json.dumps(raw_payload) if raw_payload else None,
            ))

        chunk_size = 500
        for i in range(0, len(records), chunk_size):
            await self._pool.executemany(
                """
                INSERT INTO funding_rates
                    (ts, source, inst_id, funding_rate, realized_rate, mark_price,
                     funding_interval_hours, next_funding_ts, raw_payload)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (source, inst_id, ts) DO UPDATE SET
                    funding_rate=EXCLUDED.funding_rate,
                    realized_rate=EXCLUDED.realized_rate,
                    mark_price=EXCLUDED.mark_price,
                    funding_interval_hours=COALESCE(
                        EXCLUDED.funding_interval_hours,
                        funding_rates.funding_interval_hours
                    ),
                    next_funding_ts=EXCLUDED.next_funding_ts,
                    raw_payload=EXCLUDED.raw_payload,
                    ingested_at=NOW()
                """,
                records[i : i + chunk_size],
            )
        return {"inserted": len(rows)}

    async def refresh_funding_intervals(self, source: str, inst_id: str) -> None:
        """Infer funding_interval_hours from adjacent funding timestamps."""
        await self._pool.execute(
            """
            WITH ordered AS (
                SELECT
                    source,
                    inst_id,
                    ts,
                    LEAD(ts) OVER (
                        PARTITION BY source, inst_id
                        ORDER BY ts
                    ) AS next_ts
                FROM funding_rates
                WHERE source=$1 AND inst_id=$2
            )
            UPDATE funding_rates f
            SET funding_interval_hours = EXTRACT(EPOCH FROM (ordered.next_ts - ordered.ts)) / 3600.0
            FROM ordered
            WHERE f.source = ordered.source
              AND f.inst_id = ordered.inst_id
              AND f.ts = ordered.ts
              AND ordered.next_ts IS NOT NULL
            """,
            source, inst_id,
        )

    async def get_funding_rates(
        self,
        inst_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        source: str = "okx",
    ) -> pd.DataFrame:
        """
        Query funding_rates and return a DataFrame compatible with
        backtesting.data_loader.load_funding().
        """
        await self.ensure_ingestion_checkpoint_table()
        conditions = ["source=$1", "inst_id=$2"]
        params: list[Any] = [source, inst_id]
        if start:
            params.append(start)
            conditions.append(f"ts >= ${len(params)}")
        if end:
            params.append(end)
            conditions.append(f"ts < ${len(params)}")
        where = " AND ".join(conditions)
        gap_param = len(params) + 1

        rows = await self._pool.fetch(
            f"""
            SELECT
                ts,
                funding_rate AS rate,
                COALESCE(realized_rate, funding_rate) AS realized_rate,
                mark_price,
                funding_interval_hours,
                EXTRACT(EPOCH FROM next_funding_ts) * 1000 AS next_funding_time
            FROM funding_rates
            WHERE {where}
            ORDER BY ts
            """,
            *params,
        )
        if not rows:
            return pd.DataFrame(columns=["rate", "realized_rate", "nextFundingTime", "apr"])

        df = pd.DataFrame([dict(r) for r in rows])
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        df["nextFundingTime"] = df.pop("next_funding_time")
        df["apr"] = df["rate"].astype(float) * (365 * 24 / 8)
        return df.set_index("ts").sort_index()

    async def detect_funding_gaps(
        self,
        inst_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        source: str = "okx",
        expected_interval: timedelta = timedelta(hours=8),
        tolerance: timedelta = timedelta(seconds=1),
    ) -> list[dict]:
        """Return funding timestamp gaps larger than expected_interval + tolerance."""
        conditions = ["source=$1", "inst_id=$2"]
        params: list[Any] = [source, inst_id]
        if start:
            params.append(start)
            conditions.append(f"ts >= ${len(params)}")
        if end:
            params.append(end)
            conditions.append(f"ts < ${len(params)}")
        where = " AND ".join(conditions)
        gap_param = len(params) + 1

        rows = await self._pool.fetch(
            f"""
            WITH ordered AS (
                SELECT
                    ts,
                    LAG(ts) OVER (ORDER BY ts) AS prev_ts
                FROM funding_rates
                WHERE {where}
            )
            SELECT
                prev_ts AS gap_start,
                ts AS gap_end,
                ts - prev_ts AS gap
            FROM ordered
            WHERE prev_ts IS NOT NULL
              AND ts - prev_ts > ${gap_param}::interval
            ORDER BY ts
            """,
            *params,
            expected_interval + tolerance,
        )
        return [dict(r) for r in rows]

    async def summarize_funding_rates(
        self,
        inst_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        source: str = "okx",
    ) -> dict:
        """Return row count and timestamp bounds for funding_rates."""
        conditions = ["source=$1", "inst_id=$2"]
        params: list[Any] = [source, inst_id]
        if start:
            params.append(start)
            conditions.append(f"ts >= ${len(params)}")
        if end:
            params.append(end)
            conditions.append(f"ts < ${len(params)}")
        where = " AND ".join(conditions)
        row = await self._pool.fetchrow(
            f"""
            SELECT
                COUNT(*) AS rows,
                MIN(ts) AS first_ts,
                MAX(ts) AS last_ts,
                MAX(funding_rate * 365 * 24 / COALESCE(NULLIF(funding_interval_hours, 0), 8)) AS max_apr,
                SUM(CASE
                    WHEN funding_rate * 365 * 24 / COALESCE(NULLIF(funding_interval_hours, 0), 8) > 0.05
                    THEN 1 ELSE 0 END
                ) AS apr_gt_5pct,
                SUM(CASE
                    WHEN funding_rate * 365 * 24 / COALESCE(NULLIF(funding_interval_hours, 0), 8) > 0.12
                    THEN 1 ELSE 0 END
                ) AS apr_gt_12pct
            FROM funding_rates
            WHERE {where}
            """,
            *params,
        )
        return dict(row) if row else {}

    async def funding_interval_distribution(
        self,
        inst_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        source: str = "okx",
    ) -> list[dict]:
        """Return observed funding_interval_hours distribution."""
        conditions = ["source=$1", "inst_id=$2", "funding_interval_hours IS NOT NULL"]
        params: list[Any] = [source, inst_id]
        if start:
            params.append(start)
            conditions.append(f"ts >= ${len(params)}")
        if end:
            params.append(end)
            conditions.append(f"ts < ${len(params)}")
        where = " AND ".join(conditions)
        rows = await self._pool.fetch(
            f"""
            SELECT funding_interval_hours, COUNT(*) AS rows
            FROM funding_rates
            WHERE {where}
            GROUP BY funding_interval_hours
            ORDER BY funding_interval_hours
            """,
            *params,
        )
        return [dict(r) for r in rows]

    async def update_instrument_bar_bounds(self, inst_id: str, bar: str) -> None:
        """Refresh first_candle_ts and last_candle_ts in instrument_bars."""
        await self._pool.execute(
            """
            UPDATE instrument_bars SET
                first_candle_ts = (
                    SELECT MIN(ts) FROM canonical_candles
                    WHERE inst_id=$1 AND bar=$2
                ),
                last_candle_ts = (
                    SELECT MAX(ts) FROM canonical_candles
                    WHERE inst_id=$1 AND bar=$2
                ),
                last_checked_at = NOW()
            WHERE inst_id=$1 AND bar=$2
            """,
            inst_id, bar,
        )

    # ──────────────────────────────────────────────────────────────
    # Gap detection
    # ──────────────────────────────────────────────────────────────

    async def detect_gaps(
        self,
        inst_id: str,
        bar: str,
        start: datetime,
        end: datetime,
        table: str = "canonical_candles",
    ) -> list[tuple[datetime, datetime]]:
        """
        Return list of (gap_start, gap_end) tuples for missing candles
        in [start, end) using generate_series LEFT JOIN.
        """
        bar_interval = _BAR_MS.get(bar, 60_000)
        pg_interval = timedelta(milliseconds=bar_interval)

        rows = await self._pool.fetch(
            f"""
            SELECT gs.ts AS expected_ts
            FROM generate_series($1::timestamptz, $2::timestamptz - $3::interval, $3::interval) AS gs(ts)
            LEFT JOIN {table} c ON c.ts = gs.ts AND c.inst_id = $4 AND c.bar = $5
            WHERE c.ts IS NULL
            ORDER BY 1
            """,
            start, end, pg_interval, inst_id, bar,
        )
        if not rows:
            return []

        # Group consecutive missing timestamps into (gap_start, gap_end) ranges
        gap_timestamps = [r["expected_ts"] for r in rows]
        gaps: list[tuple[datetime, datetime]] = []
        gap_start = gap_timestamps[0]
        prev = gap_timestamps[0]

        bar_ms = _BAR_MS.get(bar, 60_000)
        bar_td = timedelta(milliseconds=bar_ms)

        for ts in gap_timestamps[1:]:
            if ts - prev > bar_td:
                gaps.append((gap_start, prev + bar_td))
                gap_start = ts
            prev = ts
        gaps.append((gap_start, prev + bar_td))
        return gaps

    # ──────────────────────────────────────────────────────────────
    # Quality events
    # ──────────────────────────────────────────────────────────────

    async def log_quality_event(
        self,
        inst_id: str,
        bar: str,
        issue_type: str,
        severity: str = "warning",
        status: str = "open",
        source: Optional[str] = None,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
        affected_count: Optional[int] = None,
        field: Optional[str] = None,
        observed_value: Optional[float] = None,
        reference_value: Optional[float] = None,
        z_score: Optional[float] = None,
        action_taken: Optional[str] = None,
        retry_count: int = 0,
        job_id: Optional[str] = None,
        details: Optional[dict] = None,
        notes: Optional[str] = None,
    ) -> None:
        await self._pool.execute(
            """
            INSERT INTO data_quality_events
                (inst_id, bar, issue_type, severity, status, source,
                 window_start, window_end, affected_count,
                 field, observed_value, reference_value, z_score,
                 action_taken, retry_count, job_id, details, notes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::UUID,$17,$18)
            """,
            inst_id, bar, issue_type, severity, status, source,
            window_start, window_end, affected_count,
            field, observed_value, reference_value, z_score,
            action_taken, retry_count, job_id,
            json.dumps(details) if details else None, notes,
        )

    async def resolve_quality_events(
        self,
        inst_id: str,
        bar: str,
        window_start: datetime,
        window_end: datetime,
        issue_type: str = "gap",
    ) -> int:
        result = await self._pool.execute(
            """
            UPDATE data_quality_events SET status='resolved', resolved_at=NOW()
            WHERE inst_id=$1 AND bar=$2 AND issue_type=$3
              AND window_start >= $4 AND window_end <= $5
              AND status='open'
            """,
            inst_id, bar, issue_type, window_start, window_end,
        )
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    async def get_quality_summary(self, inst_id: str) -> list[dict]:
        rows = await self._pool.fetch(
            """
            SELECT bar, issue_type, severity, status, COUNT(*) as count
            FROM data_quality_events
            WHERE inst_id=$1
            GROUP BY bar, issue_type, severity, status
            ORDER BY bar, issue_type
            """,
            inst_id,
        )
        return [dict(r) for r in rows]

    async def get_last_job(self, inst_id: str, job_type: str) -> Optional[dict]:
        row = await self._pool.fetchrow(
            """
            SELECT job_id::TEXT, status, started_at, finished_at,
                   rows_inserted, gaps_found, outliers_found, error_message
            FROM ingestion_jobs
            WHERE inst_id=$1 AND job_type=$2
            ORDER BY started_at DESC LIMIT 1
            """,
            inst_id, job_type,
        )
        return dict(row) if row else None
