"""Backfill CMC/top-market-cap USDT perpetual 1m candles from Binance.

The script resolves the top market-cap crypto symbols to Binance USD-M
perpetual contracts, then writes both:
  - multi-exchange tables: market_instruments / market_klines
  - legacy strategy tables: instruments / raw_candles / canonical_candles

Examples:
    python scripts/market_data/backfill_cmc_top_binance.py --dry-run
    python scripts/market_data/backfill_cmc_top_binance.py --top-n 100
    python scripts/market_data/backfill_cmc_top_binance.py --symbols BTC,ETH,SOL
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import click
import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore
from okx_quant.data.exchange_clients.binance_public import BinancePublicClient


BAR = "1m"
BAR_MS = 60_000
DEFAULT_START = "2024-01-01"
DEFAULT_END = "2026-05-11"
CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
CMC_WEB_URL = "https://coinmarketcap.com/coins/"
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"

SYMBOL_ALIASES = {
    "MATIC": ["POL", "MATIC"],
    "LUNA": ["LUNA2", "LUNA"],
}


@dataclass(frozen=True)
class MarketAsset:
    rank: int
    symbol: str
    name: str
    source: str


@dataclass(frozen=True)
class BinanceContract:
    symbol: str
    base_asset: str
    onboard_ms: int | None
    status: str


@dataclass(frozen=True)
class ResolvedSymbol:
    rank: int
    asset_symbol: str
    asset_name: str
    binance_symbol: str
    canonical_inst_id: str
    effective_start: datetime
    listing_time: datetime | None


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _from_ms(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def _strip_contract_prefix(base_asset: str) -> str:
    text = base_asset.upper()
    while text and text[0].isdigit():
        text = text[1:]
    return text


def _canonical_inst_id(asset_symbol: str) -> str:
    return f"{asset_symbol.upper()}-USDT-SWAP"


def _load_manual_assets(symbols: str, symbols_file: str | None) -> list[MarketAsset]:
    loaded: list[str] = []
    if symbols:
        loaded.extend(s.strip() for s in symbols.split(",") if s.strip())
    if symbols_file:
        with open(symbols_file, encoding="utf-8") as f:
            for line in f:
                value = line.strip()
                if value and not value.startswith("#"):
                    loaded.append(value.split(",")[0].strip())
    seen: set[str] = set()
    assets: list[MarketAsset] = []
    for symbol in loaded:
        normalized = symbol.upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        assets.append(MarketAsset(len(assets) + 1, normalized, normalized, "manual"))
    return assets


def _fetch_cmc_assets(top_n: int, timeout: float) -> list[MarketAsset]:
    api_key = os.environ.get("CMC_API_KEY") or os.environ.get("COINMARKETCAP_API_KEY")
    if not api_key:
        return []
    params = {
        "start": "1",
        "limit": str(top_n),
        "convert": "USD",
        "sort": "market_cap",
        "sort_dir": "desc",
    }
    headers = {"X-CMC_PRO_API_KEY": api_key}
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(CMC_URL, params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
    assets = []
    for item in payload.get("data", []):
        assets.append(
            MarketAsset(
                rank=int(item.get("cmc_rank") or len(assets) + 1),
                symbol=str(item.get("symbol") or "").upper(),
                name=str(item.get("name") or ""),
                source="coinmarketcap",
            )
        )
    return [a for a in assets if a.symbol]


def _fetch_cmc_web_assets(top_n: int, timeout: float) -> list[MarketAsset]:
    """Best-effort no-key parser for CoinMarketCap's rendered coins page."""
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(CMC_WEB_URL)
        resp.raise_for_status()
        html = resp.text
    marker = '"cryptoCurrencyList":'
    marker_pos = html.find(marker)
    if marker_pos < 0:
        return []
    array_pos = html.find("[", marker_pos)
    if array_pos < 0:
        return []
    try:
        payload, _ = json.JSONDecoder().raw_decode(html[array_pos:])
    except json.JSONDecodeError:
        return []

    assets: list[MarketAsset] = []
    fallback_rank = 1
    for item in payload:
        symbol = str(item.get("symbol") or "").upper()
        name = str(item.get("name") or "")
        if not symbol:
            continue
        rank_value = item.get("cmcRank") or item.get("rank")
        if rank_value is None:
            # CoinMarketCap page can include index products before rank 1.
            if symbol.startswith("CMC"):
                continue
            rank = fallback_rank
            fallback_rank += 1
        else:
            rank = int(rank_value)
        if rank < 1 or rank > top_n:
            continue
        assets.append(MarketAsset(rank=rank, symbol=symbol, name=name, source="coinmarketcap-web"))
    assets.sort(key=lambda a: a.rank)
    return assets[:top_n]


def _fetch_coingecko_assets(top_n: int, timeout: float) -> list[MarketAsset]:
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": str(min(max(top_n, 1), 250)),
        "page": "1",
        "sparkline": "false",
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(COINGECKO_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
    assets = []
    for item in payload:
        rank = int(item.get("market_cap_rank") or len(assets) + 1)
        assets.append(
            MarketAsset(
                rank=rank,
                symbol=str(item.get("symbol") or "").upper(),
                name=str(item.get("name") or ""),
                source="coingecko",
            )
        )
    return [a for a in assets if a.symbol]


def load_market_assets(
    *,
    top_n: int,
    symbols: str,
    symbols_file: str | None,
    allow_coingecko_fallback: bool,
    timeout: float,
) -> list[MarketAsset]:
    manual = _load_manual_assets(symbols, symbols_file)
    if manual:
        return manual[:top_n]

    cmc = _fetch_cmc_assets(top_n, timeout)
    if cmc:
        return cmc[:top_n]

    cmc_web = _fetch_cmc_web_assets(top_n, timeout)
    if cmc_web:
        click.echo("Using CoinMarketCap web ranking fallback.")
        return cmc_web[:top_n]

    if not allow_coingecko_fallback:
        raise click.ClickException(
            "CMC_API_KEY/COINMARKETCAP_API_KEY is required when CoinGecko fallback is disabled."
        )
    click.echo("WARN: CMC API key not found; using CoinGecko market-cap ranking fallback.")
    return _fetch_coingecko_assets(top_n, timeout)[:top_n]


def load_binance_contracts(client: BinancePublicClient) -> dict[str, BinanceContract]:
    info = client.get_futures_exchange_info()
    contracts: dict[str, BinanceContract] = {}
    for item in info.get("symbols", []):
        if item.get("contractType") != "PERPETUAL":
            continue
        if item.get("quoteAsset") != "USDT":
            continue
        status = str(item.get("status") or "")
        if status != "TRADING":
            continue
        symbol = str(item.get("symbol") or "").upper()
        if not symbol:
            continue
        contracts[symbol] = BinanceContract(
            symbol=symbol,
            base_asset=str(item.get("baseAsset") or symbol.removesuffix("USDT")).upper(),
            onboard_ms=int(item["onboardDate"]) if item.get("onboardDate") else None,
            status=status,
        )
    return contracts


def resolve_assets(
    assets: list[MarketAsset],
    contracts: dict[str, BinanceContract],
    requested_start: datetime,
) -> tuple[list[ResolvedSymbol], list[MarketAsset]]:
    by_symbol = contracts
    by_base: dict[str, BinanceContract] = {}
    for contract in contracts.values():
        by_base.setdefault(contract.base_asset.upper(), contract)
        by_base.setdefault(_strip_contract_prefix(contract.base_asset), contract)

    resolved: list[ResolvedSymbol] = []
    skipped: list[MarketAsset] = []
    seen_contracts: set[str] = set()
    for asset in assets:
        candidates = [asset.symbol, *SYMBOL_ALIASES.get(asset.symbol, [])]
        contract: BinanceContract | None = None
        for candidate in candidates:
            direct_symbol = f"{candidate}USDT"
            prefixed_symbol = f"1000{candidate}USDT"
            contract = by_symbol.get(direct_symbol) or by_symbol.get(prefixed_symbol) or by_base.get(candidate)
            if contract:
                break
        if not contract or contract.symbol in seen_contracts:
            skipped.append(asset)
            continue
        listing_time = _from_ms(contract.onboard_ms)
        effective_start = max(requested_start, listing_time) if listing_time else requested_start
        resolved.append(
            ResolvedSymbol(
                rank=asset.rank,
                asset_symbol=asset.symbol,
                asset_name=asset.name,
                binance_symbol=contract.symbol,
                canonical_inst_id=_canonical_inst_id(asset.symbol),
                effective_start=effective_start,
                listing_time=listing_time,
            )
        )
        seen_contracts.add(contract.symbol)
    return resolved, skipped


def write_manifest(
    path: Path,
    resolved: list[ResolvedSymbol],
    skipped: list[MarketAsset],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "status", "rank", "asset_symbol", "asset_name", "binance_symbol",
            "canonical_inst_id", "listing_time", "effective_start",
        ])
        for item in resolved:
            writer.writerow([
                "resolved", item.rank, item.asset_symbol, item.asset_name,
                item.binance_symbol, item.canonical_inst_id,
                item.listing_time.isoformat() if item.listing_time else "",
                item.effective_start.isoformat(),
            ])
        for item in skipped:
            writer.writerow(["skipped_no_binance_usdt_perp", item.rank, item.symbol, item.name, "", "", "", ""])


async def _last_canonical_ts(store: CandleStore, inst_id: str, start: datetime, end: datetime) -> datetime | None:
    row = await store._pool.fetchrow(
        """
        SELECT MAX(ts) AS last_ts
        FROM canonical_candles
        WHERE inst_id=$1 AND bar='1m' AND ts >= $2 AND ts < $3
        """,
        inst_id,
        start,
        end,
    )
    return row["last_ts"] if row and row["last_ts"] else None


async def backfill_one(
    *,
    dsn: str,
    item: ResolvedSymbol,
    requested_end: datetime,
    request_timeout_seconds: float,
    sleep_seconds: float,
    flush_pages: int,
    force_refresh: bool,
) -> dict[str, Any]:
    store = await CandleStore.from_dsn(dsn, min_size=1, max_size=3)
    client = BinancePublicClient(timeout=request_timeout_seconds, rate_sleep=sleep_seconds)
    job_id: str | None = None
    rows_written = 0
    request_count = 0
    last_flush_request_count = 0
    buffer: list[dict] = []
    start = item.effective_start
    try:
        if not force_refresh:
            last_ts = await _last_canonical_ts(store, item.canonical_inst_id, item.effective_start, requested_end)
            if last_ts:
                start = max(item.effective_start, last_ts + timedelta(minutes=1))
        if start >= requested_end:
            return {
                "symbol": item.binance_symbol,
                "canonical_inst_id": item.canonical_inst_id,
                "status": "covered",
                "rows": 0,
                "start": item.effective_start.isoformat(),
                "end": requested_end.isoformat(),
            }

        await store.register_instrument(
            inst_id=item.canonical_inst_id,
            base_ccy=item.asset_symbol,
            exchange="binance",
            inst_type="SWAP",
        )
        await store.register_instrument_bar(item.canonical_inst_id, "1m")
        instrument_id = await store.register_market_instrument(
            exchange="binance",
            inst_id=item.binance_symbol,
            normalized_symbol=item.binance_symbol.removesuffix("USDT"),
            base_asset=item.asset_symbol,
            quote_asset="USDT",
            settlement_asset="USDT",
            market_type="linear_perpetual",
            contract_type="perpetual",
            listing_time=item.listing_time,
            canonical_inst_id=item.canonical_inst_id,
        )
        job_id = await store.start_job(
            "backfill",
            "binance",
            inst_id=item.binance_symbol,
            bar="1m",
            start_ts=start,
            end_ts=requested_end,
            details={
                "mode": "cmc_top_binance",
                "rank": item.rank,
                "asset_symbol": item.asset_symbol,
                "canonical_inst_id": item.canonical_inst_id,
            },
        )
        cursor_ms = _to_ms(start)
        end_ms = _to_ms(requested_end)
        await store.update_checkpoint("binance", "klines_1m", item.binance_symbol, "forward", cursor_ms, "running")

        while cursor_ms < end_ms:
            page = client.get_klines(
                item.binance_symbol,
                "1m",
                start_ms=cursor_ms,
                end_ms=end_ms - 1,
                limit=1500,
                market_type="futures",
            )
            page = [r for r in page if cursor_ms <= int(r["ts_ms"]) < end_ms]
            request_count += 1
            if not page:
                break
            buffer.extend(page)
            cursor_ms = int(page[-1]["ts_ms"]) + BAR_MS
            if request_count % flush_pages == 0:
                request_delta = request_count - last_flush_request_count
                rows_written += await _flush_rows(store, instrument_id, item, buffer, cursor_ms, request_delta)
                last_flush_request_count = request_count
                buffer.clear()

        if buffer:
            request_delta = request_count - last_flush_request_count
            rows_written += await _flush_rows(store, instrument_id, item, buffer, cursor_ms, request_delta)

        await store.update_instrument_bar_bounds(item.canonical_inst_id, "1m")
        await store.update_checkpoint("binance", "klines_1m", item.binance_symbol, "forward", cursor_ms, "success")
        await store.finish_job(
            job_id,
            "success",
            rows_fetched=rows_written,
            rows_inserted=rows_written,
            details={"request_count": request_count, "final_cursor_ms": cursor_ms},
        )
        return {
            "symbol": item.binance_symbol,
            "canonical_inst_id": item.canonical_inst_id,
            "status": "success",
            "rows": rows_written,
            "requests": request_count,
            "start": start.isoformat(),
            "end": requested_end.isoformat(),
        }
    except Exception as exc:
        if job_id:
            await store.finish_job(job_id, "failed", error_message=str(exc))
        raise
    finally:
        client.close()
        await store.close()


async def _flush_rows(
    store: CandleStore,
    instrument_id: str,
    item: ResolvedSymbol,
    rows: list[dict],
    cursor_ms: int,
    request_count_delta: int,
) -> int:
    if not rows:
        return 0
    deduped = {int(row["ts_ms"]): row for row in rows}
    ordered = [deduped[k] for k in sorted(deduped)]
    await store.upsert_market_klines(ordered, instrument_id=instrument_id, bar="1m", data_source="binance")
    await store.upsert_raw_candles(ordered, source="binance", inst_id=item.canonical_inst_id, bar="1m")
    await store.upsert_canonical_candles(
        ordered,
        inst_id=item.canonical_inst_id,
        bar="1m",
        source_primary="binance",
        quality_status="raw",
    )
    await store.update_checkpoint(
        "binance",
        "klines_1m",
        item.binance_symbol,
        "forward",
        cursor_ms,
        "running",
        request_count_delta=request_count_delta,
        row_count_delta=len(ordered),
    )
    return len(ordered)


@click.command()
@click.option("--top-n", default=100, show_default=True, type=int)
@click.option("--symbols", default="", help="Comma-separated crypto symbols. Overrides market-cap lookup.")
@click.option("--symbols-file", default=None, type=click.Path(exists=True, dir_okay=False))
@click.option("--start", default=DEFAULT_START, show_default=True)
@click.option("--end", default=DEFAULT_END, show_default=True, help="Exclusive end date/time.")
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option("--manifest", default="results/market_data/cmc_top_binance_manifest.csv", show_default=True)
@click.option("--dry-run", is_flag=True, help="Resolve symbols and write manifest without fetching candles.")
@click.option("--force-refresh", is_flag=True, help="Fetch from effective start even if canonical rows already exist.")
@click.option("--allow-coingecko-fallback/--no-coingecko-fallback", default=True, show_default=True)
@click.option("--request-timeout-seconds", default=30.0, show_default=True, type=float)
@click.option("--sleep-seconds", default=0.08, show_default=True, type=float)
@click.option("--flush-pages", default=10, show_default=True, type=int)
def cli(
    top_n: int,
    symbols: str,
    symbols_file: str | None,
    start: str,
    end: str,
    config: str,
    manifest: str,
    dry_run: bool,
    force_refresh: bool,
    allow_coingecko_fallback: bool,
    request_timeout_seconds: float,
    sleep_seconds: float,
    flush_pages: int,
) -> None:
    """Fetch top-market-cap Binance USDT perpetual 1m OHLCV into TimescaleDB."""
    requested_start = _parse_time(start)
    requested_end = _parse_time(end)
    if requested_start >= requested_end:
        raise click.ClickException("--start must be earlier than --end")

    assets = load_market_assets(
        top_n=top_n,
        symbols=symbols,
        symbols_file=symbols_file,
        allow_coingecko_fallback=allow_coingecko_fallback,
        timeout=request_timeout_seconds,
    )
    client = BinancePublicClient(timeout=request_timeout_seconds)
    try:
        contracts = load_binance_contracts(client)
    finally:
        client.close()

    resolved, skipped = resolve_assets(assets, contracts, requested_start)
    write_manifest(Path(manifest), resolved, skipped)
    click.echo(f"Resolved {len(resolved)} Binance USDT perpetuals; skipped {len(skipped)}. Manifest: {manifest}")
    if dry_run:
        for item in resolved:
            click.echo(
                f"{item.rank:>3} {item.asset_symbol:<8} -> {item.binance_symbol:<16} "
                f"{item.canonical_inst_id:<20} start={item.effective_start.date()}"
            )
        return

    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = os.environ.get("DATABASE_URL") or cfg.storage.timescale_dsn
    if not dsn:
        raise click.ClickException("storage.timescale_dsn is not set")

    async def _run() -> None:
        started = time.monotonic()
        for idx, item in enumerate(resolved, start=1):
            click.echo(f"\n[{idx}/{len(resolved)}] {item.asset_symbol} -> {item.binance_symbol}")
            result = await backfill_one(
                dsn=dsn,
                item=item,
                requested_end=requested_end,
                request_timeout_seconds=request_timeout_seconds,
                sleep_seconds=sleep_seconds,
                flush_pages=flush_pages,
                force_refresh=force_refresh,
            )
            click.echo(f"  {result['status']} rows={result['rows']:,} requests={result.get('requests', 0)}")
        elapsed = time.monotonic() - started
        click.echo(f"\nDone in {elapsed / 60:.1f} minutes.")

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
