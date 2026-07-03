from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtesting.turtle_backtest import (
    TurtleParams,
    calc_unit_size,
    expand_turtle_grid,
    max_consecutive,
    run_turtle_backtest,
    turtle_metric_row,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "turtle"
INT_COLUMNS = [
    "s1_units",
    "s2_units",
    "buy_action",
    "sell_action",
    "total_units",
    "cumulative_win_count",
    "cumulative_loss_count",
]
FLOAT_COLUMNS = [
    "profit",
    "equity",
    "money_in_hand",
    "cumulative_profit",
    "whole_asset",
    "s1_position",
    "s2_position",
    "s1_stop_loss",
    "s2_stop_loss",
    "realized_pnl",
]


def _daily(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.mark.parametrize(
    ("expected_file", "params"),
    [
        ("expected_default.csv", TurtleParams()),
        (
            "expected_stress.csv",
            TurtleParams(both_sys_unit_limit=6, own_capital=10_000.0, invest_pct=0.25),
        ),
    ],
)
def test_turtle_matches_golden_fixture(expected_file: str, params: TurtleParams) -> None:
    daily = pd.read_csv(FIXTURE_DIR / "daily_ohlc.csv")
    expected = pd.read_csv(FIXTURE_DIR / expected_file, parse_dates=["date"])

    actual = run_turtle_backtest(daily, params).frame.loc[:, expected.columns].copy()

    pd.testing.assert_series_equal(actual["date"], expected["date"], check_names=False)
    pd.testing.assert_frame_equal(
        actual[INT_COLUMNS].astype("int64"),
        expected[INT_COLUMNS].astype("int64"),
        check_dtype=True,
    )
    np.testing.assert_allclose(
        actual[FLOAT_COLUMNS].to_numpy(dtype=float),
        expected[FLOAT_COLUMNS].to_numpy(dtype=float),
        rtol=1e-9,
        atol=1e-9,
    )


def test_unit_size_matches_reference_flooring() -> None:
    assert calc_unit_size(own_capital=50_000, atr=100, close=50_000, invest_pct=0.01, min_position=0.0001) == pytest.approx(0.0099)


def test_turtle_uses_shifted_rolling_entry_threshold() -> None:
    df = _daily([
        ("2024-01-01", 10, 10, 9, 10),
        ("2024-01-02", 10, 10, 9, 10),
        ("2024-01-03", 10, 10, 9, 10),
        ("2024-01-04", 10, 11, 9, 10),
        ("2024-01-05", 10, 11.5, 9, 10),
    ])
    result = run_turtle_backtest(
        df,
        TurtleParams(
            enter_term_sys1=3,
            enter_term_sys2=4,
            leave_term_sys1=2,
            leave_term_sys2=3,
            own_capital=1_000,
            invest_pct=0.5,
            min_position=0.0001,
            fee=0.0,
            atr_period=2,
        ),
    )

    row = result.frame.iloc[-1]
    assert row["last_enter_max_sys1"] == pytest.approx(11.0)
    assert row["last_enter_max_sys2"] == pytest.approx(11.0)
    assert row["s1_buy"] == 1
    assert row["s2_buy"] == 1


def test_cash_gate_is_strict_and_counts_skips() -> None:
    df = _daily([
        ("2024-01-01", 10, 10, 9, 10),
        ("2024-01-02", 10, 10, 9, 10),
        ("2024-01-03", 10, 10, 9, 10),
        ("2024-01-04", 10, 11, 9, 10),
        ("2024-01-05", 10, 12, 9, 10),
    ])
    result = run_turtle_backtest(
        df,
        TurtleParams(
            enter_term_sys1=3,
            enter_term_sys2=4,
            leave_term_sys1=2,
            leave_term_sys2=3,
            own_capital=1,
            invest_pct=1.0,
            min_position=0.0001,
            fee=0.9,
            atr_period=2,
        ),
    )

    assert result.metrics["cash_skip_count"] > 0
    assert result.frame["buy_action"].sum() == 0
    assert result.frame.iloc[-1]["money_in_hand"] == pytest.approx(1.0)


def test_s1_skip_after_winning_trade_skips_next_breakout_only() -> None:
    df = _daily([
        ("2024-01-01", 10, 10, 9, 10),
        ("2024-01-02", 10, 10, 9, 10),
        ("2024-01-03", 10, 10, 9, 10),
        ("2024-01-04", 10, 11, 9, 10),
        ("2024-01-05", 12, 12, 11, 12),
        ("2024-01-06", 12, 14, 8, 14),
        ("2024-01-07", 14, 15, 11, 14),
        ("2024-01-08", 14, 16, 11, 14),
    ])
    result = run_turtle_backtest(
        df,
        TurtleParams(
            enter_term_sys1=3,
            enter_term_sys2=4,
            leave_term_sys1=2,
            leave_term_sys2=3,
            own_capital=10_000,
            invest_pct=0.1,
            min_position=0.0001,
            fee=0.0,
            atr_period=2,
        ),
    )

    frame = result.frame
    assert frame["s1_sell"].sum() == 1
    assert frame["s1_win"].sum() == 1
    # The first breakout after a winning S1 exit is consumed by skip_next.
    assert frame.loc[frame["date"] == pd.Timestamp("2024-01-07"), "s1_buy"].iloc[0] == 0
    assert frame.loc[frame["date"] == pd.Timestamp("2024-01-08"), "s1_buy"].iloc[0] == 1


def test_no_forced_end_liquidation_final_equity_marks_open_position() -> None:
    df = _daily([
        ("2024-01-01", 10, 10, 9, 10),
        ("2024-01-02", 10, 10, 9, 10),
        ("2024-01-03", 10, 10, 9, 10),
        ("2024-01-04", 10, 11, 9, 10),
        ("2024-01-05", 10, 12, 9, 10),
    ])
    result = run_turtle_backtest(
        df,
        TurtleParams(
            enter_term_sys1=3,
            enter_term_sys2=4,
            leave_term_sys1=2,
            leave_term_sys2=3,
            own_capital=1_000,
            invest_pct=0.5,
            min_position=0.0001,
            fee=0.0,
            atr_period=2,
        ),
    )

    last = result.frame.iloc[-1]
    assert last["total_units"] == 2
    assert last["sell_action"] == 0
    assert last["equity"] == pytest.approx(last["money_in_hand"] + last["s1_position_value"] + last["s2_position_value"])


def test_metric_row_uses_reference_columns_and_consecutive_outcomes() -> None:
    df = _daily([
        ("2024-01-01", 10, 10, 9, 10),
        ("2024-01-02", 10, 10, 9, 10),
        ("2024-01-03", 10, 10, 9, 10),
        ("2024-01-04", 10, 11, 9, 10),
        ("2024-01-05", 12, 12, 11, 12),
        ("2024-01-06", 12, 13, 8, 12),
        ("2024-01-07", 12, 14, 11, 12),
        ("2024-01-08", 12, 15, 8, 12),
    ])
    params = TurtleParams(
        enter_term_sys1=3,
        enter_term_sys2=4,
        leave_term_sys1=2,
        leave_term_sys2=3,
        own_capital=10_000,
        invest_pct=0.1,
        min_position=0.0001,
        fee=0.0,
        atr_period=2,
    )
    result = run_turtle_backtest(df, params)
    row = turtle_metric_row(result.frame, params)

    assert {"win_rate", "profit_loss_ratio", "expectancy", "mdd", "final_equity"} <= set(row)
    assert row["final_equity"] == pytest.approx(result.frame.iloc[-1]["equity"])
    assert max_consecutive([1, 1, 0, 1], 1) == 2
    assert math.isfinite(row["mdd"])


def test_expand_turtle_grid_validates_reference_constraints() -> None:
    combos, skipped = expand_turtle_grid(
        {
            "enter_term_sys1": "5~7",
            "enter_term_sys2": 8,
            "leave_term_sys1": 5,
            "leave_term_sys2": 6,
        }
    )

    assert combos == [
        {"enter_term_sys1": 6, "enter_term_sys2": 8, "leave_term_sys1": 5, "leave_term_sys2": 6},
        {"enter_term_sys1": 7, "enter_term_sys2": 8, "leave_term_sys1": 5, "leave_term_sys2": 6},
    ]
    assert skipped


def test_invest_pct_axis_requires_fixed_window_params() -> None:
    with pytest.raises(ValueError, match="invest_pct axis requires all 4 window params fixed"):
        expand_turtle_grid(
            {
                "enter_term_sys1": "5~7",
                "enter_term_sys2": 8,
                "leave_term_sys1": 5,
                "leave_term_sys2": 6,
                "invest_pct": "1~10:1",
            }
        )


def test_invest_pct_axis_sweep_summary_is_json_serializable() -> None:
    """Regression: equity_curves rows carried pandas Timestamps, which crashed
    the sweep job's json.dumps of summary.json (found by the 2026-07-04
    DB-backed API smoke)."""
    import json

    from backtesting.turtle_backtest import run_turtle_sweep

    df = _daily([
        (f"2024-01-{day:02d}", 10, 10 + (0.5 if day > 9 else 0), 9, 10)
        for day in range(1, 13)
    ])
    summary = run_turtle_sweep(
        df,
        {
            "enter_term_sys1": 6,
            "enter_term_sys2": 8,
            "leave_term_sys1": 5,
            "leave_term_sys2": 6,
            "invest_pct": "1~3:1",
        },
        TurtleParams(
            enter_term_sys1=6,
            enter_term_sys2=8,
            leave_term_sys1=5,
            leave_term_sys2=6,
            own_capital=1_000,
            invest_pct=0.5,
            min_position=0.0001,
            fee=0.0,
            atr_period=2,
        ),
    )

    encoded = json.dumps(summary, allow_nan=True)
    assert '"equity_curves"' in encoded
    assert summary["completed_count"] == 3
