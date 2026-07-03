"""Download Binance Vision UM daily metrics into external_observations."""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import sys
import zipfile
from datetime import date, datetime, time, timezone, timedelta
from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from okx_quant.core.config import load_config  # noqa: E402
from okx_quant.data.external_store import ExternalDataStore  # noqa: E402

BASE_URL = "https://data.binance.vision/data/futures/um/daily/metrics"
PROVENANCE = "binance_vision_metrics"
EXPECTED_COLUMNS = (
    "create_time",
    "symbol",
    "sum_open_interest",
    "sum_open_interest_value",
    "count_toptrader_long_short_ratio",
    "sum_toptrader_long_short_ratio",
    "count_long_short_ratio",
    "sum_taker_long_short_vol_ratio",
)
DATASETS = {
    "BTCUSDT": "oi_binance_hist_btc",
    "ETHUSDT": "oi_binance_hist_eth",
}


class MissingDailyZip(Exception):
    """Raised when a daily Vision zip is not available."""


class BinanceVisionSchemaError(Exception):
    """Raised when the Binance Vision metrics schema is unavailable or unsafe."""


class LocalVisionMetricsSource:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def read_zip(self, symbol: str, day: date) -> bytes:
        path = self._path(symbol, day)
        if not path.exists():
            raise MissingDailyZip(str(path))
        return path.read_bytes()

    def source_url(self, symbol: str, day: date) -> str:
        return str(self._path(symbol, day))

    def _path(self, symbol: str, day: date) -> Path:
        filename = _zip_name(symbol, day)
        nested = self.root / symbol / filename
        return nested if nested.exists() else self.root / filename


class HttpVisionMetricsSource:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def read_zip(self, symbol: str, day: date) -> bytes:
        url = self.source_url(symbol, day)
        try:
            with urlopen(url, timeout=self.timeout) as response:  # noqa: S310 - public Binance data URL.
                return response.read()
        except HTTPError as exc:
            if exc.code == 404:
                raise MissingDailyZip(url) from exc
            raise
        except URLError as exc:
            raise BinanceVisionSchemaError(f"unable to fetch Binance Vision metrics: {exc}") from exc

    def source_url(self, symbol: str, day: date) -> str:
        return f"{self.base_url}/{symbol}/{_zip_name(symbol, day)}"


def validate_btc_schema(source: LocalVisionMetricsSource | HttpVisionMetricsSource, day: date) -> None:
    try:
        payload = source.read_zip("BTCUSDT", day)
    except MissingDailyZip as exc:
        raise BinanceVisionSchemaError(f"BTCUSDT schema check unavailable for {day}") from exc
    parse_metrics_zip(payload, expected_symbol="BTCUSDT", source_url=source.source_url("BTCUSDT", day))


def parse_metrics_zip(payload: bytes, *, expected_symbol: str, source_url: str) -> list[dict[str, Any]]:
    expected_symbol = expected_symbol.upper()
    with zipfile.ZipFile(BytesIO(payload)) as zf:
        csv_names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise BinanceVisionSchemaError(f"{source_url}: expected one CSV in metrics zip")
        with zf.open(csv_names[0]) as raw:
            reader = csv.DictReader(TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
            fieldnames = tuple((name or "").strip() for name in (reader.fieldnames or ()))
            if fieldnames != EXPECTED_COLUMNS:
                raise BinanceVisionSchemaError(f"{source_url}: schema mismatch {fieldnames!r}")
            rows = [_row_to_observation(row, expected_symbol, source_url) for row in reader]
    return sorted(rows, key=lambda row: row["observed_at"])


async def ingest_symbol(
    store: Any,
    source: LocalVisionMetricsSource | HttpVisionMetricsSource,
    *,
    symbol: str,
    dataset_id: str,
    start: date,
    end: date,
    dry_run: bool,
) -> dict[str, Any]:
    symbol = symbol.upper()
    rows: list[dict[str, Any]] = []
    missing_days: list[str] = []
    for day in _days(start, end):
        try:
            payload = source.read_zip(symbol, day)
        except MissingDailyZip:
            missing_days.append(day.isoformat())
            continue
        rows.extend(parse_metrics_zip(payload, expected_symbol=symbol, source_url=source.source_url(symbol, day)))

    rows.sort(key=lambda row: row["observed_at"])
    stats = {"rows": len(rows), "inserted": 0, "updated": 0}
    if not dry_run:
        await store.upsert_dataset(dataset_id, _dataset_config(dataset_id, symbol))
        job_id = await store.start_fetch_job(dataset_id, "binance_vision", _day_start(start), _day_start(end))
        try:
            stats = await store.upsert_observations(dataset_id, rows)
            await store.finish_fetch_job(
                job_id,
                status="success",
                rows_fetched=len(rows),
                rows_inserted=stats["inserted"],
                rows_updated=stats["updated"],
                details={"missing_days": missing_days, "provenance": PROVENANCE},
            )
            await store.update_checkpoint(
                dataset_id,
                direction="backfill",
                cursor_time=max((row["observed_at"] for row in rows), default=None),
                request_count=1,
                row_count=len(rows),
                status="success",
            )
        except Exception as exc:
            await store.finish_fetch_job(job_id, status="failed", error_message=str(exc))
            await store.update_checkpoint(
                dataset_id,
                direction="backfill",
                cursor_time=_day_start(start),
                request_count=1,
                row_count=0,
                status="failed",
                last_error=str(exc),
            )
            raise

    return {
        "symbol": symbol,
        "dataset_id": dataset_id,
        "first": rows[0]["observed_at"].isoformat() if rows else None,
        "last": rows[-1]["observed_at"].isoformat() if rows else None,
        "rows": len(rows),
        "missing_days": missing_days,
        "inserted": stats["inserted"],
        "updated": stats["updated"],
        "provenance": PROVENANCE,
    }


async def run(args: argparse.Namespace) -> list[dict[str, Any]]:
    start = _parse_day(args.start)
    end = _parse_day(args.end)
    if end <= start:
        raise SystemExit("--end must be after --start")
    symbols = [symbol.upper() for symbol in (args.symbol or ["BTCUSDT", "ETHUSDT"])]
    source = LocalVisionMetricsSource(args.source_dir) if args.source_dir else HttpVisionMetricsSource()
    validate_btc_schema(source, _parse_day(args.schema_date) if args.schema_date else start)

    if args.dry_run:
        store = None
        reports = [
            await ingest_symbol(
                store,
                source,
                symbol=symbol,
                dataset_id=_dataset_id(symbol),
                start=start,
                end=end,
                dry_run=True,
            )
            for symbol in symbols
        ]
        return reports

    dsn = args.dsn or load_config(settings_path=args.config, require_secrets=False).storage.timescale_dsn
    if not dsn:
        raise SystemExit("storage.timescale_dsn is not set; pass --dsn or use --dry-run")
    async with await ExternalDataStore.from_dsn(dsn, min_size=1, max_size=2) as store:
        return [
            await ingest_symbol(
                store,
                source,
                symbol=symbol,
                dataset_id=_dataset_id(symbol),
                start=start,
                end=end,
                dry_run=False,
            )
            for symbol in symbols
        ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", action="append", choices=sorted(DATASETS), help="Binance native symbol; repeatable")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD, exclusive")
    parser.add_argument("--schema-date", help="BTCUSDT one-day schema check date; defaults to --start")
    parser.add_argument("--source-dir", type=Path, help="Read local fixture zips instead of Binance Vision HTTP")
    parser.add_argument("--dsn", help="Override DATABASE_URL / config DSN for external_observations upsert")
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Parse/report only; do not write DB")
    return parser


def main(argv: Optional[list[str]] = None) -> None:
    reports = asyncio.run(run(build_parser().parse_args(argv)))
    print(json.dumps({"coverage": reports}, indent=2, sort_keys=True))


def _row_to_observation(row: dict[str, str], expected_symbol: str, source_url: str) -> dict[str, Any]:
    symbol = (row.get("symbol") or "").upper()
    if symbol != expected_symbol:
        raise BinanceVisionSchemaError(f"{source_url}: unexpected symbol {symbol!r}")
    observed_at = _parse_create_time(row["create_time"])
    notional = _to_float(row["sum_open_interest_value"])
    contracts = _to_float(row["sum_open_interest"])
    return {
        "observed_at": observed_at,
        "published_at": observed_at,
        "value_num": notional,
        "value_text": None,
        "fields": {
            "symbol": symbol,
            "unit": "USDT_notional",
            "value_unit": "USDT_notional",
            "source_value_field": "sum_open_interest_value",
            "open_interest_contracts": contracts,
            "provenance": PROVENANCE,
        },
        "quality_status": "raw",
        "raw_payload": {**row, "source_url": source_url, "provenance": PROVENANCE},
    }


def _dataset_config(dataset_id: str, symbol: str) -> dict[str, Any]:
    return {
        "provider": "binance_vision",
        "frequency": "5m",
        "value_kind": "scalar",
        "max_age_seconds": 604800,
        "source_url": f"{BASE_URL}/{symbol}/",
        "attribution": "Data source: Binance Vision futures UM daily metrics",
        "adapter": "binance_vision_metrics",
        "symbol": symbol,
        "unit": "USDT_notional",
        "source_value_field": "sum_open_interest_value",
        "provenance": PROVENANCE,
        "notes": f"{dataset_id} stores sum_open_interest_value as USDT_notional from Binance Vision metrics dumps.",
    }


def _dataset_id(symbol: str) -> str:
    try:
        return DATASETS[symbol.upper()]
    except KeyError as exc:
        raise SystemExit(f"unsupported symbol for P8 historical OI: {symbol}") from exc


def _zip_name(symbol: str, day: date) -> str:
    return f"{symbol.upper()}-metrics-{day.isoformat()}.zip"


def _parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _day_start(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _days(start: date, end: date) -> Iterable[date]:
    day = start
    while day < end:
        yield day
        day += timedelta(days=1)


def _parse_create_time(value: str) -> datetime:
    text = str(value).strip()
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _to_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise BinanceVisionSchemaError(f"invalid numeric metrics value: {value!r}") from exc
    if not math.isfinite(parsed):
        raise BinanceVisionSchemaError(f"invalid numeric metrics value: {value!r}")
    return parsed


if __name__ == "__main__":
    main()
