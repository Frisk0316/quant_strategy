import inspect

from okx_quant.data.candle_store import CandleStore
from okx_quant.data.canonical_policy import (
    canonical_conflict_where,
    should_replace_canonical,
    source_priority,
    venue_canonical_conflict_where,
)
from scripts._db_writer import _should_replace_canonical, _source_priority, _upsert_async


def test_canonical_source_priority_prefers_binance_over_okx() -> None:
    assert source_priority("binance") > source_priority("okx")
    assert _source_priority("binance") == source_priority("binance")
    assert should_replace_canonical("okx", "raw", "binance")
    assert _should_replace_canonical("okx", "raw", "binance")
    assert not should_replace_canonical("binance", "raw", "okx")


def test_canonical_source_priority_allows_gap_refresh_and_suspect_repair() -> None:
    assert should_replace_canonical("binance", "raw", "binance")
    assert should_replace_canonical("binance", "suspect", "okx")


def test_canonical_source_priority_protects_validated_and_corrected_rows() -> None:
    assert not should_replace_canonical("okx", "validated", "binance")
    assert not should_replace_canonical("okx", "corrected", "binance")
    assert should_replace_canonical("binance", "corrected", "manual")


def test_canonical_source_priority_allows_incoming_corrections() -> None:
    assert should_replace_canonical("binance", "raw", "okx", incoming_quality="corrected")
    assert should_replace_canonical("manual", "corrected", "okx", incoming_quality="corrected")


def test_canonical_store_paths_use_shared_priority_gate() -> None:
    assert "EXCLUDED.quality_status != 'raw'" in canonical_conflict_where()
    for method in (
        CandleStore.canonicalize_from_raw,
        CandleStore.canonicalize_from_market_klines,
        CandleStore.upsert_canonical_candles,
    ):
        source = inspect.getsource(method)
        assert "canonical_conflict_where()" in source
        assert "ON CONFLICT (inst_id, bar, ts) DO NOTHING" not in source


def test_raw_writers_dual_write_source_aware_canonical_without_overwriting_corrections() -> None:
    policy = venue_canonical_conflict_where()
    assert "quality_status IN ('raw', 'suspect')" in policy
    assert "IS DISTINCT FROM" in policy
    for method in (CandleStore.canonicalize_from_raw, _upsert_async):
        source = inspect.getsource(method)
        assert "INSERT INTO venue_canonical_candles" in source
        assert "venue_canonical_conflict_where()" in source
