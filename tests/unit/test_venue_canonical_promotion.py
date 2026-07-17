import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backtesting.pipeline_stage2_registry import _fetch_venue_coverage
from okx_quant.data.candle_store import CandleStore
from scripts import promote_okx_canonical_1m as promotion


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
async def test_promotion_command_has_fixed_authorized_scope(monkeypatch):
    calls = []

    class Store:
        @classmethod
        async def from_dsn(cls, dsn, **kwargs):
            assert dsn == "postgresql://example"
            return cls()

        async def canonicalize_from_raw(self, source, symbol, bar, start, end):
            calls.append((source, symbol, bar, start, end))
            return {"promoted": 0, "venue_promoted": 1}

        async def close(self):
            return None

    monkeypatch.setattr(promotion, "CandleStore", Store)

    report = await promotion.promote("postgresql://example")

    assert report["status"] == "COMPLETE"
    assert [call[1] for call in calls] == list(promotion.SYMBOLS)
    assert all(call[0] == "okx" and call[2] == "1m" for call in calls)
    assert all(call[3] == promotion.START and call[4] == promotion.END_EXCLUSIVE for call in calls)
