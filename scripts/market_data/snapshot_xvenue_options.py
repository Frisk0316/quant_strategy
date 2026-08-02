"""Store hourly H-039 option-IV snapshots and fail the task on detected gaps."""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.external_store import ExternalDataStore
from scripts.market_data.ingest_external import _ingest_one, _load_external_config


DEFAULT_DATASETS = (
    "xvenue_opt_iv_okx_btc",
    "xvenue_opt_iv_okx_eth",
    "xvenue_opt_iv_bybit_btc",
    "xvenue_opt_iv_bybit_eth",
    "xvenue_opt_iv_deribit_btc",
    "xvenue_opt_iv_deribit_eth",
)


async def _snapshot(args: argparse.Namespace) -> None:
    datasets = _load_external_config(args.config)
    missing = [dataset_id for dataset_id in args.dataset if dataset_id not in datasets]
    if missing:
        raise SystemExit(f"unknown dataset(s): {', '.join(missing)}")
    cfg = load_config(settings_path=args.settings, require_secrets=False)
    if not cfg.storage.timescale_dsn:
        raise SystemExit("storage.timescale_dsn is not set")

    gaps = []
    failures = []
    async with await ExternalDataStore.from_dsn(
        cfg.storage.timescale_dsn,
        min_size=1,
        max_size=2,
    ) as store:
        for dataset_id in args.dataset:
            before = await store.summarize_observations(dataset_id)
            try:
                await _ingest_one(
                    store,
                    dataset_id,
                    datasets[dataset_id],
                    None,
                    None,
                    False,
                )
            except Exception as exc:
                failures.append(f"{dataset_id}={exc}")
                print(f"{dataset_id}: failed; continuing: {exc}", file=sys.stderr)
                continue
            after = await store.summarize_observations(dataset_id)
            gap = _gap_hours(
                before.get("last_observed_at"),
                after.get("last_observed_at"),
                args.max_gap_hours,
            )
            if gap is not None:
                gaps.append(f"{dataset_id}={gap:.1f}h")
    alerts = []
    if failures:
        alerts.append(f"snapshot failures: {', '.join(failures)}")
    if gaps:
        alerts.append(f"snapshot gap alert: {', '.join(gaps)}")
    if alerts:
        raise SystemExit("; ".join(alerts))


def _gap_hours(
    previous: Optional[datetime],
    current: Optional[datetime],
    maximum: float,
) -> Optional[float]:
    if previous is None or current is None or current <= previous:
        return None
    hours = (current - previous).total_seconds() / 3600
    return hours if hours > maximum else None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", action="append", default=None)
    parser.add_argument("--config", default="config/external_data.yaml")
    parser.add_argument("--settings", default="config/settings.yaml")
    parser.add_argument(
        "--max-gap-hours",
        type=float,
        default=1.5,
        help="Exit non-zero after storing the current snapshot if prior coverage has a larger gap.",
    )
    args = parser.parse_args(argv)
    if args.dataset is None:
        args.dataset = list(DEFAULT_DATASETS)
    if args.max_gap_hours <= 0:
        parser.error("--max-gap-hours must be positive")
    return args


def main() -> None:
    asyncio.run(_snapshot(_parse_args()))


if __name__ == "__main__":
    main()
