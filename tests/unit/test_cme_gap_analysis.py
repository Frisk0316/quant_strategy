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

    gaps = detect_weekend_gaps(bars, min_gap_bps=10, max_fill_days=2)
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

    gaps = detect_weekend_gaps(bars, min_gap_bps=10, max_fill_days=1)
    included = detect_weekend_gaps(bars, min_gap_bps=10, max_fill_days=1, exclude_roll_days=False)

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
