"""Fetch configured external datasets into external_observations."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import click
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.external_clients import (
    BinanceOIClient,
    DeribitDVOLClient,
    FREDClient,
    FearGreedClient,
    NasdaqDataLinkClient,
    YFinanceClient,
)
from okx_quant.data.external_store import ExternalDataStore


class _EmptyFetchError(click.ClickException):
    pass


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _load_external_config(path: str) -> dict[str, dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as fh:
        payload = yaml.safe_load(fh) or {}
    datasets = payload.get("datasets") or {}
    if not isinstance(datasets, dict):
        raise click.ClickException("external_data.yaml must contain a datasets mapping")
    for dataset_id, cfg in datasets.items():
        if str(cfg.get("adapter") or "") == "fred" and int(cfg.get("publish_lag_days", 1)) < 1:
            raise click.ClickException(f"{dataset_id}: publish_lag_days must be >= 1")
    return datasets


def _select_datasets(datasets: dict[str, dict[str, Any]], dataset: tuple[str, ...], include_all: bool) -> list[str]:
    if include_all:
        return sorted(datasets.keys())
    selected = list(dataset)
    if not selected:
        raise click.ClickException("Pass --dataset or --all")
    missing = [name for name in selected if name not in datasets]
    if missing:
        raise click.ClickException(f"Unknown external dataset(s): {', '.join(missing)}")
    return selected


def _build_client(dataset_id: str, cfg: dict[str, Any]):
    adapter = str(cfg.get("adapter") or "")
    if adapter == "binance_oi":
        return BinanceOIClient()
    if adapter == "deribit_dvol":
        return DeribitDVOLClient()
    if adapter == "fear_greed":
        return FearGreedClient()
    if adapter == "fred":
        env_name = str(cfg.get("api_key_env") or "FRED_API_KEY")
        api_key = os.environ.get(env_name)
        if not api_key:
            raise click.ClickException(f"{dataset_id} requires ${env_name}")
        return FREDClient(api_key=api_key, publish_lag_days=int(cfg.get("publish_lag_days", 1)))
    if adapter == "nasdaq_data_link":
        env_name = str(cfg.get("api_key_env") or "NASDAQ_DATA_LINK_API_KEY")
        api_key = os.environ.get(env_name)
        if not api_key:
            raise click.ClickException(f"{dataset_id} requires ${env_name}")
        return NasdaqDataLinkClient(api_key=api_key, publish_lag_days=int(cfg.get("publish_lag_days", 1)))
    if adapter == "yfinance":
        return YFinanceClient(publish_lag_days=int(cfg.get("publish_lag_days", 1)))
    raise click.ClickException(f"{dataset_id} has unsupported adapter: {adapter}")


def _fetch_rows(dataset_id: str, cfg: dict[str, Any], start: Optional[datetime], end: Optional[datetime]) -> list[dict[str, Any]]:
    client = _build_client(dataset_id, cfg)
    adapter = str(cfg.get("adapter") or "")
    if adapter == "binance_oi":
        return client.fetch(
            symbol=str(cfg.get("symbol") or "BTCUSDT"),
            start=start,
            end=end,
            interval=str(cfg.get("interval") or "1h"),
        )
    if adapter == "deribit_dvol":
        return client.fetch(
            currency=str(cfg.get("currency") or "BTC"),
            start=start,
            end=end,
            resolution=str(cfg.get("resolution") or "1D"),
        )
    if adapter == "fear_greed":
        return client.fetch(start=start, end=end)
    if adapter == "fred":
        return client.fetch(series_id=str(cfg.get("series_id") or "DGS10"), start=start, end=end)
    if adapter == "nasdaq_data_link":
        code = cfg.get("dataset_code")
        if not code and cfg.get("dataset_code_env"):
            code = os.environ.get(str(cfg["dataset_code_env"]))
        if not code:
            hint = f" or ${cfg['dataset_code_env']}" if cfg.get("dataset_code_env") else ""
            raise click.ClickException(f"{dataset_id} requires dataset_code{hint}")
        return client.fetch(dataset_code=str(code), start=start, end=end)
    if adapter == "yfinance":
        return client.fetch(
            ticker=str(cfg.get("ticker") or "BTC=F"),
            start=start,
            end=end,
            interval=str(cfg.get("interval") or "1d"),
        )
    return []


async def _ingest_one(
    store: ExternalDataStore,
    dataset_id: str,
    cfg: dict[str, Any],
    start: Optional[datetime],
    end: Optional[datetime],
    dry_run: bool,
) -> None:
    await store.upsert_dataset(dataset_id, cfg)
    if dry_run:
        click.echo(
            f"[dry-run] {dataset_id}: provider={cfg.get('provider')} "
            f"adapter={cfg.get('adapter')} start={start} end={end}"
        )
        return

    job_id = await store.start_fetch_job(dataset_id, str(cfg["provider"]), start, end)
    try:
        rows = _fetch_rows(dataset_id, cfg, start, end)
        if not rows and bool(cfg.get("fail_on_empty_fetch", False)):
            raise _EmptyFetchError(f"{dataset_id}: empty fetch; refusing to update checkpoint")
        stats = await store.upsert_observations(dataset_id, rows)
        await store.finish_fetch_job(
            job_id,
            status="success",
            rows_fetched=len(rows),
            rows_inserted=stats["inserted"],
            rows_updated=stats["updated"],
        )
        cursor = max((row["observed_at"] for row in rows), default=end or start)
        await store.update_checkpoint(
            dataset_id,
            direction="backfill" if start else "forward",
            cursor_time=cursor,
            request_count=1,
            row_count=len(rows),
            status="success",
        )
        click.echo(
            f"{dataset_id}: fetched={len(rows)} inserted={stats['inserted']} "
            f"updated={stats['updated']}"
        )
    except _EmptyFetchError as exc:
        await store.finish_fetch_job(job_id, status="failed", error_message=str(exc))
        raise
    except Exception as exc:
        await store.finish_fetch_job(job_id, status="failed", error_message=str(exc))
        await store.update_checkpoint(
            dataset_id,
            direction="backfill" if start else "forward",
            cursor_time=start,
            request_count=1,
            row_count=0,
            status="failed",
            last_error=str(exc),
        )
        raise


async def _main(
    datasets: dict[str, dict[str, Any]],
    selected: list[str],
    settings_path: str,
    start: Optional[datetime],
    end: Optional[datetime],
    dry_run: bool,
) -> None:
    if dry_run:
        for dataset_id in selected:
            cfg = datasets[dataset_id]
            _build_client(dataset_id, cfg)
            click.echo(
                f"[dry-run] {dataset_id}: provider={cfg.get('provider')} "
                f"adapter={cfg.get('adapter')} start={start} end={end}"
            )
        return

    cfg = load_config(settings_path=settings_path, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        raise click.ClickException("storage.timescale_dsn is not set")
    async with await ExternalDataStore.from_dsn(dsn, min_size=1, max_size=2) as store:
        for dataset_id in selected:
            await _ingest_one(store, dataset_id, datasets[dataset_id], start, end, dry_run)


@click.command()
@click.option("--dataset", "dataset_names", multiple=True, help="Dataset id from config/external_data.yaml")
@click.option("--all", "include_all", is_flag=True, help="Ingest all configured datasets")
@click.option("--start", default=None, help="UTC start date/time")
@click.option("--end", default=None, help="UTC end date/time")
@click.option("--config", "external_config", default="config/external_data.yaml", show_default=True)
@click.option("--settings", default="config/settings.yaml", show_default=True)
@click.option("--dry-run", is_flag=True, help="Validate selection and upsert dataset metadata only")
def cli(
    dataset_names: tuple[str, ...],
    include_all: bool,
    start: Optional[str],
    end: Optional[str],
    external_config: str,
    settings: str,
    dry_run: bool,
) -> None:
    datasets = _load_external_config(external_config)
    selected = _select_datasets(datasets, dataset_names, include_all)
    asyncio.run(_main(datasets, selected, settings, _parse_dt(start), _parse_dt(end), dry_run))


if __name__ == "__main__":
    cli()
