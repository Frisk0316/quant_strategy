from datetime import datetime, timedelta, timezone

import pytest

from backtesting.xvenue_funding_spread_probe import (
    AlignedEvent,
    FundingProxyParams,
    ProbeThresholds,
    align_funding_events,
    build_distinctness_check,
    evaluate_funding_proxy,
    evaluate_xvenue_funding_spread_rows,
    event_gap_count,
)


UTC = timezone.utc


def test_two_leg_turnover_and_funding_are_gross_normalized_and_lagged():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    events = [
        AlignedEvent(start + timedelta(hours=8 * index), deribit_rate=spread, binance_rate=0.0)
        for index, spread in enumerate((0.001, -0.001, 0.001))
    ]

    result = evaluate_funding_proxy(
        events,
        FundingProxyParams(lookback_events=1, entry_bps=0.0),
        one_way_cost_bps=4.0,
    )

    # Targets are +1,-1,+1, but t+1 execution produces positions 0,+1,-1.
    assert result["gross_capture"] == pytest.approx(-0.001)
    # Entry 1 + flip 2 + final exit 1 across two 0.5 legs.
    assert result["turnover"] == pytest.approx(4.0)
    assert result["cost"] == pytest.approx(0.0016)


def test_full_funding_alignment_still_fails_closed_without_deribit_prices():
    start = datetime(2024, 1, 2, tzinfo=UTC)
    end = start + timedelta(hours=16)
    binance_rows = []
    deribit_rows = []
    for symbol, dataset in (
        ("BTC-USDT-SWAP", "funding_deribit_btc"),
        ("ETH-USDT-SWAP", "funding_deribit_eth"),
    ):
        for event_index in range(2):
            event_ts = start + timedelta(hours=8 * event_index)
            # Provider settlements may land a millisecond before the nominal hour.
            binance_rows.append(
                {
                    "inst_id": symbol,
                    "observed_at": event_ts - timedelta(milliseconds=1),
                    "rate": 0.0001,
                }
            )
            for offset in range(7, -1, -1):
                observed_at = event_ts - timedelta(hours=offset)
                deribit_rows.append(
                    {
                        "dataset_id": dataset,
                        "observed_at": observed_at,
                        "published_at": observed_at,
                        "rate": 0.00002,
                        "quality_status": "validated",
                        "unit": "rate_1h_decimal",
                    }
                )

    result = evaluate_xvenue_funding_spread_rows(
        binance_rows=binance_rows,
        deribit_rows=deribit_rows,
        price_rows=[],
        ctx={
            "batch_id": "batch",
            "candidate_id": "candidate",
            "candidate_dir": "candidate_dir",
            "hypothesis_id": "H-test",
            "family_id": "F-XVENUE-FUNDING-SPREAD",
            "start": start,
            "end": end,
        },
        thresholds=ProbeThresholds(min_common_days=0, min_price_coverage=0.95),
    )

    checks = {check.name: check for check in result.checks}
    assert result.batch_id == "batch"
    assert result.family_id == "F-XVENUE-FUNDING-SPREAD"
    assert checks["data_availability"].status == "FAIL"
    assert checks["data_availability"].details["funding_signal_ready"] is True
    assert checks["data_availability"].details["stage3_price_ready"] is False


def test_alignment_rejects_timestamp_jitter_over_one_second():
    event_ts = datetime(2024, 1, 2, tzinfo=UTC)
    deribit_rows = []
    for offset in range(7, -1, -1):
        observed_at = event_ts - timedelta(hours=offset)
        if offset == 0:
            observed_at += timedelta(seconds=2)
        deribit_rows.append(
            {
                "dataset_id": "funding_deribit_btc",
                "observed_at": observed_at,
                "published_at": observed_at,
                "rate": 0.00002,
                "quality_status": "validated",
                "unit": "rate_1h_decimal",
            }
        )

    aligned, _coverage = align_funding_events(
        [{"inst_id": "BTC-USDT-SWAP", "observed_at": event_ts, "rate": 0.0001}],
        deribit_rows,
        start=event_ts,
        end=event_ts + timedelta(hours=8),
    )

    assert aligned["BTC-USDT-SWAP"] == []


def test_distinctness_fails_closed_when_correlation_is_undefined():
    check = build_distinctness_check({"BTC-USDT-SWAP": [], "ETH-USDT-SWAP": []})

    assert check.status == "FAIL"
    assert check.details["all_correlations_defined"] is False


def test_funding_proxy_detects_missing_eight_hour_event():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    events = [
        AlignedEvent(start, deribit_rate=0.001, binance_rate=0.0),
        AlignedEvent(start + timedelta(hours=16), deribit_rate=0.001, binance_rate=0.0),
    ]

    assert event_gap_count(events) == 1
