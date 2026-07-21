import math
from datetime import datetime, timedelta, timezone

import pytest

import backtesting.pipeline_stage2_registry as registry
from backtesting.pipeline_feasibility import FeasibilityCheck
from backtesting.xvenue_leadlag_probe import (
    BREADTH,
    N_OBS,
    N_TRIALS,
    PARAMS,
    AnchorParams,
    _funding_cashflow,
    build_distinctness_check,
    checks_from_evidence,
    payload_sha256,
    simulate_fixed_anchor,
    validate_calibration_evidence,
)


UTC = timezone.utc


def _rows(start, gaps, opens=None):
    opens = opens or [100.0] * len(gaps)
    rows = []
    for symbol in ("BTC-USDT-SWAP", "ETH-USDT-SWAP"):
        for offset, (gap, okx_open) in enumerate(zip(gaps, opens)):
            rows.append(
                {
                    "inst_id": symbol,
                    "ts": start + timedelta(minutes=offset),
                    "okx_open": okx_open,
                    "okx_close": 100.0,
                    "binance_close": 100.0 * math.exp(gap),
                }
            )
    return rows


def _funding(start, rate=0.001):
    return [
        {
            "source": "okx",
            "inst_id": symbol,
            "ts": start,
            "funding_rate": rate,
            "realized_rate": rate,
        }
        for symbol in ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
    ]


def test_funding_window_includes_entry_and_excludes_exit_settlement():
    entry = datetime(2024, 1, 1, tzinfo=UTC)
    middle = entry + timedelta(hours=8)
    exit_time = entry + timedelta(hours=16)

    cashflow, count = _funding_cashflow(
        ([entry, middle, exit_time], [0.001, 0.002, 0.004]),
        entry=entry,
        exit=exit_time,
        side=1,
    )

    assert count == 2
    assert cashflow == pytest.approx(-0.003)


def test_fixed_anchor_signal_uses_next_open_and_exact_episode_cost():
    start = datetime(2020, 1, 1, tzinfo=UTC)
    gaps = [0.0, 0.0, 0.03, 0.01, 0.01, 0.01]
    opens = [100.0, 100.0, 100.0, 100.0, 101.0, 101.0]

    result = simulate_fixed_anchor(
        _rows(start, gaps, opens),
        _funding(start),
        start=start,
        end=start + timedelta(minutes=len(gaps)),
        params=AnchorParams(lookback_min=3, z_entry=1.0, z_exit=0.5, max_hold_min=60),
    )

    assert result["input_valid"] is True
    assert result["funding_complete"] is True
    assert result["trade_count"] == 2
    trade = result["trades"][0]
    assert trade["entry_ts"] == (start + timedelta(minutes=3)).isoformat()
    assert trade["exit_ts"] == (start + timedelta(minutes=4)).isoformat()
    assert trade["gross_capture"] == pytest.approx(0.01)
    assert trade["roundtrip_cost_bps"] == 8.0


def test_positive_funding_is_paid_by_long_and_received_by_short():
    start = datetime(2020, 1, 1, tzinfo=UTC)
    index = ([start + timedelta(hours=8)], [0.001])

    long_cashflow, long_count = _funding_cashflow(
        index, entry=start, exit=start + timedelta(hours=9), side=1
    )
    short_cashflow, short_count = _funding_cashflow(
        index, entry=start, exit=start + timedelta(hours=9), side=-1
    )

    assert (long_cashflow, long_count) == (-0.001, 1)
    assert (short_cashflow, short_count) == (0.001, 1)


def test_missing_aligned_minute_fails_closed():
    start = datetime(2020, 1, 1, tzinfo=UTC)
    rows = _rows(start, [0.0] * 6)
    rows = [row for row in rows if not (
        row["inst_id"] == "BTC-USDT-SWAP" and row["ts"] == start + timedelta(minutes=2)
    )]

    result = simulate_fixed_anchor(
        rows,
        _funding(start),
        start=start,
        end=start + timedelta(minutes=6),
        params=AnchorParams(lookback_min=3),
    )

    assert result["input_valid"] is False
    assert any("BTC-USDT-SWAP" in error for error in result["errors"])


def test_distinctness_fails_closed_on_undefined_reference():
    candidate = {f"2024-01-{day:02d}": float(day % 2) for day in range(1, 10)}

    check = build_distinctness_check(candidate, {})

    assert check.status == "FAIL"
    assert check.details["undefined_fails_closed"] is True


def test_distinctness_compares_returns_to_returns_with_minimum_overlap():
    days = [(datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i)).date().isoformat() for i in range(400)]
    candidate = {day: float(1 if i % 2 else -1) for i, day in enumerate(days)}
    reference_one = {day: float((1, 1, -1, -1)[i % 4]) for i, day in enumerate(days)}
    reference_two = {day: float((1, -2, 1)[i % 3]) for i, day in enumerate(days)}

    check = build_distinctness_check(
        candidate,
        {
            "F-FUNDING-XS-DISPERSION": reference_one,
            "F-VOL-REGIME-OPT": reference_two,
            "F-XVENUE-FUNDING-SPREAD": {},
        },
    )

    assert check.status == "PASS"
    assert check.details["candidate_kind"] == "fixed_anchor_daily_net_strategy_returns"


def test_calibration_evidence_hash_and_reference_hash_are_fail_closed(tmp_path):
    refs = {}
    for family, field in (
        ("F-FUNDING-XS-DISPERSION", "signal"),
        ("F-VOL-REGIME-OPT", "return"),
        ("F-XVENUE-FUNDING-SPREAD", "return"),
    ):
        path = tmp_path / f"{family}.json"
        path.write_text("{}", encoding="utf-8")
        refs[family] = (path, "json", field)
    reference_payload = {
        family: {
            "path": str(path).replace("\\", "/"),
            "format": kind,
            "field": field,
            "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
        }
        for family, (path, kind, field) in refs.items()
    }
    payload = {
        "schema_version": 1,
        "kind": "h010_pre_stage2_calibration",
        "anchor": PARAMS.__dict__,
        "statistical_power": {
            "breadth": BREADTH,
            "n_obs": N_OBS,
            "n_trials": N_TRIALS,
            "plausible_net_sharpe": 0.0,
        },
        "references": reference_payload,
    }
    payload["payload_sha256"] = payload_sha256(payload)

    assert validate_calibration_evidence(payload, reference_specs=refs)["payload_sha256"]
    payload["statistical_power"]["n_obs"] = 1
    with pytest.raises(ValueError, match="hash mismatch"):
        validate_calibration_evidence(payload, reference_specs=refs)


def test_stage2_checks_reject_binance_funding_substitution():
    evidence = {
        "measured": False,
        "calibration_window": {},
        "statistical_power": {"plausible_net_sharpe": 0.0},
        "calibration": {
            "input_valid": True,
            "funding": {"complete": False, "source": "okx"},
            "trade_count": 10,
            "median_gross_capture_bps": 12.0,
            "median_roundtrip_cost_bps": 8.0,
            "cost_gate_passed": True,
        },
        "distinctness": {"status": "FAIL", "reason": "prerequisite missing", "details": {}},
    }

    checks = checks_from_evidence(FeasibilityCheck("data_availability", "PASS", "candles ok"), evidence)

    assert [check.status for check in checks] == ["FAIL", "FAIL", "FAIL"]
    assert checks[0].details["cross_venue_funding_substitution"] is False


@pytest.mark.asyncio
async def test_active_xvenue_stage2_requires_frozen_evidence_before_connect(tmp_path, monkeypatch):
    async def forbidden_connect(_dsn):
        raise AssertionError("DB connection opened before H-010 evidence validation")

    monkeypatch.setattr(registry, "_connect", forbidden_connect)
    with pytest.raises(ValueError, match="requires frozen calibration evidence"):
        await registry.run_data_probe(
            dsn="postgresql://example",
            output_root=tmp_path,
            universe_path=tmp_path / "unused.parquet",
            candidates=["xvenue"],
            statistical_power={
                "breadth": BREADTH,
                "n_obs": N_OBS,
                "n_trials": N_TRIALS,
                "plausible_net_sharpe": 0.0,
            },
        )
