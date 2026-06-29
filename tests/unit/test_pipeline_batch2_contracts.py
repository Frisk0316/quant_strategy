from backtesting.differential_validation import REFERENCE_VALIDATION_CONTRACTS


def test_pipeline_batch2_new_research_candidates_are_adapter_required():
    for strategy in ("c1_pairs_ou", "c2_funding_carry"):
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


def test_pipeline_batch2_c3_reuses_existing_fear_greed_contract():
    contract = REFERENCE_VALIDATION_CONTRACTS["fear_greed_sentiment"]
    assert contract["portable_validation_required"] is True
    assert contract["engines"]["vectorbt"]["status"] == "implemented"
