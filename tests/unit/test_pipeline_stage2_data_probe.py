from backtesting.pipeline_feasibility import result_to_dict
from scripts.run_pipeline_stage2_data_probe import (
    FundingThresholds,
    OIThresholds,
    VenueThresholds,
    build_fail_closed_result,
    build_funding_data_check,
    build_oi_data_check,
    build_oi_universe_data_check,
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
        rebalance_breadth=[{"day": "2024-03-01", "ready_symbols": 9}],
        thresholds=FundingThresholds(min_good_symbols=10, min_symbol_coverage=0.8, min_rebalance_breadth=10),
        universe_symbol_count=12,
        expected_8h_rows=100,
    )

    assert check.status == "FAIL"
    assert "good_symbols=9/10" in check.reason
    assert "min_rebalance_breadth=9/10" in check.reason
    assert check.details["good_symbol_count"] == 9
    assert check.details["thresholds"]["min_good_symbols"] == 10


def test_funding_breadth_excludes_warmup_edge_days_from_min():
    """User-approved 2026-07-03 window change: universe eligibility needs 30
    warmup days, so breadth-min is evaluated from START+30d; earlier days stay
    recorded in details but cannot fail the check. An all-warmup window stays
    fail-closed (empty evaluation -> min 0)."""
    rows = [
        {"inst_id": f"SYM{i:02d}-USDT-SWAP", "row_count": 100, "coverage_ratio": 1.0}
        for i in range(12)
    ]
    warmup_edge = [{"day": "2024-01-05", "ready_symbols": 2}]
    post_warmup = [{"day": "2024-02-05", "ready_symbols": 12}, {"day": "2024-02-06", "ready_symbols": 11}]

    check = build_funding_data_check(
        symbol_coverage=rows,
        rebalance_breadth=warmup_edge + post_warmup,
        thresholds=FundingThresholds(),
        universe_symbol_count=12,
        expected_8h_rows=100,
    )
    assert check.status == "PASS"
    assert check.details["rebalance_breadth_stats"]["min"] == 11
    assert check.details["window"]["breadth_warmup_cutoff"] == "2024-01-31"
    assert check.details["window"]["breadth_days_evaluated"] == 2
    assert check.details["window"]["breadth_days_total"] == 3
    assert len(check.details["rebalance_breadth"]) == 3  # warmup days stay auditable

    all_warmup = build_funding_data_check(
        symbol_coverage=rows,
        rebalance_breadth=warmup_edge,
        thresholds=FundingThresholds(),
        universe_symbol_count=12,
        expected_8h_rows=100,
    )
    assert all_warmup.status == "FAIL"  # fail-closed: nothing evaluable
    assert all_warmup.details["window"]["breadth_days_evaluated"] == 0


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


def test_oi_probe_reports_coverage_missing_and_stale_ratios():
    check = build_oi_data_check(
        dataset_coverage={
            "oi_binance_hist_btc": {
                "row_count": 288,
                "daily_rows": [{"day": "2024-01-01", "row_count": 288}],
            },
            "oi_binance_hist_eth": {
                "row_count": 200,
                "daily_rows": [{"day": "2024-01-01", "row_count": 200}],
            },
        },
        thresholds=OIThresholds(min_coverage=0.95, max_stale_ratio=0.05),
        expected_5m_rows=288,
        expected_days=1,
    )

    assert check.status == "FAIL"
    assert "oi_binance_hist_eth" in check.reason
    assert check.details["dataset_coverage"]["oi_binance_hist_btc"]["coverage_ratio"] == 1.0
    assert check.details["dataset_coverage"]["oi_binance_hist_btc"]["missing_ratio"] == 0.0
    assert check.details["dataset_coverage"]["oi_binance_hist_btc"]["stale_ratio"] == 0.0
    assert check.details["dataset_coverage"]["oi_binance_hist_eth"]["missing_ratio"] == 88 / 288
    assert check.details["dataset_coverage"]["oi_binance_hist_eth"]["stale_ratio"] == 1.0


def test_oi_universe_probe_uses_pit_days_and_good_symbol_gate():
    good_symbols = [f"GOOD{i:02d}-USDT-SWAP" for i in range(9)]
    daily_universe = {
        "2024-01-01": set(good_symbols + ["THIN-USDT-SWAP"]),
        "2024-01-02": set(good_symbols),
    }
    daily_rows = {
        f"oi_binance_hist_good{i:02d}": [
            {"day": "2024-01-01", "row_count": 288, "first_ts": "2024-01-01T00:00:00+00:00"},
            {"day": "2024-01-02", "row_count": 288, "first_ts": "2024-01-02T00:00:00+00:00"},
        ]
        for i in range(9)
    }
    daily_rows["oi_binance_hist_thin"] = [{"day": "2024-01-01", "row_count": 100}]

    check = build_oi_universe_data_check(
        symbols=good_symbols + ["THIN-USDT-SWAP"],
        daily_universe=daily_universe,
        dataset_daily_rows=daily_rows,
        thresholds=OIThresholds(min_good_symbols=10, min_coverage=0.95, max_stale_ratio=0.05),
    )

    assert check.status == "FAIL"
    assert "good_symbols=9/10" in check.reason
    assert check.details["good_symbol_count"] == 9
    assert check.details["thresholds"]["min_good_symbols"] == 10
    assert check.details["symbol_coverage"][0]["expected_5m_rows"] == 576
    assert check.details["symbol_coverage"][-1]["inst_id"] == "THIN-USDT-SWAP"
    assert check.details["symbol_coverage"][-1]["expected_5m_rows"] == 288


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
