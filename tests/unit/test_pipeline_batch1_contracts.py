import yaml

from backtesting.differential_validation import REFERENCE_VALIDATION_CONTRACTS


def test_pipeline_batch1_candidates_are_disabled_and_adapter_required():
    with open("config/strategies.yaml", encoding="utf-8") as f:
        strategies = yaml.safe_load(f)

    for strategy in ("s5_residual_meanrev", "s6_ts_momentum", "s7_basis_meanrev"):
        assert strategies[strategy]["enabled"] is False
        contract = REFERENCE_VALIDATION_CONTRACTS[strategy]
        assert contract["portable_validation_required"] is True
        assert {
            engine: spec["status"]
            for engine, spec in contract["engines"].items()
        } == {
            "vectorbt": "adapter_required",
            "backtrader": "adapter_required",
            "nautilus": "adapter_required",
        }


def test_pipeline_refit_summary_carries_cpcv_retention_fields():
    import pandas as pd

    from scripts.run_pipeline_batch1_checkpoint import _refit_validation

    idx = pd.date_range("2024-01-01", periods=24, freq="D")
    records = [
        {
            "combo": {"lookback_days": 3},
            "daily_returns": pd.Series([0.001, -0.002, 0.003, 0.001] * 6, index=idx),
        },
        {
            "combo": {"lookback_days": 7},
            "daily_returns": pd.Series([-0.001, 0.002, 0.001, -0.002] * 6, index=idx),
        },
    ]

    validation = _refit_validation(
        records,
        n_trials=2,
        is_days=6,
        oos_days=3,
        cpcv_n_splits=4,
        cpcv_k_test=2,
        embargo_pct=0.0,
        purge_size=0,
    )

    assert validation["cpcv"]["path_returns"]
    assert validation["cpcv"]["path_return_lengths"] == [
        len(values) for values in validation["cpcv"]["path_returns"]
    ]
    assert validation["cpcv"]["n_trials_provenance"] == "caller_declared"
    assert validation["cpcv"]["n_trials_is_floor"] is False
