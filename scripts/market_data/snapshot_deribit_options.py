"""Snapshot Deribit BTC/ETH option-surface aggregates."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.external_store import ExternalDataStore
from scripts.market_data.ingest_external import _fetch_rows, _load_external_config


DEFAULT_DATASETS = ("optsurf_deribit_btc", "optsurf_deribit_eth")


async def _snapshot(args: argparse.Namespace) -> None:
    datasets = _load_external_config(args.config)
    cfg = load_config(settings_path=args.settings, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        raise SystemExit("storage.timescale_dsn is not set")
    async with await ExternalDataStore.from_dsn(dsn, min_size=1, max_size=2) as store:
        for dataset_id in args.dataset:
            if dataset_id not in datasets:
                raise SystemExit(f"unknown dataset: {dataset_id}")
            dataset_cfg = datasets[dataset_id]
            await store.upsert_dataset(dataset_id, dataset_cfg)
            rows = _fetch_rows(dataset_id, dataset_cfg, None, None)
            if not rows:
                raise SystemExit(f"{dataset_id}: empty snapshot")
            job_id = await store.start_fetch_job(dataset_id, str(dataset_cfg["provider"]), None, None)
            try:
                stats = await store.upsert_observations(dataset_id, rows)
                await store.finish_fetch_job(
                    job_id,
                    status="success",
                    rows_fetched=len(rows),
                    rows_inserted=stats["inserted"],
                    rows_updated=stats["updated"],
                )
                cursor = max(row["observed_at"] for row in rows)
                await store.update_checkpoint(
                    dataset_id,
                    direction="forward",
                    cursor_time=cursor,
                    request_count=1,
                    row_count=len(rows),
                    status="success",
                )
            except Exception as exc:
                await store.finish_fetch_job(job_id, status="failed", error_message=str(exc))
                raise
            for row in rows:
                print(
                    f"{dataset_id}: observed_at={row['observed_at'].isoformat()} "
                    f"value_num={row['value_num']} inserted={stats['inserted']} updated={stats['updated']}"
                )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", action="append", default=None)
    parser.add_argument("--config", default="config/external_data.yaml")
    parser.add_argument("--settings", default="config/settings.yaml")
    args = parser.parse_args(argv)
    if args.dataset is None:
        args.dataset = list(DEFAULT_DATASETS)
    return args


def main() -> None:
    args = _parse_args()
    asyncio.run(_snapshot(args))


if __name__ == "__main__":
    main()
