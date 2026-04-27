"""
Tick data persistence. Default backend: Parquet (zero infrastructure).
TimescaleDB backend available via config: storage.backend = timescaledb.

Parquet layout: {parquet_dir}/{instrument}/{date}/books.parquet
                {parquet_dir}/{instrument}/{date}/trades.parquet
                {parquet_dir}/{instrument}/{date}/funding.parquet
"""
from __future__ import annotations

import asyncio
import datetime
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger


class FeedStore:
    def __init__(
        self,
        backend: str = "parquet",
        parquet_dir: str = "./data/ticks",
        timescale_dsn: Optional[str] = None,
        flush_interval_secs: int = 60,
    ) -> None:
        self._backend = backend
        self._parquet_dir = Path(parquet_dir)
        self._timescale_dsn = timescale_dsn
        self._flush_interval = flush_interval_secs

        # In-memory buffers keyed by (inst_id, table)
        self._buffers: dict[tuple, list] = defaultdict(list)
        self._lock = asyncio.Lock()

        if backend == "parquet":
            self._parquet_dir.mkdir(parents=True, exist_ok=True)
        elif backend == "timescaledb":
            if not timescale_dsn:
                raise ValueError("timescale_dsn required for timescaledb backend")

    # ------------------------------------------------------------------
    # Write methods (async-safe, buffer + periodic flush)
    # ------------------------------------------------------------------

    async def write_book_snapshot(
        self,
        inst_id: str,
        ts: int,
        bids: list,
        asks: list,
    ) -> None:
        row = {
            "ts": ts,
            "bid_px_0": float(bids[0][0]) if bids else None,
            "bid_sz_0": float(bids[0][1]) if bids else None,
            "ask_px_0": float(asks[0][0]) if asks else None,
            "ask_sz_0": float(asks[0][1]) if asks else None,
        }
        async with self._lock:
            self._buffers[(inst_id, "books")].append(row)

    async def write_trade(
        self,
        inst_id: str,
        ts: int,
        trade_id: str,
        price: float,
        size: float,
        side: str,
    ) -> None:
        row = {"ts": ts, "trade_id": trade_id, "price": price, "size": size, "side": side}
        async with self._lock:
            self._buffers[(inst_id, "trades")].append(row)

    async def write_funding(
        self,
        inst_id: str,
        ts: int,
        rate: float,
        next_funding_time: int,
    ) -> None:
        row = {"ts": ts, "rate": rate, "next_funding_time": next_funding_time}
        async with self._lock:
            self._buffers[(inst_id, "funding")].append(row)

    # ------------------------------------------------------------------
    # Flush task — run periodically
    # ------------------------------------------------------------------

    async def flush_loop(self) -> None:
        """Periodic flush task; run as asyncio background task."""
        while True:
            await asyncio.sleep(self._flush_interval)
            await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            buffers_snapshot = dict(self._buffers)
            self._buffers.clear()

        for (inst_id, table), rows in buffers_snapshot.items():
            if not rows:
                continue
            try:
                if self._backend == "parquet":
                    await asyncio.to_thread(self._flush_parquet, inst_id, table, rows)
                else:
                    await self._flush_timescale(inst_id, table, rows)
            except Exception as e:
                logger.error("FeedStore flush error", inst_id=inst_id, table=table, exc=str(e))

    def _flush_parquet(self, inst_id: str, table: str, rows: list) -> None:
        date_str = datetime.date.today().isoformat()
        out_dir = self._parquet_dir / inst_id.replace("-", "_") / date_str
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{table}.parquet"

        df = pd.DataFrame(rows)
        new_table = pa.Table.from_pandas(df)

        if out_path.exists():
            existing = pq.read_table(out_path)
            combined = pa.concat_tables([existing, new_table])
        else:
            combined = new_table

        pq.write_table(combined, out_path, compression="snappy")
        logger.debug("Parquet flushed", inst_id=inst_id, table=table, rows=len(rows))

    async def _flush_timescale(self, inst_id: str, table: str, rows: list) -> None:
        try:
            import asyncpg
        except ImportError:
            raise ImportError("asyncpg required for timescaledb backend: pip install asyncpg")

        conn = await asyncpg.connect(self._timescale_dsn)
        try:
            df = pd.DataFrame(rows)
            records = [tuple(r) for r in df.itertuples(index=False)]
            cols = ", ".join(df.columns)
            placeholders = ", ".join(f"${i+1}" for i in range(len(df.columns)))
            tbl = f"{inst_id.lower().replace('-', '_')}_{table}"
            await conn.executemany(
                f"INSERT INTO {tbl} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                records,
            )
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Read helpers (for backtesting data loading)
    # ------------------------------------------------------------------

    def read_trades(self, inst_id: str, date: str) -> pd.DataFrame:
        path = self._parquet_dir / inst_id.replace("-", "_") / date / "trades.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pq.read_table(path).to_pandas()

    def read_books(self, inst_id: str, date: str) -> pd.DataFrame:
        path = self._parquet_dir / inst_id.replace("-", "_") / date / "books.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pq.read_table(path).to_pandas()

    def read_funding(self, inst_id: str, date: str) -> pd.DataFrame:
        path = self._parquet_dir / inst_id.replace("-", "_") / date / "funding.parquet"
        if not path.exists():
            return pd.DataFrame()
        return pq.read_table(path).to_pandas()
