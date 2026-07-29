from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from backtesting.options_flow_probe import (
    build_gamma_flow_proxy,
    build_large_otm_trade_flow,
    probe_opt_expiry_gamma,
    sampled_trades,
)


def _trade(ts: str, direction: str, amount: float, option: str = "BTC-5JAN24-60000-C") -> dict:
    return {
        "timestamp": int(pd.Timestamp(ts).timestamp() * 1000),
        "instrument_name": option,
        "direction": direction,
        "amount": amount,
        "price": 0.01,
        "index_price": 50_000,
    }


def test_option_features_use_customer_direction_gamma_and_top_decile_trade_size():
    rows = [
        {
            "dataset_id": "optflow_deribit_btc",
            "raw_payload": {
                "sample_rule": "fixture_complete",
                "sample": [
                    _trade(f"2024-01-01T{hour:02d}:00:00Z", "buy", float(hour + 1))
                    for hour in range(10)
                ],
            },
        }
    ]
    trades = sampled_trades(rows)
    gamma = build_gamma_flow_proxy(trades)
    large = build_large_otm_trade_flow(trades, lookback_hours=1)

    assert gamma.iloc[-1]["dealer_gamma_proxy"] < 0
    assert large.dropna().iloc[-1] > 0


def test_options_probe_refuses_db_access_without_whole_slate_i49():
    class NoDB:
        async def fetch(self, *_args, **_kwargs):
            raise AssertionError("DB must not be touched")

    with pytest.raises(ValueError, match="I49 whole-slate pre-flight"):
        asyncio.run(probe_opt_expiry_gamma(NoDB(), {}))


def test_options_probe_accepts_db_aggregated_sample_diagnostics():
    result = asyncio.run(
        probe_opt_expiry_gamma(
            object(),
            {
                "i49_preflight": {"status": "PASS"},
                "external_rows": [
                    {
                        "dataset_id": "optflow_deribit_btc",
                        "hourly_rows": 10,
                        "retained_sample_trades": 200,
                        "raw_sample_rules": ["first_20_inverse_trades_in_hour"],
                    }
                ],
            },
        )
    )

    details = result.checks[0].details
    assert details["hourly_rows"] == 10
    assert details["retained_sample_trades"] == 200
