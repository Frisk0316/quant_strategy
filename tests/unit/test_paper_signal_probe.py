from __future__ import annotations

import math
from dataclasses import replace

import pandas as pd
import pytest

from backtesting.paper_signal_probe import (
    BTC,
    CANDIDATES,
    ETH,
    CandidateEvaluation,
    ProbeInputs,
    _distinctness_check,
    _membership_matrix,
    _power_check,
    _validate_power_contract,
    available_scalar,
    build_salience_targets,
    central_pnl,
    run_isolated_candidates,
    salience_statistic,
    stage3_gate_checks,
)
from backtesting.pipeline_feasibility import FeasibilityCheck, FeasibilityResult


def _stage2(spec, status: str) -> FeasibilityResult:
    checks = tuple(
        FeasibilityCheck(name, status, "test")
        for name in ("data_availability", "distinctness", "cost_after_edge", "statistical_power")
    )
    return FeasibilityResult("test", spec.signal_ref, spec.candidate_dir, spec.hypothesis_id, spec.family_id, checks)


def test_published_at_signal_executes_t_plus_one() -> None:
    days = pd.date_range("2024-01-01", periods=4, tz="UTC")
    rows = pd.DataFrame(
        {
            "dataset_id": ["feature"],
            "observed_at": [days[0]],
            "published_at": [days[1]],
            "value_num": [1.0],
            "quality_status": ["validated"],
        }
    )
    available = available_scalar(rows, "feature")
    assert available.index.tolist() == [days[1]]

    target = pd.DataFrame({BTC: available.reindex(days).fillna(0.0)}, index=days)
    close = pd.DataFrame({BTC: [100.0, 100.0, 110.0, 110.0]}, index=days)
    funding = pd.DataFrame({BTC: 0.0}, index=days)
    pnl = central_pnl(target, close, funding)
    assert pnl.loc[days[1], "positions"] == "{}"
    assert pnl.loc[days[2], "positions"] == '{"BTC-USDT-SWAP":1.0}'
    assert math.isclose(pnl.loc[days[2], "gross"], 0.10)


def test_central_pnl_posts_sum_funding_and_full_roundtrip_cost() -> None:
    days = pd.date_range("2024-01-01", periods=3, tz="UTC")
    target = pd.DataFrame({BTC: [1.0, 0.0, 0.0]}, index=days)
    close = pd.DataFrame({BTC: [100.0, 110.0, 110.0]}, index=days)
    funding = pd.DataFrame({BTC: [0.0, 0.001, 0.0]}, index=days)
    pnl = central_pnl(target, close, funding)
    assert math.isclose(pnl["gross"].sum(), 0.10)
    assert math.isclose(pnl["funding"].sum(), -0.001)
    assert math.isclose(pnl["cost"].sum(), 0.0008)
    assert math.isclose(pnl["net"].sum(), 0.0982)


def test_salience_formula_and_weekly_target() -> None:
    ri = pd.Series([0.10, -0.02, 0.01])
    rm = pd.Series([0.00, 0.00, 0.00])
    sigma = (ri - rm).abs() / (ri.abs() + rm.abs() + 0.1)
    rank = sigma.rank(ascending=False, method="first")
    weights = 0.7 ** (rank - 1.0)
    expected = float((weights / weights.sum() * ri).sum() - ri.mean())
    assert math.isclose(salience_statistic(ri, rm), expected)

    days = pd.date_range("2024-01-01", periods=14, tz="UTC")
    returns = pd.DataFrame(
        {
            f"S{i}": [0.00]
            + [((i + 1) / 500.0) * (1 if (day + i) % 3 else -1) for day in range(13)]
            for i in range(10)
        },
        index=days,
    )
    closes = 100.0 * (1.0 + returns).cumprod()
    membership = pd.DataFrame(True, index=days, columns=closes.columns)
    targets = build_salience_targets(closes, membership)
    rebalance = pd.Timestamp("2024-01-08", tz="UTC")
    assert math.isclose(targets.loc[rebalance].clip(lower=0).sum(), 0.5)
    assert math.isclose(targets.loc[rebalance].clip(upper=0).sum(), -0.5)
    assert targets.loc[rebalance].gt(0).sum() == 2
    assert targets.loc[rebalance].lt(0).sum() == 2
    pd.testing.assert_series_equal(
        targets.loc[rebalance],
        targets.loc[rebalance + pd.Timedelta(days=1)],
        check_names=False,
    )
    too_narrow = build_salience_targets(closes.iloc[:, :9], membership.iloc[:, :9])
    assert not too_narrow.loc[rebalance].any()


def test_salience_membership_reuses_consumer_time_alias_collapse() -> None:
    day = pd.Timestamp("2024-01-01", tz="UTC")
    membership = pd.DataFrame(
        {
            "date": [day, day],
            "symbol": ["SHIB-USDT-SWAP", "1000SHIB-USDT-SWAP"],
            "eligible": [True, True],
        }
    )
    matrix = _membership_matrix(
        membership,
        ["1000SHIB-USDT-SWAP"],
        pd.DatetimeIndex([day]),
    )
    assert matrix.loc[day, "1000SHIB-USDT-SWAP"]
    assert matrix.sum(axis=1).iloc[0] == 1


def test_stage2_fail_stops_stage3_and_exceptions_are_isolated() -> None:
    specs = CANDIDATES[:3]
    stage3_calls: list[str] = []

    def stage2_runner(spec):
        if spec.hypothesis_id == "H-041":
            raise RuntimeError("broken candidate")
        status = "FAIL" if spec.hypothesis_id == "H-040" else "PASS"
        return CandidateEvaluation(spec, _stage2(spec, status), pd.DataFrame(), pd.DataFrame(), {})

    def stage3_runner(evaluation):
        stage3_calls.append(evaluation.spec.hypothesis_id)
        return {"statistical_gate_passed": False}

    outcomes = run_isolated_candidates(specs, stage2_runner, stage3_runner)
    assert stage3_calls == ["H-042"]
    assert outcomes[0].stage3 is None and outcomes[0].error is None
    assert isinstance(outcomes[1].error, RuntimeError)
    assert outcomes[2].stage3 == {"statistical_gate_passed": False}


def test_new_family_distinctness_fails_closed_on_undefined_market_correlation() -> None:
    days = pd.date_range("2024-01-01", periods=400, tz="UTC")
    close = pd.DataFrame(
        {
            BTC: 100.0 + pd.Series(range(400), index=days),
            "ETH-USDT-SWAP": 50.0 + pd.Series(range(400), index=days) * 0.5,
        },
        index=days,
    )
    references = {
        "E031_funding_xs": pd.Series(range(400), index=days, dtype=float),
        "E045_xs_illiquidity:test": pd.Series(range(400), index=days, dtype=float),
    }
    inputs = ProbeInputs(
        close=close,
        funding=pd.DataFrame(index=days),
        external=pd.DataFrame(),
        membership=pd.DataFrame(),
        references=references,
        reference_errors={},
    )
    check = _distinctness_check(CANDIDATES[0], inputs, pd.Series(0.0, index=days))
    assert check.status == "FAIL"
    assert "btc_buy_hold" in check.details["reference_errors"]
    assert "btc_eth_equal_weight_buy_hold" in check.details["reference_errors"]


def test_stage3_gate_requires_all_reconciliation_checks() -> None:
    passed = stage3_gate_checks(
        dsr=0.96,
        psr=0.97,
        nonzero_activity=True,
        n_trials=1,
        n_trials_provenance="caller_declared",
    )
    assert passed["statistical_gate_passed"]
    assert not stage3_gate_checks(
        dsr=0.98,
        psr=0.97,
        nonzero_activity=True,
        n_trials=1,
        n_trials_provenance="caller_declared",
    )["statistical_gate_passed"]
    assert not stage3_gate_checks(
        dsr=0.96,
        psr=0.97,
        nonzero_activity=False,
        n_trials=2,
        n_trials_provenance="grid_size_floor",
    )["statistical_gate_passed"]


def test_power_breadth_is_explicit_and_prevalidated() -> None:
    days = pd.date_range("2024-01-01", periods=400, tz="UTC")
    targets = pd.DataFrame({BTC: 0.5, ETH: 0.5}, index=days)
    pnl = pd.DataFrame({"net": 0.001}, index=days)
    spec = replace(CANDIDATES[1], power_breadth=1.0)

    assert _power_check(spec, targets, pnl).details["breadth"] == 1.0
    with pytest.raises(ValueError, match="finite and positive"):
        _validate_power_contract((replace(spec, power_breadth=0.0),))
