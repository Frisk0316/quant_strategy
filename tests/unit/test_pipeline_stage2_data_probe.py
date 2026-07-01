from backtesting.pipeline_feasibility import result_to_dict
from scripts.run_pipeline_stage2_data_probe import (
    FundingThresholds,
    VenueThresholds,
    build_fail_closed_result,
    build_funding_data_check,
    build_stage2_result,
    build_xvenue_data_check,
)


def test_funding_breadth_requires_minimum_good_symbols():
    rows = [
        {"inst_id": f"SYM{i:02d}-USDT-SWAP", "row_count": 100, "coverage_ratio": 1.0}
        for i in range(9)
    ]
    rows.extend(
        {"inst_id": f"THIN{i:02d}-USDT-SWAP", "row_count": 20, "coverage_ratio": 0.2}
        for i in range(3)
    )

    check = build_funding_data_check(
        symbol_coverage=rows,
        rebalance_breadth=[{"day": "2024-01-01", "ready_symbols": 9}],
        thresholds=FundingThresholds(min_good_symbols=10, min_symbol_coverage=0.8, min_rebalance_breadth=10),
        universe_symbol_count=12,
        expected_8h_rows=100,
    )

    assert check.status == "FAIL"
    assert "good_symbols=9/10" in check.reason
    assert "min_rebalance_breadth=9/10" in check.reason
    assert check.details["good_symbol_count"] == 9
    assert check.details["thresholds"]["min_good_symbols"] == 10


def test_xvenue_probe_does_not_substitute_binance_for_missing_okx_leg():
    check = build_xvenue_data_check(
        venue_coverage={
            "BTC-USDT-SWAP": {
                "binance": {"row_count": 100, "coverage_ratio": 1.0},
                "okx": {"row_count": 0, "coverage_ratio": 0.0},
                "aligned_rows": 0,
                "alignment_ratio": 0.0,
            }
        },
        thresholds=VenueThresholds(min_coverage=0.95, min_alignment=0.95),
        expected_1m_rows=100,
    )

    assert check.status == "FAIL"
    assert "okx" in check.reason.lower()
    assert check.details["missing_venues"] == [
        {"inst_id": "BTC-USDT-SWAP", "venue": "okx", "coverage_ratio": 0.0}
    ]
    assert check.details["venue_coverage"]["BTC-USDT-SWAP"]["binance"]["coverage_ratio"] == 1.0


def test_data_probe_unavailable_fails_closed_without_stage3_release():
    result = build_fail_closed_result("funding", RuntimeError("db down"))
    payload = result_to_dict(result)
    checks = {check["name"]: check for check in payload["checks"]}

    assert payload["stage2_status"] == "FAIL"
    assert list(checks) == ["data_availability"]
    assert checks["data_availability"]["status"] == "FAIL"
    assert checks["data_availability"]["reason"] == "data_probe_unavailable"
    assert checks["data_availability"]["details"]["error_type"] == "RuntimeError"


def test_data_only_artifact_remains_stage2_fail_until_other_checks_run():
    check = build_xvenue_data_check(
        venue_coverage={
            "BTC-USDT-SWAP": {
                "binance": {"row_count": 100, "coverage_ratio": 1.0},
                "okx": {"row_count": 100, "coverage_ratio": 1.0},
                "aligned_rows": 100,
                "alignment_ratio": 1.0,
            }
        },
        thresholds=VenueThresholds(min_coverage=0.95, min_alignment=0.95),
        expected_1m_rows=100,
    )
    result = build_stage2_result("xvenue", check)

    assert check.status == "PASS"
    assert result_to_dict(result)["stage2_status"] == "FAIL"
