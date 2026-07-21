from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backtesting.xvenue_funding_spread_backtest import (
    MarketEvent,
    PairSizes,
    deribit_funding_cashflow,
    equal_usd_delta_sizes,
    inverse_perp_price_pnl_coin,
    pair_event_pnl,
    target_positions,
)
from backtesting.xvenue_funding_spread_probe import FundingProxyParams


def test_hand_computed_inverse_perp_cycle_base_and_stress_costs():
    nav = 1_000.0
    sizes = equal_usd_delta_sizes(1, binance_mark=100.0, pair_nav=nav)
    assert sizes == PairSizes(
        binance_base_qty=5.0,
        deribit_direction=-1,
        deribit_usd_notional=500.0,
    )

    rates = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0002)
    marks = (101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 101.0, 102.0)
    funding_coin, funding_usd = deribit_funding_cashflow(-1, 500.0, rates, marks)
    assert funding_coin == pytest.approx(0.1 / 102.0, rel=0.0, abs=1e-15)
    assert funding_usd == pytest.approx(0.1, rel=0.0, abs=1e-15)

    expected_inverse_coin = -500.0 * (1.0 / 100.0 - 1.0 / 105.0)
    assert inverse_perp_price_pnl_coin(-1, 500.0, 100.0, 105.0) == pytest.approx(
        expected_inverse_coin, rel=0.0, abs=1e-15
    )
    assert expected_inverse_coin * 105.0 == pytest.approx(-25.0, rel=0.0, abs=1e-12)

    base = pair_event_pnl(
        pair_position=1,
        sizes=sizes,
        binance_previous=100.0,
        binance_current=110.0,
        deribit_previous=100.0,
        deribit_current=105.0,
        binance_funding_rate=0.0001,
        deribit_hourly_rates=rates,
        deribit_hourly_marks=marks,
        turnover=2.0,
        cost_bps=4.0,
        pair_nav=nav,
    )
    stress = pair_event_pnl(
        pair_position=1,
        sizes=sizes,
        binance_previous=100.0,
        binance_current=110.0,
        deribit_previous=100.0,
        deribit_current=105.0,
        binance_funding_rate=0.0001,
        deribit_hourly_rates=rates,
        deribit_hourly_marks=marks,
        turnover=2.0,
        cost_bps=7.0,
        pair_nav=nav,
    )

    assert base["binance_price_pnl_usd"] == 50.0
    assert base["deribit_price_pnl_coin"] == pytest.approx(
        expected_inverse_coin, rel=0.0, abs=1e-15
    )
    assert base["deribit_price_pnl_usd"] == pytest.approx(-25.0, rel=0.0, abs=1e-12)
    assert base["binance_funding_usd"] == pytest.approx(-0.05, rel=0.0, abs=1e-15)
    assert base["deribit_funding_coin"] == pytest.approx(0.1 / 102.0, rel=0.0, abs=1e-15)
    assert base["deribit_funding_usd"] == pytest.approx(0.1, rel=0.0, abs=1e-15)
    assert base["gross_pnl_usd"] == pytest.approx(25.05, rel=0.0, abs=1e-12)
    assert base["turnover_cost_usd"] == pytest.approx(0.8, rel=0.0, abs=1e-15)
    assert stress["turnover_cost_usd"] == pytest.approx(1.4, rel=0.0, abs=1e-15)
    assert base["net_pnl_usd"] == pytest.approx(24.25, rel=0.0, abs=1e-12)
    assert stress["net_pnl_usd"] == pytest.approx(23.65, rel=0.0, abs=1e-12)


def test_signal_decision_first_applies_to_next_event():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    events = [
        MarketEvent(
            ts=start + timedelta(hours=8 * index),
            spread=0.0002,
            binance_rate=0.0,
            deribit_hourly_rates=(0.0,) * 8,
            binance_mark=100.0,
            deribit_mark=100.0,
            deribit_hourly_marks=(100.0,) * 8,
        )
        for index in range(5)
    ]

    assert target_positions(events, FundingProxyParams(3, 1.0)) == [0, 0, 0, 1, 1]
