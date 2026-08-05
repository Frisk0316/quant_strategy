import pickle

import pandas as pd
import pytest

from backtesting.funding_xs_dispersion_backtest import (
    FundingXSDispersionParams,
    run_funding_xs_dispersion_backtest,
)
from scripts.worklog.build_funding_holdings import build_payload


def _fixture():
    index = pd.date_range("2024-01-01", periods=21, freq="D")
    symbols = [f"S{i}-USDT-SWAP" for i in range(10)]
    close = pd.DataFrame(100.0, index=index, columns=symbols)
    funding = pd.DataFrame(
        {symbol: [rank / 10_000] * len(index) for rank, symbol in enumerate(symbols)},
        index=index,
    )
    membership = pd.DataFrame(
        [
            {"date": date, "symbol": symbol, "eligible": True}
            for date in index
            for symbol in symbols
        ]
    )
    params = FundingXSDispersionParams(
        universe=symbols,
        bar="1D",
        rebalance="weekly",
        lookback_days=7,
        quantile=0.5,
        inverse_vol=True,
        max_name_weight=0.1,
    )
    return close, funding, membership, params


def _run(*, holdings_log: bool = False):
    close, funding, membership, params = _fixture()
    return run_funding_xs_dispersion_backtest(
        close,
        close,
        close,
        close,
        funding,
        membership,
        params,
        holdings_log=holdings_log,
    )


def test_holdings_log_is_opt_in_and_default_output_is_byte_identical():
    default = _run()
    explicit_off = _run(holdings_log=False)

    assert "holdings_log" not in default.metrics
    assert pickle.dumps(default, protocol=5) == pickle.dumps(explicit_off, protocol=5)


def test_holdings_log_records_capped_dollar_neutral_rebalances():
    result = _run(holdings_log=True)
    rows = result.metrics["holdings_log"]

    assert [row["date"] for row in rows] == ["2024-01-01", "2024-01-08", "2024-01-15"]
    for row in rows:
        target = result.target_weights.loc[row["date"]]
        assert row["long"] == target[target > 0].to_dict()
        assert row["short"] == (-target[target < 0]).to_dict()
        assert sum(row["long"].values()) == pytest.approx(0.5, abs=1e-6)
        assert sum(row["short"].values()) == pytest.approx(0.5, abs=1e-6)
        assert max((*row["long"].values(), *row["short"].values())) <= 0.1
        assert isinstance(row["period_return"], float)


def test_holdings_log_keeps_scheduled_flat_rebalances():
    close, funding, membership, params = _fixture()
    membership.loc[membership["date"] == pd.Timestamp("2024-01-08"), "eligible"] = False

    result = run_funding_xs_dispersion_backtest(
        close,
        close,
        close,
        close,
        funding,
        membership,
        params,
        holdings_log=True,
    )

    flat = next(row for row in result.metrics["holdings_log"] if row["date"] == "2024-01-08")
    assert flat["long"] == {}
    assert flat["short"] == {}


def test_holdings_payload_schema_and_notional_conversion():
    rows = _run(holdings_log=True).metrics["holdings_log"]
    payload = build_payload(rows, notional_base_usd=10_000, generated_at="2026-08-05T00:00:00+00:00")

    assert payload["schema_version"] == 1
    assert payload["params_frozen_from"] == "E-063"
    assert payload["notional_base_usd"] == 10_000
    assert payload["generated_at"] == "2026-08-05T00:00:00+00:00"
    first = payload["rebalances"][0]
    assert first["long"] == {"S0": 1000.0, "S1": 1000.0, "S2": 1000.0, "S3": 1000.0, "S4": 1000.0}
    assert first["short"] == {"S5": 1000.0, "S6": 1000.0, "S7": 1000.0, "S8": 1000.0, "S9": 1000.0}
