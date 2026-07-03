from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from scripts.market_data.backfill_universe_funding import (
    EIGHT_HOURS_MS,
    backfill_universe_funding,
    build_coverage_report,
    fetch_symbol_funding,
    load_eligible_symbols,
    rows_to_frame,
)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def test_load_eligible_symbols_returns_union_in_window(tmp_path):
    membership = pd.DataFrame(
        [
            {"date": "2024-01-01", "symbol": "BTC-USDT-SWAP", "eligible": True},
            {"date": "2024-01-02", "symbol": "ETH-USDT-SWAP", "eligible": True},
            {"date": "2024-01-02", "symbol": "SOL-USDT-SWAP", "eligible": False},
            {"date": "2024-02-01", "symbol": "DOGE-USDT-SWAP", "eligible": True},
        ]
    )
    path = tmp_path / "universe_membership.parquet"
    membership.to_parquet(path, index=False)

    symbols = load_eligible_symbols(path, start=_dt("2024-01-01"), end=_dt("2024-01-31"))

    assert symbols == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]


def test_fetch_symbol_funding_paginates_and_reports_internal_gaps():
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int, int, int]] = []
            self.rows = [
                {"ts_ms": 0, "funding_rate": 0.0001, "mark_price": 100.0},
                {"ts_ms": EIGHT_HOURS_MS, "funding_rate": 0.0002, "mark_price": 101.0},
                {"ts_ms": 3 * EIGHT_HOURS_MS, "funding_rate": -0.0001, "mark_price": 99.0},
            ]

        def get_funding_rates(self, symbol: str, *, start_ms: int, end_ms: int, limit: int):
            self.calls.append((symbol, start_ms, end_ms, limit))
            return [row for row in self.rows if start_ms <= row["ts_ms"] <= end_ms][:limit]

    client = FakeClient()

    rows = fetch_symbol_funding(
        client,
        "BTC-USDT-SWAP",
        start=_dt("1970-01-01"),
        end=_dt("1970-01-02 01:00:00"),
        limit=2,
    )
    frame = rows_to_frame(rows)
    report = build_coverage_report({"BTC-USDT-SWAP": rows})

    assert [call[0] for call in client.calls] == ["BTCUSDT", "BTCUSDT"]
    assert [row["inst_id"] for row in rows] == ["BTC-USDT-SWAP"] * 3
    assert list(frame["source"].unique()) == ["binance"]
    assert report[0]["rows"] == 3
    assert report[0]["first_ts"] == "1970-01-01T00:00:00+00:00"
    assert report[0]["last_ts"] == "1970-01-02T00:00:00+00:00"
    assert report[0]["gap_count"] == 1
    assert report[0]["stale_intervals"][0]["gap_hours"] == 16.0


def test_backfill_universe_funding_writes_parquet_and_skips_db_without_dsn(tmp_path):
    class FakeClient:
        def get_funding_rates(self, symbol: str, *, start_ms: int, end_ms: int, limit: int):
            return [{"ts_ms": start_ms, "funding_rate": 0.0001, "mark_price": 100.0}]

    membership_path = tmp_path / "universe_membership.parquet"
    pd.DataFrame(
        [{"date": "2024-01-01", "symbol": "BTC-USDT-SWAP", "eligible": True}]
    ).to_parquet(membership_path, index=False)

    summary = backfill_universe_funding(
        membership_path=membership_path,
        start=_dt("2024-01-01"),
        end=_dt("2024-01-02"),
        parquet_path=tmp_path / "funding.parquet",
        report_path=tmp_path / "coverage.json",
        dsn=None,
        client=FakeClient(),
        store_factory=lambda _dsn: (_ for _ in ()).throw(AssertionError("store used")),
        stage2_runner=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("stage2 used")),
    )

    assert summary["db"]["status"] == "skipped"
    assert summary["stage2"]["status"] == "skipped"
    assert (tmp_path / "funding.parquet").exists()
    assert (tmp_path / "coverage.json").exists()
