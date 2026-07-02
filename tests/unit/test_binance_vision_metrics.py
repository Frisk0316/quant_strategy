from __future__ import annotations

import zipfile
from datetime import date, datetime, timezone
from io import BytesIO

import pytest

from scripts.market_data.download_binance_vision_metrics import (
    BinanceVisionSchemaError,
    LocalVisionMetricsSource,
    build_parser,
    ingest_symbol,
    parse_metrics_zip,
    validate_btc_schema,
)


HEADER = (
    "create_time,symbol,sum_open_interest,sum_open_interest_value,"
    "count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
    "count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
)


def _zip_bytes(csv_text: str, name: str = "BTCUSDT-metrics-2024-01-01.csv") -> bytes:
    payload = BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, csv_text)
    return payload.getvalue()


def _write_zip(root, symbol: str, day: date, csv_text: str) -> None:
    path = root / f"{symbol}-metrics-{day.isoformat()}.zip"
    path.write_bytes(_zip_bytes(csv_text, name=f"{symbol}-metrics-{day.isoformat()}.csv"))


def test_parse_metrics_zip_normalizes_vision_rows():
    csv_text = HEADER + (
        "2024-01-01 00:00:00,BTCUSDT,100.5,1234567.89,1.1,1.2,1.3,1.4\n"
        "2024-01-01 00:05:00,BTCUSDT,101.5,2234567.89,1.1,1.2,1.3,1.4\n"
    )

    rows = parse_metrics_zip(
        _zip_bytes(csv_text),
        expected_symbol="BTCUSDT",
        source_url="file://fixture/BTCUSDT-metrics-2024-01-01.zip",
    )

    assert len(rows) == 2
    assert rows[0]["observed_at"] == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert rows[0]["published_at"] == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert rows[0]["value_num"] == 1234567.89
    assert rows[0]["fields"]["unit"] == "USDT_notional"
    assert rows[0]["fields"]["provenance"] == "binance_vision_metrics"
    assert rows[0]["fields"]["source_value_field"] == "sum_open_interest_value"
    assert rows[0]["fields"]["open_interest_contracts"] == 100.5
    assert rows[0]["raw_payload"]["source_url"].endswith("BTCUSDT-metrics-2024-01-01.zip")


def test_parse_metrics_zip_fails_closed_on_schema_mismatch():
    bad_csv = (
        "create_time,symbol,sum_open_interest\n"
        "2024-01-01 00:00:00,BTCUSDT,100.5\n"
    )

    with pytest.raises(BinanceVisionSchemaError, match="schema"):
        parse_metrics_zip(_zip_bytes(bad_csv), expected_symbol="BTCUSDT", source_url="fixture")


def test_validate_btc_schema_fails_when_one_day_btc_zip_is_unavailable(tmp_path):
    source = LocalVisionMetricsSource(tmp_path)

    with pytest.raises(BinanceVisionSchemaError, match="BTCUSDT schema"):
        validate_btc_schema(source, date(2024, 1, 1))


def test_build_parser_accepts_minimal_dry_run_args(tmp_path):
    args = build_parser().parse_args([
        "--start",
        "2024-01-01",
        "--end",
        "2024-01-02",
        "--source-dir",
        str(tmp_path),
        "--dry-run",
    ])

    assert args.start == "2024-01-01"
    assert args.end == "2024-01-02"
    assert args.dry_run is True


@pytest.mark.asyncio
async def test_ingest_symbol_reports_coverage_and_reruns_idempotently(tmp_path):
    _write_zip(
        tmp_path,
        "BTCUSDT",
        date(2024, 1, 1),
        HEADER + "2024-01-01 00:00:00,BTCUSDT,100.5,1234567.89,1.1,1.2,1.3,1.4\n",
    )
    _write_zip(
        tmp_path,
        "BTCUSDT",
        date(2024, 1, 3),
        HEADER + "2024-01-03 00:00:00,BTCUSDT,200.5,3234567.89,1.1,1.2,1.3,1.4\n",
    )

    class FakeStore:
        def __init__(self):
            self.datasets = []
            self.jobs = []
            self.finishes = []
            self.checkpoints = []
            self.seen = set()

        async def upsert_dataset(self, dataset_id, cfg):
            self.datasets.append((dataset_id, cfg))

        async def start_fetch_job(self, dataset_id, provider, start, end):
            self.jobs.append((dataset_id, provider, start, end))
            return f"job-{len(self.jobs)}"

        async def finish_fetch_job(self, job_id, **kwargs):
            self.finishes.append((job_id, kwargs))

        async def upsert_observations(self, dataset_id, rows):
            inserted = 0
            updated = 0
            for row in rows:
                key = (dataset_id, row["observed_at"])
                if key in self.seen:
                    updated += 1
                else:
                    self.seen.add(key)
                    inserted += 1
            return {"rows": len(rows), "inserted": inserted, "updated": updated}

        async def update_checkpoint(self, dataset_id, **kwargs):
            self.checkpoints.append((dataset_id, kwargs))

    store = FakeStore()
    source = LocalVisionMetricsSource(tmp_path)

    first = await ingest_symbol(
        store,
        source,
        symbol="BTCUSDT",
        dataset_id="oi_binance_hist_btc",
        start=date(2024, 1, 1),
        end=date(2024, 1, 4),
        dry_run=False,
    )
    second = await ingest_symbol(
        store,
        source,
        symbol="BTCUSDT",
        dataset_id="oi_binance_hist_btc",
        start=date(2024, 1, 1),
        end=date(2024, 1, 4),
        dry_run=False,
    )

    assert first["rows"] == 2
    assert first["first"] == "2024-01-01T00:00:00+00:00"
    assert first["last"] == "2024-01-03T00:00:00+00:00"
    assert first["missing_days"] == ["2024-01-02"]
    assert first["inserted"] == 2
    assert second["inserted"] == 0
    assert second["updated"] == 2
    assert store.datasets[0][0] == "oi_binance_hist_btc"
    assert store.datasets[0][1]["provider"] == "binance_vision"
    assert store.finishes[-1][1]["status"] == "success"
    assert store.checkpoints[-1] == (
        "oi_binance_hist_btc",
        {
            "direction": "backfill",
            "cursor_time": datetime(2024, 1, 3, tzinfo=timezone.utc),
            "request_count": 1,
            "row_count": 2,
            "status": "success",
        },
    )
