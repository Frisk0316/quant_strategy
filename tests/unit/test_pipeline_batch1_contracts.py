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
