from backtesting.parameter_sweep import (
    _attach_finalist_status,
    _estimate_finalist_count,
    coerce_parameter_values,
    estimate_sweep_runtime,
    expand_parameter_grid,
    rank_sweep_rows,
)
from backtesting.research_controls import apply_research_risk_overrides
from okx_quant.core.config import load_config


def test_coerce_parameter_values_supports_lists_and_ranges():
    assert coerce_parameter_values([7, 14, 21]) == [7, 14, 21]
    assert coerce_parameter_values("21..25:2") == [21, 23, 25]
    assert coerce_parameter_values("7, 21~25:2") == [7, 21, 23, 25]
    assert coerce_parameter_values("7~10") == [7, 8, 9, 10]


def test_expand_parameter_grid_allows_large_range_after_invalid_pairs_are_skipped():
    combos, skipped = expand_parameter_grid(
        "ma_crossover",
        {"fast_window": "7~100", "slow_window": "7~100"},
        max_combinations=5000,
    )

    assert len(combos) == 4371
    assert len(skipped) == 4465
    assert {"fast_window": 7, "slow_window": 21} in combos
    assert {"fast_window": 21, "slow_window": 21} not in combos


def test_expand_parameter_grid_filters_fast_slow_invalid_combinations():
    combos, skipped = expand_parameter_grid(
        "ma_crossover",
        {"fast_window": [7, 30], "slow_window": [21, 50]},
    )

    assert combos == [
        {"fast_window": 7, "slow_window": 21},
        {"fast_window": 7, "slow_window": 50},
        {"fast_window": 30, "slow_window": 50},
    ]
    assert skipped == [
        {
            "params": {"fast_window": 30, "slow_window": 21},
            "reason": "fast parameter must be smaller than slow parameter",
        }
    ]


def test_rank_sweep_rows_prefers_sharpe_then_return_then_drawdown():
    rows = [
        {
            "trial": 1,
            "status": "ok",
            "sharpe": 1.0,
            "total_return": 0.50,
            "max_drawdown": -0.30,
            "real_fill_count": 5,
        },
        {
            "trial": 2,
            "status": "ok",
            "sharpe": 1.2,
            "total_return": 0.10,
            "max_drawdown": -0.05,
            "real_fill_count": 5,
        },
        {
            "trial": 3,
            "status": "ok",
            "sharpe": 1.2,
            "total_return": 0.20,
            "max_drawdown": -0.15,
            "real_fill_count": 5,
        },
    ]

    ranked = rank_sweep_rows(rows)

    assert [row["trial"] for row in ranked] == [3, 2, 1]
    assert [row["rank"] for row in ranked] == [1, 2, 3]


def test_estimate_sweep_runtime_scales_with_bar_and_combinations():
    one_hour = estimate_sweep_runtime(
        strategy="ma_crossover",
        bar="1H",
        start="2024-01-01",
        end="2024-01-11",
        symbols=["BTC-USDT-SWAP"],
        combinations=10,
    )
    one_minute = estimate_sweep_runtime(
        strategy="ma_crossover",
        bar="1m",
        start="2024-01-01",
        end="2024-01-11",
        symbols=["BTC-USDT-SWAP"],
        combinations=10,
    )

    assert one_hour["estimated_total_seconds"] > 0
    assert one_minute["estimated_total_seconds"] > one_hour["estimated_total_seconds"]


def test_finalist_count_and_status_are_attached_to_ranked_rows():
    assert _estimate_finalist_count(
        4371,
        run_finalists=True,
        finalist_top_pct=0.10,
        max_finalists=20,
    ) == 20
    ranked = [{"rank": 1, "trial": 4}, {"rank": 2, "trial": 8}]
    _attach_finalist_status(
        ranked,
        [{"rank": 1, "status": "ok", "run_id": "ui_sweep_rank_001", "artifact_dir": "results/x"}],
    )

    assert ranked[0]["finalist_run_id"] == "ui_sweep_rank_001"
    assert ranked[0]["finalist_status"] == "ok"
    assert "finalist_run_id" not in ranked[1]


def test_research_risk_overrides_copy_config_without_mutating_base():
    cfg = load_config(require_secrets=False)
    original = cfg.risk.max_order_notional_usd

    updated, overrides = apply_research_risk_overrides(
        cfg,
        {"max_order_notional_usd": 2500, "max_pos_pct_equity": 0.75},
    )

    assert overrides == {"max_order_notional_usd": 2500.0, "max_pos_pct_equity": 0.75}
    assert updated.risk.max_order_notional_usd == 2500.0
    assert updated.risk.max_pos_pct_equity == 0.75
    assert cfg.risk.max_order_notional_usd == original
