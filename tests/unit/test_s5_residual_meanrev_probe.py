import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import backtesting.s5_residual_meanrev_probe as probe
from backtesting.s5_residual_meanrev_probe import (
    MIN_MEMBER_DAY_COVERAGE,
    build_data_check,
    build_breadth_provenance,
    derive_breadth,
    evaluate_probe,
    file_sha256,
    load_effective_membership,
    load_frozen_e014_params,
)


def test_membership_collapses_alias_after_top_n_without_refill(tmp_path: Path) -> None:
    path = tmp_path / "membership.parquet"
    pd.DataFrame(
        [
            {"date": "2024-01-01", "symbol": "SHIB-USDT-SWAP", "eligible": True, "adv_usd": 3},
            {"date": "2024-01-01", "symbol": "1000SHIB-USDT-SWAP", "eligible": True, "adv_usd": 2},
            {"date": "2024-01-01", "symbol": "BTC-USDT-SWAP", "eligible": True, "adv_usd": 1},
        ]
    ).to_parquet(path)

    membership, audit = load_effective_membership(
        path,
        start=pd.Timestamp("2024-01-01", tz="UTC").to_pydatetime(),
        end=pd.Timestamp("2024-01-02", tz="UTC").to_pydatetime(),
        top_n=2,
    )

    assert membership["symbol"].tolist() == ["1000SHIB-USDT-SWAP"]
    assert audit["raw_member_days"] == 2
    assert audit["effective_member_days"] == 1
    assert audit["no_rank_refill_after_alias_collapse"] is True


def test_breadth_is_mean_daily_actual_position_count() -> None:
    hours = pd.date_range("2024-01-01", periods=48, freq="h")
    positions = pd.DataFrame(0.0, index=hours, columns=["A", "B", "C"])
    positions.loc["2024-01-01", ["A", "B"]] = [0.5, -0.5]
    positions.loc["2024-01-02", ["A", "B", "C"]] = [0.4, -0.2, -0.2]
    returns = pd.Series([0.01, -0.01], index=pd.date_range("2024-01-01", periods=2, freq="D"))

    result = derive_breadth(positions, returns)

    assert result["measured_mean_simultaneous_names"] == 2.5
    assert result["breadth_used"] == 2.5
    assert [row["count"] for row in result["input_nonzero_position_count_by_day"]] == [2, 3]


def test_breadth_fails_closed_to_one_for_zero_positions() -> None:
    days = pd.date_range("2024-01-01", periods=2, freq="D")
    result = derive_breadth(pd.DataFrame(0.0, index=days, columns=["A"]), pd.Series([0.0, 0.0], index=days))

    assert result["measured_mean_simultaneous_names"] == 0.0
    assert result["breadth_used"] == 1.0
    assert result["fail_closed_to_one"] is True


def test_frozen_params_are_loaded_from_e014_artifact(tmp_path: Path) -> None:
    source = tmp_path / "summary.json"
    source.write_text(
        '{"family_id":"F-S5-RESIDUAL-MEANREV","full_sample_best_params":'
        '{"factors":"BTC+ETH","fee_bps":2.0,"lookback_days":14,"slippage_bps":2.0,'
        '"top_n":10,"z_enter":1.5,"z_exit":0.0}}',
        encoding="utf-8",
    )

    params, provenance = load_frozen_e014_params(source)

    assert params.factors == "BTC+ETH"
    assert params.lookback_days == 14
    assert params.top_n == 10
    assert provenance["source_field"] == "full_sample_best_params"
    assert len(provenance["source_sha256"]) == 64


def test_data_gate_fails_closed_when_eth_factor_is_absent() -> None:
    day = pd.Timestamp("2024-01-01")
    minutes = pd.date_range(day, periods=1_440, freq="min")
    close = pd.DataFrame({"BTC-USDT-SWAP": 1.0, "A-USDT-SWAP": 1.0}, index=minutes)
    membership = pd.DataFrame(
        [{"date": day, "symbol": "A-USDT-SWAP", "eligible": True, "adv_usd": 1.0}]
    )

    check = build_data_check(close, membership, {"universe_days": 898})

    assert check.status == "FAIL"
    assert check.details["factor_missing_days"]["ETH-USDT-SWAP"] == 898


def test_e095_coverage_threshold_passes_into_distinctness(monkeypatch, tmp_path: Path) -> None:
    day = pd.Timestamp("2024-01-01")
    monkeypatch.setattr(probe, "START", day.tz_localize("UTC").to_pydatetime())
    monkeypatch.setattr(
        probe,
        "END",
        (day + pd.Timedelta(days=1)).tz_localize("UTC").to_pydatetime(),
    )
    monkeypatch.setattr(probe, "EXPECTED_MINUTES_PER_DAY", 1)
    symbols = [f"S{index}-USDT-SWAP" for index in range(17_272)]
    membership = pd.DataFrame(
        {"date": day, "symbol": symbols, "eligible": True, "adv_usd": 1.0}
    )
    closes = {symbol: 1.0 for symbol in (*probe.FACTOR_SYMBOLS, *symbols)}
    closes[symbols[-1]] = None
    close = pd.DataFrame([closes], index=[day])
    source = tmp_path / "summary.json"
    source.write_text(
        '{"family_id":"F-S5-RESIDUAL-MEANREV","full_sample_best_params":'
        '{"factors":"BTC+ETH","fee_bps":2.0,"lookback_days":14,"slippage_bps":2.0,'
        '"top_n":10,"z_enter":1.5,"z_exit":0.0}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        probe,
        "run_s5_residual_meanrev_backtest",
        lambda *_args: SimpleNamespace(
            positions=pd.DataFrame([[0.5, -0.5]], index=[day], columns=["A", "B"]),
            daily_returns=pd.Series([0.01], index=[day]),
        ),
    )

    result = evaluate_probe(
        close,
        pd.DataFrame(),
        membership,
        {"universe_days": 1},
        e014_path=source,
    )
    data = result.checks[0]

    assert MIN_MEMBER_DAY_COVERAGE == 0.95
    assert data.status == "PASS"
    assert data.details["member_day_coverage"] == 17_271 / 17_272
    assert "taker_flow_probe.py" in data.details["required_member_day_coverage_provenance"]["precedent"]
    assert data.details["required_member_day_coverage_provenance"]["invariant"].startswith(
        "docs/INVARIANTS.md::I11"
    )
    assert result.checks[1].reason.startswith("UNCONFIRMED")


def test_data_failure_records_data_as_downstream_stop_point(tmp_path: Path) -> None:
    source = tmp_path / "summary.json"
    source.write_text(
        '{"family_id":"F-S5-RESIDUAL-MEANREV","full_sample_best_params":'
        '{"factors":"BTC+ETH","fee_bps":2.0,"lookback_days":14,"slippage_bps":2.0,'
        '"top_n":10,"z_enter":1.5,"z_exit":0.0}}',
        encoding="utf-8",
    )
    day = pd.Timestamp("2024-01-01")
    membership = pd.DataFrame(
        [{"date": day, "symbol": "A-USDT-SWAP", "eligible": True, "adv_usd": 1.0}]
    )

    result = evaluate_probe(
        pd.DataFrame(index=pd.DatetimeIndex([])),
        pd.DataFrame(),
        membership,
        {"universe_days": 1},
        e014_path=source,
    )

    assert result.checks[2].details["stop_point"] == "data_availability"
    assert result.checks[3].details["stop_point"] == "data_availability"
    assert "data availability failed" in result.checks[2].reason


def test_breadth_provenance_records_empty_position_input(tmp_path: Path) -> None:
    parent = tmp_path / "stage2_feasibility.json"
    parent.write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "name": "data_availability",
                        "status": "FAIL",
                        "details": {
                            "missing_member_days": [
                                {"day": "2026-01-01", "symbol": "SOL-USDT-SWAP", "minute_rows": 1439}
                            ]
                        },
                    },
                    {
                        "name": "statistical_power",
                        "status": "FAIL",
                        "details": {"stop_point": "data_availability", "breadth": 1.0, "n_obs": 0},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    provenance = build_breadth_provenance(parent)

    assert provenance["positions_present"] is False
    assert provenance["input_nonzero_position_count_by_day"] == []
    assert provenance["measured_mean_simultaneous_names"] is None
    assert provenance["breadth_used"] == 1.0
    assert provenance["fail_closed_to_one"] is True
    assert provenance["n_obs"] == 0
    assert provenance["parent_artifact"]["sha256"] == file_sha256(parent)
