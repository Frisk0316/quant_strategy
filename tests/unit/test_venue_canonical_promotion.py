import inspect
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from backtesting.pipeline_stage2_registry import _fetch_venue_coverage
from okx_quant.data.candle_store import CandleStore
from scripts import promote_okx_canonical_1m as promotion
from scripts import verify_okx_1m_backfill as verifier


def test_migration_is_additive_and_keeps_resolved_identity_and_caggs_unchanged():
    root = Path(__file__).resolve().parents[2]
    sql = (root / "src/okx_quant/data/migrations/004_venue_canonical_candles.sql").read_text(
        encoding="utf-8"
    )

    assert "ON venue_canonical_candles (source_primary, inst_id, bar, ts)" in sql
    assert "CREATE OR REPLACE VIEW canonical_candles_by_source" in sql
    assert "FROM canonical_candles c\nUNION ALL" in sql
    assert "AND c.source_primary = v.source_primary" in sql
    assert "ALTER TABLE canonical_candles" not in sql
    assert "canonical_candles_5m" not in sql


@pytest.mark.asyncio
async def test_raw_promotion_writes_venue_layer_before_resolved_layer():
    class Pool:
        def __init__(self):
            self.calls = []

        async def fetchval(self, sql, *params):
            self.calls.append((sql, params))
            return 2 if "INSERT INTO venue_canonical_candles" in sql else 0

    pool = Pool()
    result = await CandleStore(pool).canonicalize_from_raw(
        "okx",
        "BTC-USDT-SWAP",
        "1m",
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    assert result == {"promoted": 0, "venue_promoted": 2}
    assert "INSERT INTO venue_canonical_candles" in pool.calls[0][0]
    assert "ON CONFLICT (source_primary, inst_id, bar, ts)" in pool.calls[0][0]
    assert "INSERT INTO canonical_candles" in pool.calls[1][0]
    assert pool.calls[0][1] == pool.calls[1][1]


def test_xvenue_stage2_reads_only_the_source_aware_view():
    source = inspect.getsource(_fetch_venue_coverage)
    assert source.count("canonical_candles_by_source") == 4
    assert "FROM canonical_candles\n" not in source


@pytest.mark.asyncio
async def test_promotion_defaults_keep_the_frozen_window():
    class Connection:
        def __init__(self):
            self.calls = []

        async def fetch(self, _sql, *_params):
            return [
                {"inst_id": symbol, "raw_rows": 1, "resolved_guard_mismatch": False}
                for symbol in promotion.SYMBOLS
            ]

        async def fetchval(self, sql, *params):
            self.calls.append((sql, params))
            return 1 if "INSERT INTO venue_canonical_candles" in sql else 0

    conn = Connection()
    rows, preflight = await promotion._promote_on_connection(
        conn,
        promotion.START,
        promotion.END_EXCLUSIVE,
    )
    calls = [
        call for call in conn.calls if "INSERT INTO venue_canonical_candles" in call[0]
    ]

    assert all(row == {"promoted": 0, "venue_promoted": 1} for row in rows.values())
    assert all(not row["resolved_guard_mismatch"] for row in preflight.values())
    assert [params[1] for _, params in calls] == list(promotion.SYMBOLS)
    assert all(call[3] == promotion.START and call[4] == promotion.END_EXCLUSIVE for _, call in calls)


def test_promotion_cli_accepts_wide_window_without_changing_defaults(monkeypatch):
    windows = []

    async def fake_schema(_dsn):
        return None

    async def fake_promote(_dsn, start, end):
        windows.append((start, end))
        return {"status": "COMPLETE"}

    monkeypatch.setattr(promotion, "resolve_dsn", lambda explicit=None: explicit)
    monkeypatch.setattr(promotion, "apply_schema", fake_schema)
    monkeypatch.setattr(promotion, "promote", fake_promote)

    assert promotion.main(["--dsn", "postgresql://unit"]) == 0
    assert promotion.main(
        [
            "--dsn",
            "postgresql://unit",
            "--start",
            "2020-01-01",
            "--end",
            "2024-01-01",
        ]
    ) == 0
    assert windows == [
        (promotion.START, promotion.END_EXCLUSIVE),
        (
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
    ]


def test_promotion_rejects_an_empty_or_reversed_window():
    with pytest.raises(SystemExit) as exc:
        promotion.main(["--start", "2024-01-01", "--end", "2024-01-01"])
    assert exc.value.code == 2


@pytest.mark.asyncio
async def test_promotion_fails_before_resolved_rows_can_change():
    class Connection:
        async def fetch(self, _sql, *_params):
            return [
                {
                    "inst_id": promotion.SYMBOLS[0],
                    "raw_rows": 1,
                    "resolved_guard_mismatch": True,
                }
            ]

        async def fetchval(self, *_args):
            raise AssertionError("promotion ran after unsafe resolved preflight")

    with pytest.raises(RuntimeError, match="resolved canonical preflight failed"):
        await promotion._promote_on_connection(
            Connection(),
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_promotion_rolls_back_if_resolved_changes_after_preflight():
    class Connection:
        async def fetch(self, _sql, *_params):
            return [
                {"inst_id": symbol, "raw_rows": 1, "resolved_guard_mismatch": False}
                for symbol in promotion.SYMBOLS
            ]

        async def fetchval(self, sql, *_params):
            return 1 if "INSERT INTO canonical_candles" in sql else 0

    with pytest.raises(RuntimeError, match="resolved canonical mutation detected"):
        await promotion._promote_on_connection(
            Connection(),
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


def test_verifier_compresses_raw_missing_days_without_substitution():
    rows = [
        {"inst_id": "BTC-USDT-SWAP", "day": date(2020, 1, 1), "row_count": 1439},
        {"inst_id": "BTC-USDT-SWAP", "day": date(2020, 1, 2), "row_count": 1440},
    ]
    gaps = verifier._raw_gap_ranges(
        rows,
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        datetime(2020, 1, 3, tzinfo=timezone.utc),
    )

    assert gaps["BTC-USDT-SWAP"] == [
        {
            "start": "2020-01-01",
            "end_exclusive": "2020-01-02",
            "expected_rows": 1440,
            "observed_rows": 1439,
            "missing_rows": 1,
        }
    ]
    assert gaps["ETH-USDT-SWAP"] == [
        {
            "start": "2020-01-01",
            "end_exclusive": "2020-01-03",
            "expected_rows": 2880,
            "observed_rows": 0,
            "missing_rows": 2880,
        }
    ]


def test_verifier_cli_passes_the_full_range(monkeypatch):
    seen = {}

    async def fake_verify(_dsn, start, end):
        seen["window"] = (start, end)
        return {"status": "PASS", "symbols": {}}

    monkeypatch.setattr(verifier, "resolve_dsn", lambda explicit=None: explicit)
    monkeypatch.setattr(verifier, "verify", fake_verify)

    assert verifier.main(
        [
            "--dsn",
            "postgresql://unit",
            "--start",
            "2020-01-01",
            "--end",
            "2026-06-17",
        ]
    ) == 0
    assert seen["window"] == (
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 6, 17, tzinfo=timezone.utc),
    )
