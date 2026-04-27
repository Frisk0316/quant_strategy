"""
OKX WebSocket Order Book Streamer — tick-level data collector.

串接 OKX 公開 WebSocket，訂閱 BTC-USDT-SWAP / ETH-USDT-SWAP 的
books (L2 400-level) 及 trades 頻道，記錄每次 book update 的微結構特徵，
flush 至 Parquet 供 AS Market Maker 回測使用。

每個 tick snapshot 包含：
  ts_ns       — 本地接收時間 (nanoseconds, int64)
  server_ts   — OKX server timestamp (ms)
  mid         — (best_bid + best_ask) / 2
  wmid        — 加權中間價 (Stoikov weighted mid)
  micro       — Stoikov microprice
  spread      — best_ask - best_bid (absolute)
  spread_bps  — spread / mid * 10000
  obi_l1      — L1 Order Book Imbalance ∈ [-1, 1]
  obi_multi   — Multi-level OBI (depth=5, alpha=0.5)
  ofi         — Order Flow Imbalance increment (Cont-Kukanov-Stoikov)
  best_bid    — best bid price
  best_ask    — best ask price
  bid_sz      — best bid size (contracts)
  ask_sz      — best ask size (contracts)

Usage:
    python scripts/stream_orderbook.py                      # 60 min default
    python scripts/stream_orderbook.py --duration 30        # 30 min
    python scripts/stream_orderbook.py --duration 0         # run forever (Ctrl-C to stop)
    python scripts/stream_orderbook.py --symbols BTC-USDT-SWAP ETH-USDT-SWAP

Output:
    data/ticks/{inst_id}/ob_ticks_{YYYYMMDD_HHMMSS}.parquet
"""
from __future__ import annotations

import argparse
import asyncio
import json
import signal
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import websockets
from loguru import logger

from okx_quant.data.okx_book import OkxBook
from okx_quant.signals.obi_ofi import compute_obi_features, compute_ofi, book_to_l1_snap

# ── Constants ─────────────────────────────────────────────────────────────────
WS_PUBLIC_URL = "wss://ws.okx.com:8443/ws/v5/public"
FLUSH_EVERY   = 500       # flush buffer to Parquet every N ticks per symbol
OB_DEPTH      = 10        # depth for OBI signal (5 levels with decay)
HEARTBEAT_S   = 25        # OKX drops connection after 30s silence

DATA_DIR = PROJECT_ROOT / "data" / "ticks"

# ── Parquet schema (fixed, ensures consistent files for concatenation) ─────────
SCHEMA = pa.schema([
    ("ts_ns",      pa.int64()),
    ("server_ts",  pa.int64()),
    ("mid",        pa.float64()),
    ("wmid",       pa.float64()),
    ("micro",      pa.float64()),
    ("spread",     pa.float64()),
    ("spread_bps", pa.float64()),
    ("obi_l1",     pa.float64()),
    ("obi_multi",  pa.float64()),
    ("ofi",        pa.float64()),
    ("best_bid",   pa.float64()),
    ("best_ask",   pa.float64()),
    ("bid_sz",     pa.float64()),
    ("ask_sz",     pa.float64()),
])


class TickBuffer:
    """Accumulate tick dicts and flush to Parquet."""

    def __init__(self, inst_id: str, session_tag: str) -> None:
        self.inst_id     = inst_id
        self.session_tag = session_tag
        self._rows: list[dict] = []
        self._file_idx   = 0
        self._total      = 0

        out_dir = DATA_DIR / inst_id.replace("-", "_")
        out_dir.mkdir(parents=True, exist_ok=True)
        self._out_dir = out_dir

    def append(self, row: dict) -> None:
        self._rows.append(row)
        self._total += 1

    def flush(self, force: bool = False) -> None:
        if not self._rows:
            return
        if not force and len(self._rows) < FLUSH_EVERY:
            return

        df = pd.DataFrame(self._rows)
        table = pa.Table.from_pandas(df, schema=SCHEMA, preserve_index=False)

        path = self._out_dir / f"ob_ticks_{self.session_tag}_{self._file_idx:04d}.parquet"
        pq.write_table(table, path, compression="snappy")
        logger.info(f"[{self.inst_id}] flushed {len(self._rows):,} ticks → {path.name}")
        self._rows = []
        self._file_idx += 1

    @property
    def total(self) -> int:
        return self._total


class BookState:
    """Wraps OkxBook and tracks previous snapshot for OFI."""

    def __init__(self, inst_id: str) -> None:
        self.book      = OkxBook(inst_id)
        self._prev_l1  = None   # dict: pb, qb, pa, qa

    def update(self, msg: dict) -> dict | None:
        """
        Apply WebSocket message to book; return tick dict or None if book not ready.
        """
        try:
            self.book.handle(msg)
        except RuntimeError as e:
            logger.warning(f"Book error ({self.book.inst}): {e} — will resubscribe")
            raise

        if not self.book.is_valid():
            return None

        server_ts = int(msg["data"][0].get("ts", 0))
        bids, asks = self.book.levels(OB_DEPTH)
        if not bids or not asks:
            return None

        feats = compute_obi_features(bids, asks, depth=OB_DEPTH)
        mid   = feats["mid"]
        if mid <= 0:
            return None

        # L1 snap for OFI
        bids_arr, asks_arr = self.book.to_array(depth=1)
        curr_l1 = book_to_l1_snap(bids_arr, asks_arr)
        ofi = compute_ofi(self._prev_l1, curr_l1) if self._prev_l1 else 0.0
        self._prev_l1 = curr_l1

        best_bid, bid_sz = self.book.best_bid()
        best_ask, ask_sz = self.book.best_ask()

        return {
            "ts_ns":      time.time_ns(),
            "server_ts":  server_ts,
            "mid":        mid,
            "wmid":       feats["wmid"],
            "micro":      feats["micro"],
            "spread":     feats["spread"],
            "spread_bps": feats["spread"] / mid * 10_000 if mid > 0 else 0.0,
            "obi_l1":     feats["obi_l1"],
            "obi_multi":  feats["obi_multi"],
            "ofi":        ofi,
            "best_bid":   best_bid,
            "best_ask":   best_ask,
            "bid_sz":     bid_sz,
            "ask_sz":     ask_sz,
        }


async def _heartbeat(ws) -> None:
    """Send ping every 25 s to keep connection alive."""
    while True:
        await asyncio.sleep(HEARTBEAT_S)
        try:
            await ws.send("ping")
        except Exception:
            return


async def stream(
    symbols: list[str],
    duration_min: float,
    stop_event: asyncio.Event,
) -> None:
    """
    Main streaming coroutine. Subscribes to books + trades,
    accumulates ticks, flushes to Parquet.
    """
    session_tag = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    states  = {s: BookState(s)    for s in symbols}
    buffers = {s: TickBuffer(s, session_tag) for s in symbols}
    deadline = time.monotonic() + duration_min * 60 if duration_min > 0 else float("inf")

    logger.info(f"Connecting to {WS_PUBLIC_URL}")
    logger.info(f"Symbols: {symbols}")
    logger.info(f"Duration: {'∞' if duration_min == 0 else f'{duration_min:.0f} min'}")
    logger.info(f"Session tag: {session_tag}")

    reconnect_delay = 1.0

    while not stop_event.is_set():
        if time.monotonic() >= deadline:
            logger.info("Duration reached — stopping.")
            break

        try:
            async with websockets.connect(
                WS_PUBLIC_URL,
                ping_interval=None,   # we send manual pings
                max_size=2 ** 23,     # 8 MB (400-level books can be large)
                open_timeout=15,
            ) as ws:
                reconnect_delay = 1.0   # reset on successful connect

                # Subscribe: books (400-level) + trades
                book_args  = [{"channel": "books", "instId": s} for s in symbols]
                trade_args = [{"channel": "trades", "instId": s} for s in symbols]
                await ws.send(json.dumps({"op": "subscribe", "args": book_args}))
                await ws.send(json.dumps({"op": "subscribe", "args": trade_args}))
                logger.info("Subscribed to books + trades")

                hb_task = asyncio.create_task(_heartbeat(ws))

                tick_counts = {s: 0 for s in symbols}
                last_log = time.monotonic()

                try:
                    async for raw in ws:
                        if stop_event.is_set() or time.monotonic() >= deadline:
                            break
                        if raw == "pong":
                            continue

                        msg = json.loads(raw)

                        # Skip event/subscribe acks
                        if "event" in msg:
                            ev = msg.get("event", "")
                            if ev == "error":
                                logger.warning(f"WS error event: {msg}")
                            continue

                        channel = msg.get("arg", {}).get("channel", "")
                        inst_id = msg.get("arg", {}).get("instId", "")

                        if channel != "books" or inst_id not in states:
                            continue

                        tick = states[inst_id].update(msg)
                        if tick is None:
                            continue

                        buffers[inst_id].append(tick)
                        tick_counts[inst_id] += 1

                        # Periodic flush
                        buffers[inst_id].flush()

                        # Log stats every 30 s
                        now = time.monotonic()
                        if now - last_log >= 30:
                            remaining = max(0, deadline - now)
                            rem_str = f"{remaining/60:.1f}min left" if duration_min > 0 else "∞"
                            for s in symbols:
                                st = states[s].book
                                mid = st.mid() if st.is_valid() else 0
                                buf = buffers[s]
                                logger.info(
                                    f"[{s}] mid={mid:,.1f}  "
                                    f"ticks={buf.total:,}  {rem_str}"
                                )
                            last_log = now

                finally:
                    hb_task.cancel()

        except (websockets.exceptions.ConnectionClosedError,
                websockets.exceptions.WebSocketException,
                OSError) as e:
            logger.warning(f"WS disconnected: {e}  — reconnecting in {reconnect_delay:.1f}s …")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30)

    # Final flush
    logger.info("Flushing remaining buffers …")
    for s, buf in buffers.items():
        buf.flush(force=True)
        logger.info(f"[{s}] total ticks collected: {buf.total:,}")

    _print_summary(buffers, session_tag, symbols)


def _print_summary(buffers: dict, session_tag: str, symbols: list[str]) -> None:
    """Print collected file paths and quick stats."""
    print("\n" + "=" * 60)
    print(f"  Streaming session complete — {session_tag}")
    print("=" * 60)
    for s in symbols:
        out_dir = DATA_DIR / s.replace("-", "_")
        files = sorted(out_dir.glob(f"ob_ticks_{session_tag}_*.parquet"))
        total_rows = sum(
            pq.read_metadata(f).num_rows for f in files
        )
        print(f"\n  {s}")
        print(f"    Total ticks : {total_rows:,}")
        print(f"    Files       : {len(files)}")
        for f in files:
            print(f"      {f}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stream OKX order book ticks to Parquet"
    )
    parser.add_argument(
        "--symbols", nargs="+",
        default=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        help="Instrument IDs to subscribe",
    )
    parser.add_argument(
        "--duration", type=float, default=60,
        metavar="MIN",
        help="Collection duration in minutes (0 = run until Ctrl-C)",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}",
        level="INFO",
    )

    stop_event = asyncio.Event()

    # Handle Ctrl-C gracefully
    def _handle_signal(*_):
        logger.info("Interrupt received — stopping after current flush …")
        stop_event.set()

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    asyncio.run(stream(args.symbols, args.duration, stop_event))


if __name__ == "__main__":
    main()
