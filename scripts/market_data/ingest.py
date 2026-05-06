"""Long-running, resumable market-data ingestor.

Writes the multi-exchange canonical tables:
market_instruments, market_klines, market_funding_rates.
For backward compatibility, OKX data is also mirrored into the legacy
raw_candles/canonical_candles/funding_rates path used by the current backtests.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

import click

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore
from okx_quant.data.exchange_clients.binance_public import BinancePublicClient
from okx_quant.data.exchange_clients.bybit_public import BybitPublicClient
from okx_quant.data.exchange_clients.okx_public import OKXPublicClient


Dataset = Literal["klines_1m", "funding_rate"]
Direction = Literal["forward", "backward"]

BAR_MS = 60_000
EIGHT_HOURS_MS = 8 * 60 * 60 * 1000

DEFAULT_STARTS = {
    "binance": {
        "klines_1m": "2020-01-01T00:00:00Z",
        "funding_rate": "2019-10-09T00:00:00Z",
    },
    "okx": {
        "klines_1m": "2023-07-01T00:00:00Z",
        "funding_rate": "2022-03-01T00:00:00Z",
    },
    "bybit": {
        "klines_1m": "2020-03-25T00:00:00Z",
        "funding_rate": "2020-03-25T00:00:00Z",
    },
}


@dataclass
class FlushPolicy:
    every_requests: int = 10
    max_rows: int = 50_000
    every_seconds: float = 60.0


@dataclass
class IngestState:
    cursor_ms: int
    request_count: int = 0
    row_count: int = 0
    requests_since_flush: int = 0
    last_flush_ts: float = 0.0


def _parse_time(value: str | None, *, exchange: str, dataset: Dataset) -> datetime:
    if not value:
        value = DEFAULT_STARTS[exchange][dataset]
    if value.lower() == "now":
        return datetime.now(tz=timezone.utc)
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _base_ccy(symbol: str) -> str:
    if "-" in symbol:
        return symbol.split("-")[0]
    if symbol.endswith("USDT"):
        return symbol[:-4]
    return symbol


def _normalize_symbol(exchange: str, symbol: str) -> str:
    if exchange == "okx":
        return symbol.replace("-", "").replace("SWAP", "")
    return symbol


def _ensure_usdt_perp(exchange: str, symbol: str) -> None:
    if exchange == "okx":
        if not symbol.endswith("-USDT-SWAP"):
            raise ValueError(f"OKX symbol must be USDT SWAP, got {symbol}")
    elif not symbol.endswith("USDT"):
        raise ValueError(f"{exchange} symbol must be USDT linear perpetual, got {symbol}")


def _dedupe_sort(rows: list[dict]) -> list[dict]:
    seen: dict[int, dict] = {}
    for row in rows:
        seen[int(row["ts_ms"])] = row
    return [seen[k] for k in sorted(seen)]


def _infer_funding_intervals(rows: list[dict]) -> list[dict]:
    ordered = _dedupe_sort(rows)
    for idx, row in enumerate(ordered[:-1]):
        next_ts = int(ordered[idx + 1]["ts_ms"])
        row["funding_interval_hours"] = (next_ts - int(row["ts_ms"])) / 3_600_000.0
    return ordered


def _resume_cursor(
    *,
    direction: Direction,
    start_ms: int,
    end_ms: int,
    checkpoint_cursor_ms: int | None,
) -> int:
    default_cursor = end_ms + 1 if direction == "backward" else start_ms
    if checkpoint_cursor_ms is None:
        return default_cursor
    if direction == "forward":
        return max(start_ms, checkpoint_cursor_ms)
    return min(end_ms + 1, checkpoint_cursor_ms)


def _retry_fetch(fn: Callable[[], list[dict]], *, max_retries: int, backoff_seconds: float) -> list[dict]:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            sleep_s = backoff_seconds * (2 ** attempt)
            click.echo(f"  WARN request failed: {exc}; retrying in {sleep_s:.1f}s")
            time.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


def _make_client(exchange: str, timeout_seconds: float):
    if exchange == "binance":
        return BinancePublicClient(timeout=timeout_seconds)
    if exchange == "bybit":
        return BybitPublicClient(timeout=timeout_seconds)
    if exchange == "okx":
        return OKXPublicClient(timeout=timeout_seconds)
    raise ValueError(f"unsupported exchange: {exchange}")


def _fetch_page(
    *,
    client,
    exchange: str,
    dataset: Dataset,
    symbol: str,
    cursor_ms: int,
    start_ms: int,
    end_ms: int,
    direction: Direction,
) -> tuple[list[dict], int, bool]:
    if dataset == "klines_1m":
        if exchange == "binance":
            rows = client.get_klines(
                symbol, "1m", start_ms=cursor_ms, end_ms=end_ms - 1,
                limit=1500, market_type="futures",
            )
            rows = [r for r in rows if start_ms <= r["ts_ms"] < end_ms]
            next_cursor = (rows[-1]["ts_ms"] + BAR_MS) if rows else end_ms
            return rows, next_cursor, next_cursor >= end_ms or not rows

        if exchange == "bybit":
            window_end = min(cursor_ms + 1000 * BAR_MS - 1, end_ms - 1)
            rows = client.get_kline(
                symbol, "1m", start_ms=cursor_ms, end_ms=window_end,
                limit=1000, category="linear",
            )
            rows = [r for r in rows if start_ms <= r["ts_ms"] < end_ms]
            next_cursor = (rows[-1]["ts_ms"] + BAR_MS) if rows else window_end + 1
            return rows, next_cursor, next_cursor >= end_ms

        if exchange == "okx":
            if direction != "backward":
                raise ValueError("OKX klines_1m ingestion requires --direction backward")
            rows = client.get_history_candles(symbol, "1m", after_ms=cursor_ms, limit=300)
            rows = [r for r in rows if start_ms <= r["ts_ms"] < end_ms]
            if not rows:
                return [], start_ms - 1, True
            next_cursor = min(r["ts_ms"] for r in rows) - 1
            return rows, next_cursor, next_cursor < start_ms

    if dataset == "funding_rate":
        if exchange == "binance":
            rows = client.get_funding_rates(symbol, start_ms=cursor_ms, end_ms=end_ms - 1, limit=1000)
            rows = [r for r in rows if start_ms <= r["ts_ms"] < end_ms]
            next_cursor = (rows[-1]["ts_ms"] + 1) if rows else end_ms
            return rows, next_cursor, next_cursor >= end_ms or not rows

        if exchange == "bybit":
            window_end = min(cursor_ms + 200 * EIGHT_HOURS_MS - 1, end_ms - 1)
            rows = client.get_funding_rates(
                symbol, start_ms=cursor_ms, end_ms=window_end,
                limit=200, category="linear",
            )
            rows = [r for r in rows if start_ms <= r["ts_ms"] < end_ms]
            next_cursor = (rows[-1]["ts_ms"] + 1) if rows else window_end + 1
            return rows, next_cursor, next_cursor >= end_ms

        if exchange == "okx":
            if direction != "backward":
                raise ValueError("OKX funding_rate ingestion requires --direction backward")
            rows = client.get_funding_rate_history(symbol, after_ms=cursor_ms, limit=400)
            rows = [r for r in rows if start_ms <= r["ts_ms"] < end_ms]
            if not rows:
                return [], start_ms - 1, True
            next_cursor = min(r["ts_ms"] for r in rows) - 1
            return rows, next_cursor, next_cursor < start_ms

    raise ValueError(f"unsupported ingestion target: {exchange}/{dataset}")


async def _flush(
    *,
    store: CandleStore,
    exchange: str,
    dataset: Dataset,
    symbol: str,
    direction: Direction,
    buffer: list[dict],
    state: IngestState,
    checkpoint_status: str,
) -> int:
    rows = _infer_funding_intervals(buffer) if dataset == "funding_rate" else _dedupe_sort(buffer)
    if not rows:
        return 0

    base_ccy = _base_ccy(symbol)
    instrument_id = await store.register_market_instrument(
        exchange=exchange,
        inst_id=symbol,
        normalized_symbol=_normalize_symbol(exchange, symbol),
        base_asset=base_ccy,
        quote_asset="USDT",
        settlement_asset="USDT",
        market_type="linear_perpetual",
        contract_type="perpetual",
    )

    if dataset == "klines_1m":
        result = await store.upsert_market_klines(
            rows,
            instrument_id=instrument_id,
            bar="1m",
            data_source=exchange,
        )
        if exchange == "okx":
            await store.register_instrument(
                inst_id=symbol,
                base_ccy=base_ccy,
                exchange=exchange,
                inst_type="SWAP",
            )
            await store.register_instrument_bar(symbol, "1m")
            await store.upsert_raw_candles(rows, source=exchange, inst_id=symbol, bar="1m")
            await store.canonicalize_from_raw(exchange, symbol, "1m")
            await store.update_instrument_bar_bounds(symbol, "1m")
    else:
        result = await store.upsert_market_funding_rates(
            rows,
            instrument_id=instrument_id,
            data_source=exchange,
        )
        await store.refresh_market_funding_intervals(instrument_id)
        if exchange == "okx":
            await store.register_instrument(
                inst_id=symbol,
                base_ccy=base_ccy,
                exchange=exchange,
                inst_type="SWAP",
            )
            await store.upsert_funding_rates(rows, source=exchange, inst_id=symbol)
            await store.refresh_funding_intervals(exchange, symbol)

    inserted = int(result.get("inserted", len(rows)))
    await store.update_checkpoint(
        exchange,
        dataset,
        symbol,
        direction,
        state.cursor_ms,
        checkpoint_status,
        request_count_delta=state.requests_since_flush,
        row_count_delta=inserted,
    )
    state.requests_since_flush = 0
    state.last_flush_ts = time.monotonic()
    click.echo(
        f"  FLUSH {exchange} {dataset} {symbol}: rows={len(rows)} "
        f"checkpoint={state.cursor_ms}"
    )
    return inserted


async def ingest_symbol(
    *,
    dsn: str,
    exchange: str,
    dataset: Dataset,
    symbol: str,
    start_ms: int,
    end_ms: int,
    direction: Direction,
    policy: FlushPolicy,
    timeout_seconds: float,
    max_retries: int,
    backoff_seconds: float,
) -> None:
    _ensure_usdt_perp(exchange, symbol)
    store = await CandleStore.from_dsn(dsn)
    client = _make_client(exchange, timeout_seconds)
    job_id: str | None = None
    buffer: list[dict] = []
    state = IngestState(cursor_ms=end_ms + 1 if direction == "backward" else start_ms)
    state.last_flush_ts = time.monotonic()

    try:
        checkpoint = await store.get_checkpoint(exchange, dataset, symbol, direction)
        state.cursor_ms = _resume_cursor(
            direction=direction,
            start_ms=start_ms,
            end_ms=end_ms,
            checkpoint_cursor_ms=(
                int(checkpoint["cursor_time_ms"])
                if checkpoint and checkpoint.get("cursor_time_ms") is not None
                else None
            ),
        )

        bar = "1m" if dataset == "klines_1m" else None
        job_id = await store.start_job(
            job_type="backfill",
            source=exchange,
            inst_id=symbol,
            bar=bar,
            start_ts=datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc),
            end_ts=datetime.fromtimestamp(end_ms / 1000, tz=timezone.utc),
            details={
                "mode": "long_running_ingest",
                "dataset": dataset,
                "direction": direction,
                "normalized_symbol": _normalize_symbol(exchange, symbol),
                "flush_every_requests": policy.every_requests,
                "flush_max_rows": policy.max_rows,
                "flush_every_seconds": policy.every_seconds,
            },
        )
        await store.update_checkpoint(exchange, dataset, symbol, direction, state.cursor_ms, "running")

        click.echo(
            f"INGEST {exchange} {dataset} {symbol} "
            f"{datetime.fromtimestamp(start_ms/1000, tz=timezone.utc)} -> "
            f"{datetime.fromtimestamp(end_ms/1000, tz=timezone.utc)} "
            f"direction={direction} cursor={state.cursor_ms}"
        )

        done = False
        while not done:
            rows, next_cursor, done = _retry_fetch(
                lambda: _fetch_page(
                    client=client,
                    exchange=exchange,
                    dataset=dataset,
                    symbol=symbol,
                    cursor_ms=state.cursor_ms,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    direction=direction,
                ),
                max_retries=max_retries,
                backoff_seconds=backoff_seconds,
            )
            buffer.extend(rows)
            state.cursor_ms = next_cursor
            state.request_count += 1
            state.requests_since_flush += 1
            state.row_count += len(rows)
            click.echo(
                f"  request={state.request_count} cursor={state.cursor_ms} "
                f"rows={len(rows)} buffer={len(buffer)} done={done}"
            )

            should_flush = (
                state.requests_since_flush >= policy.every_requests
                or len(buffer) >= policy.max_rows
                or time.monotonic() - state.last_flush_ts >= policy.every_seconds
                or done
            )
            if should_flush and buffer:
                await _flush(
                    store=store,
                    exchange=exchange,
                    dataset=dataset,
                    symbol=symbol,
                    direction=direction,
                    buffer=buffer,
                    state=state,
                    checkpoint_status="success" if done else "running",
                )
                buffer.clear()

            if done:
                break

        await store.update_checkpoint(exchange, dataset, symbol, direction, state.cursor_ms, "success")
        await store.finish_job(
            job_id,
            "success",
            rows_fetched=state.row_count,
            rows_inserted=state.row_count,
            details={"request_count": state.request_count, "final_cursor_ms": state.cursor_ms},
        )
    except Exception as exc:
        if buffer:
            await _flush(
                store=store,
                exchange=exchange,
                dataset=dataset,
                symbol=symbol,
                direction=direction,
                buffer=buffer,
                state=state,
                checkpoint_status="partial",
            )
        await store.update_checkpoint(
            exchange, dataset, symbol, direction, state.cursor_ms,
            "failed", last_error=str(exc),
        )
        if job_id:
            await store.finish_job(job_id, "failed", error_message=str(exc))
        raise
    finally:
        client.close()
        await store.close()


@click.command()
@click.option("--exchange", required=True, type=click.Choice(["binance", "okx", "bybit"]))
@click.option("--dataset", required=True, type=click.Choice(["klines_1m", "funding_rate"]))
@click.option("--symbols", required=True, help="Comma-separated symbols, e.g. BTCUSDT,ETHUSDT")
@click.option("--start", default=None, help="ISO start time. Defaults to exchange-level start.")
@click.option("--end", default="now", show_default=True, help="ISO end time or now.")
@click.option("--direction", default="forward", type=click.Choice(["forward", "backward"]))
@click.option("--flush-every-requests", default=10, show_default=True, type=int,
              envvar="FLUSH_EVERY_REQUESTS")
@click.option("--flush-max-rows", default=50_000, show_default=True, type=int,
              envvar="FLUSH_MAX_ROWS")
@click.option("--flush-every-seconds", default=60.0, show_default=True, type=float,
              envvar="FLUSH_EVERY_SECONDS")
@click.option("--request-timeout-seconds", default=20.0, show_default=True, type=float,
              envvar="REQUEST_TIMEOUT_SECONDS")
@click.option("--http-max-retries", default=5, show_default=True, type=int,
              envvar="HTTP_MAX_RETRIES")
@click.option("--http-backoff-seconds", default=1.5, show_default=True, type=float,
              envvar="HTTP_BACKOFF_SECONDS")
@click.option("--config", default="config/settings.yaml", show_default=True)
def cli(
    exchange: str,
    dataset: Dataset,
    symbols: str,
    start: str | None,
    end: str,
    direction: Direction,
    flush_every_requests: int,
    flush_max_rows: int,
    flush_every_seconds: float,
    request_timeout_seconds: float,
    http_max_retries: int,
    http_backoff_seconds: float,
    config: str,
) -> None:
    """Backfill public USDT perpetual OHLCV/funding with checkpointed flushing."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = os.environ.get("DATABASE_URL") or cfg.storage.timescale_dsn
    if not dsn:
        raise click.ClickException("storage.timescale_dsn is not set")

    start_dt = _parse_time(start, exchange=exchange, dataset=dataset)
    end_dt = _parse_time(end, exchange=exchange, dataset=dataset)
    policy = FlushPolicy(
        every_requests=flush_every_requests,
        max_rows=flush_max_rows,
        every_seconds=flush_every_seconds,
    )

    async def _run() -> None:
        for symbol in [s.strip() for s in symbols.split(",") if s.strip()]:
            await ingest_symbol(
                dsn=dsn,
                exchange=exchange,
                dataset=dataset,
                symbol=symbol,
                start_ms=_to_ms(start_dt),
                end_ms=_to_ms(end_dt),
                direction=direction,
                policy=policy,
                timeout_seconds=request_timeout_seconds,
                max_retries=http_max_retries,
                backoff_seconds=http_backoff_seconds,
            )

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
