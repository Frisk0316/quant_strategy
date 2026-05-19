from __future__ import annotations

import pytest
import pandas as pd

from scripts.analyze_cme_gaps import (
    detect_weekend_gaps,
    simulate_reverse_gap_trades,
    summarize_gaps,
    summarize_trades,
    time_to_fill_distribution,
    trade_holding_distribution,
)


def test_detect_weekend_gaps_and_fill_probability():
    bars = pd.DataFrame({
        "ts": pd.to_datetime([
            "2024-01-05",
            "2024-01-08",
            "2024-01-09",
            "2024-01-12",
            "2024-01-15",
        ], utc=True),
        "open": [100.0, 103.0, 101.0, 101.0, 98.0],
        "high": [101.0, 104.0, 102.0, 102.0, 99.0],
        "low": [99.0, 102.0, 99.5, 100.0, 96.0],
        "close": [100.0, 101.0, 101.0, 100.0, 99.0],
    })

    gaps = detect_weekend_gaps(bars, min_gap_bps=10, max_fill_days=2, allow_direction="both")
    summary = summarize_gaps(gaps, thresholds=(10, 200))

    assert len(gaps) == 2
    assert gaps.iloc[0]["direction"] == "up"
    assert bool(gaps.iloc[0]["filled"]) is True
    assert gaps.iloc[1]["direction"] == "down"
    assert bool(gaps.iloc[1]["filled"]) is False
    assert summary["gap_count"] == 2
    assert summary["fill_probability"] == 0.5
    assert summary["thresholds"][1]["gap_count"] == 2
    dist = time_to_fill_distribution(gaps, buckets_days=(1, 2))
    assert dist["filled_count"] == 1
    assert dist["unfilled_count"] == 1
    assert dist["buckets"][0]["count"] == 1


def test_detect_weekend_gaps_includes_friday_to_tuesday_holiday_reopen():
    bars = pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-12", "2024-01-16"], utc=True),
        "open": [100.0, 97.0],
        "high": [101.0, 99.0],
        "low": [99.0, 96.0],
        "close": [100.0, 98.0],
    })

    gaps = detect_weekend_gaps(bars, min_gap_bps=10, max_fill_days=1)

    assert len(gaps) == 1
    assert gaps.iloc[0]["direction"] == "down"


def test_detect_weekend_gaps_excludes_roll_day_artifacts_by_default():
    bars = pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-05", "2024-01-08"], utc=True),
        "open": [100.0, 110.0],
        "high": [101.0, 111.0],
        "low": [99.0, 109.0],
        "close": [100.0, 110.0],
        "is_roll_day": [False, True],
    })

    gaps = detect_weekend_gaps(bars, min_gap_bps=10, max_fill_days=1, allow_direction="both")
    included = detect_weekend_gaps(
        bars,
        min_gap_bps=10,
        max_fill_days=1,
        allow_direction="both",
        exclude_roll_days=False,
    )

    assert gaps.empty
    assert len(included) == 1
    assert bool(included.iloc[0]["is_roll_day"]) is True


def test_simulate_reverse_gap_trades_uses_okx_anchor_target_and_reports_metrics():
    gaps = pd.DataFrame({
        "open_at": ["2024-01-08T00:00:00+00:00"],
        "direction": ["up"],
        "gap_bps": [200.0],
        "filled": [True],
        "time_to_fill_days": [1.0],
        "is_roll_day": [False],
    })
    okx = pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-08 00:00Z", "2024-01-08 01:00Z"]),
        "open": [100.0, 99.0],
        "high": [101.0, 99.5],
        "low": [99.0, 97.5],
        "close": [99.0, 98.0],
    })

    trades = simulate_reverse_gap_trades(
        gaps,
        okx,
        max_hold_days=5,
        allow_direction="both",
        fee_bps_per_side=0,
        slippage_bps_per_side=0,
    )
    metrics = summarize_trades(trades)

    assert len(trades) == 1
    assert trades.iloc[0]["side"] == "short"
    assert trades.iloc[0]["target_price"] == pytest.approx(98.0)
    assert trades.iloc[0]["exit_reason"] == "target_fill"
    assert trades.iloc[0]["net_return"] == pytest.approx(0.02)
    assert metrics["trade_count"] == 1
    assert metrics["total_return"] == pytest.approx(0.02)
    holding = trade_holding_distribution(trades, buckets_hours=(1, 6))
    assert holding["trade_count"] == 1
    assert holding["buckets"][0]["count"] == 1


def test_simulate_reverse_gap_trades_records_stop_loss_exits():
    gaps = pd.DataFrame({
        "open_at": ["2024-01-08T00:00:00+00:00"],
        "direction": ["up"],
        "gap_bps": [100.0],
        "filled": [False],
        "time_to_fill_days": [None],
        "is_roll_day": [False],
    })
    okx = pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-08 00:00Z", "2024-01-08 01:00Z"]),
        "open": [100.0, 101.0],
        "high": [100.5, 101.6],
        "low": [99.2, 100.8],
        "close": [100.2, 101.4],
    })

    trades = simulate_reverse_gap_trades(
        gaps,
        okx,
        max_hold_days=1,
        stop_loss_bps_mult=1.5,
        allow_direction="both",
        fee_bps_per_side=0,
        slippage_bps_per_side=0,
    )
    metrics = summarize_trades(trades)

    assert len(trades) == 1
    assert trades.iloc[0]["side"] == "short"
    assert trades.iloc[0]["stop_price"] == pytest.approx(101.5)
    assert trades.iloc[0]["exit_reason"] == "stop_loss"
    assert trades.iloc[0]["net_return"] == pytest.approx(-0.015)
    assert metrics["stop_loss_trade_count"] == 1


def test_simulate_reverse_gap_trades_drops_above_max_gap_bps():
    gaps = pd.DataFrame({
        "open_at": ["2024-01-08T00:00:00+00:00"],
        "direction": ["up"],
        "gap_bps": [300.0],
        "filled": [False],
        "time_to_fill_days": [None],
        "is_roll_day": [False],
    })
    okx = pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-08 00:00Z"]),
        "open": [100.0],
        "high": [101.0],
        "low": [99.0],
        "close": [100.0],
    })

    trades = simulate_reverse_gap_trades(gaps, okx, max_gap_bps=200.0)

    assert trades.empty


def test_simulate_reverse_gap_trades_long_only_excludes_short_side():
    gaps = pd.DataFrame({
        "open_at": ["2024-01-08T00:00:00+00:00"],
        "direction": ["up"],
        "gap_bps": [100.0],
        "filled": [False],
        "time_to_fill_days": [None],
        "is_roll_day": [False],
    })
    okx = pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-08 00:00Z"]),
        "open": [100.0],
        "high": [101.0],
        "low": [99.0],
        "close": [100.0],
    })

    trades = simulate_reverse_gap_trades(gaps, okx, allow_direction="long_only")

    assert trades.empty


def test_detect_weekend_gaps_applies_min_and_max_gap_filters():
    bars = pd.DataFrame({
        "ts": pd.to_datetime([
            "2024-01-05",
            "2024-01-08",
            "2024-01-12",
            "2024-01-15",
            "2024-01-19",
            "2024-01-22",
        ], utc=True),
        "open": [100.0, 100.1, 101.0, 104.0, 104.0, 109.2],
        "high": [101.0, 101.0, 102.0, 105.0, 105.0, 110.0],
        "low": [99.0, 99.0, 100.0, 103.0, 103.0, 108.0],
        "close": [100.0, 101.0, 101.0, 104.0, 104.0, 109.0],
    })

    gaps = detect_weekend_gaps(
        bars,
        min_gap_bps=25.0,
        max_gap_bps=400.0,
        max_fill_days=1,
        allow_direction="both",
    )

    assert len(gaps) == 1
    assert gaps.iloc[0]["open_at"] == "2024-01-15T00:00:00+00:00"


def test_detect_weekend_gaps_long_only_excludes_up_gaps():
    bars = pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-05", "2024-01-08"], utc=True),
        "open": [100.0, 103.0],
        "high": [101.0, 104.0],
        "low": [99.0, 102.0],
        "close": [100.0, 103.0],
    })

    gaps = detect_weekend_gaps(
        bars,
        min_gap_bps=10,
        max_fill_days=1,
        allow_direction="long_only",
    )

    assert gaps.empty


def test_simulate_reverse_gap_trades_default_excludes_short_side():
    gaps = pd.DataFrame({
        "open_at": [
            "2024-01-08T00:00:00+00:00",
            "2024-01-15T00:00:00+00:00",
        ],
        "direction": ["up", "down"],
        "gap_bps": [100.0, 100.0],
        "filled": [False, False],
        "time_to_fill_days": [None, None],
        "is_roll_day": [False, False],
    })
    okx = pd.DataFrame({
        "ts": pd.to_datetime(["2024-01-08 00:00Z", "2024-01-15 00:00Z"]),
        "open": [100.0, 100.0],
        "high": [101.0, 101.0],
        "low": [99.0, 99.0],
        "close": [100.0, 100.0],
    })

    trades = simulate_reverse_gap_trades(
        gaps,
        okx,
        max_hold_days=1,
        fee_bps_per_side=0,
        slippage_bps_per_side=0,
    )

    assert len(trades) == 1
    assert set(trades["side"]) == {"long"}
