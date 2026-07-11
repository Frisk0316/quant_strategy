from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtesting.turtle_backtest import (
    SWEEP_COLUMNS,
    TurtleParams,
    calc_unit_size,
    expand_turtle_grid,
    max_consecutive,
    render_surface_html,
    run_turtle_backtest,
    run_turtle_sweep,
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
SWEEP_KEY_COLUMNS = ("enter_term_sys1", "enter_term_sys2", "leave_term_sys1", "leave_term_sys2")
SWEEP_INT_COLUMNS = {
    *SWEEP_KEY_COLUMNS,
    "s1_max_consec_win",
    "s1_max_consec_loss",
    "s2_max_consec_win",
    "s2_max_consec_loss",
    "overall_max_consec_win",
    "overall_max_consec_loss",
    "final_win_count",
    "final_loss_count",
}
REFERENCE_SWEEP_GOLDEN = [
    {
        "enter_term_sys1": 6,
        "enter_term_sys2": 55,
        "leave_term_sys1": 5,
        "leave_term_sys2": 20,
        "win_rate": 0.3111111111111111,
        "profit_loss_ratio": 3.307607667377739,
        "expectancy": 52.33509858955648,
        "mdd": -0.2271591158788672,
        "final_whole_asset": 2417.8587761500344,
        "positive_rate": 0.9365256124721604,
        "median_asset": 3006.7841782400283,
        "mean_asset": 2770.457313736273,
        "s1_return_median": -0.028590779758799763,
        "s1_return_mean": -0.00838338820546833,
        "s2_return_median": -0.025811042750071993,
        "s2_return_mean": 0.009706604092898684,
        "s1_max_consec_win": 3,
        "s1_max_consec_loss": 9,
        "s2_max_consec_win": 1,
        "s2_max_consec_loss": 4,
        "overall_max_consec_win": 4,
        "overall_max_consec_loss": 10,
        "final_win_count": 14,
        "final_loss_count": 31,
        "min_equity": 9985.478109759999,
        "min_realized_pnl": 0.0,
        "final_equity": 12417.858776150042,
    },
    {
        "enter_term_sys1": 20,
        "enter_term_sys2": 55,
        "leave_term_sys1": 10,
        "leave_term_sys2": 20,
        "win_rate": 0.2692307692307692,
        "profit_loss_ratio": 4.879156922098342,
        "expectancy": 112.15802453769314,
        "mdd": -0.2211990768316672,
        "final_whole_asset": 2916.1086379800213,
        "positive_rate": 0.9365256124721604,
        "median_asset": 3120.3000222700202,
        "mean_asset": 2842.8492893970006,
        "s1_return_median": -0.029730825845528382,
        "s1_return_mean": 0.014084061364625004,
        "s2_return_median": -0.029190956629576166,
        "s2_return_mean": -0.008777522686102497,
        "s1_max_consec_win": 2,
        "s1_max_consec_loss": 7,
        "s2_max_consec_win": 1,
        "s2_max_consec_loss": 6,
        "overall_max_consec_win": 2,
        "overall_max_consec_loss": 8,
        "final_win_count": 7,
        "final_loss_count": 19,
        "min_equity": 9985.478109759999,
        "min_realized_pnl": 0.0,
        "final_equity": 12916.108637980025,
    },
    {
        "enter_term_sys1": 30,
        "enter_term_sys2": 55,
        "leave_term_sys1": 19,
        "leave_term_sys2": 20,
        "win_rate": 0.24,
        "profit_loss_ratio": 4.684135225616537,
        "expectancy": 73.43691352760067,
        "mdd": -0.2683728115408445,
        "final_whole_asset": 1835.9228381900148,
        "positive_rate": 0.9365256124721604,
        "median_asset": 2509.3230685900135,
        "mean_asset": 2488.3667467432792,
        "s1_return_median": -0.03957914635755195,
        "s1_return_mean": -0.001121621443428224,
        "s2_return_median": -0.033180703244246386,
        "s2_return_mean": 0.01854640937337516,
        "s1_max_consec_win": 1,
        "s1_max_consec_loss": 7,
        "s2_max_consec_win": 1,
        "s2_max_consec_loss": 5,
        "overall_max_consec_win": 1,
        "overall_max_consec_loss": 7,
        "final_win_count": 6,
        "final_loss_count": 19,
        "min_equity": 9985.478109759999,
        "min_realized_pnl": 0.0,
        "final_equity": 11835.922838190023,
    },
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


def test_sweep_metric_rows_match_direct_metric_rows_on_subgrid() -> None:
    daily = pd.read_csv(FIXTURE_DIR / "daily_ohlc.csv")
    base = TurtleParams(
        enter_term_sys1=20,
        enter_term_sys2=55,
        leave_term_sys1=10,
        leave_term_sys2=20,
        own_capital=10_000.0,
        invest_pct=0.25,
        min_position=0.0001,
        fee=0.003,
        atr_period=20,
        single_sys_unit_limit=4,
        both_sys_unit_limit=4,
    )
    spec = {
        "enter_term_sys1": "6,20,30",
        "enter_term_sys2": 55,
        "leave_term_sys1": "5,10,19",
        "leave_term_sys2": 20,
    }
    summary = run_turtle_sweep(daily, spec, base)
    actual = {
        (row["enter_term_sys1"], row["enter_term_sys2"], row["leave_term_sys1"], row["leave_term_sys2"]): row
        for row in summary["rows"]
    }

    combos, _ = expand_turtle_grid(spec)
    assert len(actual) == len(combos)
    for combo in combos:
        params = TurtleParams(**{**base.__dict__, **combo})
        expected = turtle_metric_row(run_turtle_backtest(daily, params).frame, params)
        key = (
            expected["enter_term_sys1"],
            expected["enter_term_sys2"],
            expected["leave_term_sys1"],
            expected["leave_term_sys2"],
        )
        for column in SWEEP_COLUMNS:
            assert actual[key][column] == pytest.approx(expected[column])


def test_sweep_metric_rows_match_verbatim_reference_golden_subset() -> None:
    daily = pd.read_csv(FIXTURE_DIR / "daily_ohlc.csv")
    base = TurtleParams(
        enter_term_sys1=20,
        enter_term_sys2=55,
        leave_term_sys1=10,
        leave_term_sys2=20,
        own_capital=10_000.0,
        invest_pct=0.25,
        min_position=0.0001,
        fee=0.003,
        atr_period=20,
        single_sys_unit_limit=4,
        both_sys_unit_limit=4,
    )
    summary = run_turtle_sweep(
        daily,
        {
            "enter_term_sys1": "6,20,30",
            "enter_term_sys2": 55,
            "leave_term_sys1": "5,10,19",
            "leave_term_sys2": 20,
        },
        base,
    )
    actual = {
        tuple(int(row[column]) for column in SWEEP_KEY_COLUMNS): row
        for row in summary["rows"]
    }

    for expected in REFERENCE_SWEEP_GOLDEN:
        key = tuple(int(expected[column]) for column in SWEEP_KEY_COLUMNS)
        for column in SWEEP_COLUMNS:
            if column in SWEEP_INT_COLUMNS:
                assert int(actual[key][column]) == int(expected[column])
            else:
                assert actual[key][column] == pytest.approx(expected[column], rel=1e-9, abs=1e-9)


def test_expand_turtle_grid_caps_post_filter_valid_count_for_full_reference_grid() -> None:
    combos, skipped = expand_turtle_grid(
        {
            "enter_term_sys1": "5~30",
            "enter_term_sys2": "31~60",
            "leave_term_sys1": "5~20",
            "leave_term_sys2": "5~25",
        },
        max_combinations=115_200,
    )

    assert len(combos) == 115_200
    assert len(skipped) == 146_880


def test_expand_turtle_grid_keeps_raw_candidate_guardrail_above_reference_grid() -> None:
    with pytest.raises(ValueError, match="raw candidates exceed cap"):
        expand_turtle_grid(
            {
                "enter_term_sys1": "1~100",
                "enter_term_sys2": "1~100",
                "leave_term_sys1": "1~20",
                "leave_term_sys2": "1~20",
            },
            max_combinations=200_000,
        )


def test_batched_turtle_sweep_rows_match_single_pass_bytes(tmp_path) -> None:
    daily = pd.read_csv(FIXTURE_DIR / "daily_ohlc.csv")
    base = TurtleParams(
        enter_term_sys1=20,
        enter_term_sys2=55,
        leave_term_sys1=10,
        leave_term_sys2=20,
        own_capital=10_000.0,
        invest_pct=0.25,
        min_position=0.0001,
        fee=0.003,
        atr_period=20,
        single_sys_unit_limit=4,
        both_sys_unit_limit=4,
    )
    spec = {
        "enter_term_sys1": "6,20,30",
        "enter_term_sys2": 55,
        "leave_term_sys1": "5,10,19",
        "leave_term_sys2": 20,
    }
    single_dir = tmp_path / "single"
    batched_dir = tmp_path / "batched"

    run_turtle_sweep(daily, spec, base, output_dir=single_dir, sweep_id="single")
    run_turtle_sweep(daily, spec, base, output_dir=batched_dir, sweep_id="batched", batch_size=1)

    assert (batched_dir / "rows.csv").read_text(encoding="utf-8") == (
        single_dir / "rows.csv"
    ).read_text(encoding="utf-8")


def test_turtle_sweep_resume_keeps_completed_combos_exactly_once(tmp_path) -> None:
    daily = _daily([
        (f"2024-01-{day:02d}", 10, 10 + (day / 10), 9, 10 + (day / 20))
        for day in range(1, 13)
    ])
    base = TurtleParams(
        enter_term_sys1=6,
        enter_term_sys2=8,
        leave_term_sys1=5,
        leave_term_sys2=6,
        own_capital=1_000,
        invest_pct=0.5,
        min_position=0.0001,
        fee=0.0,
        atr_period=2,
    )
    spec = {
        "enter_term_sys1": "6~7",
        "enter_term_sys2": "8~9",
        "leave_term_sys1": 5,
        "leave_term_sys2": 6,
    }
    output_dir = tmp_path / "resume"
    cancel = {"stop": False}

    def progress(update: dict[str, object]) -> None:
        if int(update.get("completed_count") or 0) >= 2:
            cancel["stop"] = True

    first = run_turtle_sweep(
        daily,
        spec,
        base,
        output_dir=output_dir,
        sweep_id="resume",
        batch_size=1,
        progress_callback=progress,
        cancel_callback=lambda: cancel["stop"],
    )
    resumed = run_turtle_sweep(
        daily,
        spec,
        base,
        output_dir=output_dir,
        sweep_id="resume",
        batch_size=1,
    )
    fresh = run_turtle_sweep(daily, spec, base)
    rows = pd.read_csv(output_dir / "rows.csv")
    keys = list(zip(rows.enter_term_sys1, rows.enter_term_sys2, rows.leave_term_sys1, rows.leave_term_sys2))

    assert first["status"] == "cancelled"
    assert resumed["completed_count"] == fresh["completed_count"]
    assert len(keys) == len(set(keys)) == fresh["completed_count"]
    with pytest.raises(ValueError, match="checkpoint grid"):
        run_turtle_sweep(
            daily,
            {**spec, "enter_term_sys2": "8~10"},
            base,
            output_dir=output_dir,
            sweep_id="resume",
            batch_size=1,
        )


def test_turtle_sweep_cancel_checks_between_combos_not_only_batches(tmp_path) -> None:
    daily = _daily([
        (f"2024-01-{day:02d}", 10, 10 + (day / 10), 9, 10 + (day / 20))
        for day in range(1, 13)
    ])
    base = TurtleParams(
        enter_term_sys1=6,
        enter_term_sys2=8,
        leave_term_sys1=5,
        leave_term_sys2=6,
        own_capital=1_000,
        invest_pct=0.5,
        min_position=0.0001,
        fee=0.0,
        atr_period=2,
    )
    calls = {"count": 0}

    def cancel_after_first_combo() -> bool:
        calls["count"] += 1
        return calls["count"] > 1

    summary = run_turtle_sweep(
        daily,
        {
            "enter_term_sys1": "6~7",
            "enter_term_sys2": "8~9",
            "leave_term_sys1": 5,
            "leave_term_sys2": 6,
        },
        base,
        output_dir=tmp_path / "cancel",
        sweep_id="cancel",
        batch_size=100,
        cancel_callback=cancel_after_first_combo,
    )

    assert summary["status"] == "cancelled"
    assert summary["completed_count"] == 1


def test_turtle_sweep_fixed_invest_pct_still_writes_surface_artifact(tmp_path) -> None:
    daily = _daily([
        (f"2024-01-{day:02d}", 10, 10 + (day / 10), 9, 10 + (day / 20))
        for day in range(1, 13)
    ])
    base = TurtleParams(
        enter_term_sys1=6,
        enter_term_sys2=8,
        leave_term_sys1=5,
        leave_term_sys2=7,
        own_capital=1_000,
        invest_pct=0.25,
        min_position=0.0001,
        fee=0.0,
        atr_period=2,
    )
    output_dir = tmp_path / "surface"

    summary = run_turtle_sweep(
        daily,
        {
            "enter_term_sys1": "6~7",
            "enter_term_sys2": 8,
            "leave_term_sys1": "5~6",
            "leave_term_sys2": 7,
            "invest_pct": "25",
        },
        base,
        output_dir=output_dir,
        sweep_id="surface",
        batch_size=1,
    )

    assert summary["artifacts"]["surface"] == "surface.html"
    assert (output_dir / "surface.html").exists()


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


def test_surface_html_includes_fixed_params_and_hovertemplate() -> None:
    rows = [
        {
            "enter_term_sys1": 6,
            "leave_term_sys1": 5,
            "mdd": -0.1,
            "win_rate": 0.5,
            "final_whole_asset": 100.0,
            "profit_loss_ratio": 1.2,
            "expectancy": 3.4,
        }
    ]

    html = render_surface_html(
        rows,
        "enter_term_sys1",
        "leave_term_sys1",
        fixed_params={"enter_term_sys2": 55, "leave_term_sys2": 20, "invest_pct": 0.25},
    )

    assert "Turtle Sweep Surface | Fixed: enter_term_sys2=55, leave_term_sys2=20, invest_pct=0.25" in html
    assert "hovertemplate" in html
    assert "%{z:.4f}" in html
