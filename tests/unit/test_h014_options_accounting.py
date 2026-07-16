"""Golden-cycle tests for H-014 inverse-options research accounting (I39/R8).

Hand-computed covered-call cycle per ADR-0010: entry premium, Deribit fee
formulas, coin-denominated settlement on the delivery price.
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "probes"))

from h014_stage3_backtest import (  # noqa: E402
    bs_coin,
    settle,
    settlement_fee,
    short_call_cycle_pnl,
    trade_fee,
)


def test_trade_fee_cap_and_floor():
    # small premium: 12.5% cap binds
    assert trade_fee(0.001) == pytest.approx(0.000125)
    # large premium: flat 0.0003 coin binds
    assert trade_fee(0.02) == pytest.approx(0.0003)


def test_settlement_fee_only_when_itm():
    assert settlement_fee(0.0) == 0.0
    assert settlement_fee(0.0004) == pytest.approx(0.00005)  # 12.5% cap
    assert settlement_fee(0.10) == pytest.approx(0.00015)  # flat cap


def test_inverse_settlement_payoffs():
    # call: (S_T - K)/S_T coin; put: (K - S_T)/S_T coin (R8.2)
    assert settle("call", 60_000, 55_000) == pytest.approx(5_000 / 60_000)
    assert settle("call", 50_000, 55_000) == 0.0
    assert settle("put", 40_000, 55_000) == pytest.approx(15_000 / 40_000)
    assert settle("put", 60_000, 55_000) == 0.0


def test_golden_short_call_cycle():
    """Hand-computed: sell 1 call at 0.0100 coin, K=55k, expires with S_T=60k.

    trade fee   = min(0.0003, 0.125*0.01) = 0.0003
    payoff      = (60000-55000)/60000     = 0.0833333...
    settle fee  = min(0.00015, 0.125*payoff) = 0.00015
    PnL = 0.01 - 0.0003 - 0.0833333 - 0.00015 = -0.0737833...
    """
    pnl = short_call_cycle_pnl(entry_premium=0.0100, s_t=60_000, k=55_000)
    assert pnl == pytest.approx(0.0100 - 0.0003 - 5_000 / 60_000 - 0.00015, abs=1e-12)


def test_golden_short_call_cycle_otm_keeps_premium():
    pnl = short_call_cycle_pnl(entry_premium=0.0100, s_t=50_000, k=55_000)
    assert pnl == pytest.approx(0.0100 - 0.0003, abs=1e-12)


def test_bs_coin_atm_magnitude():
    # ATM 30d at 50% vol: coin premium ~ 0.4 * sigma * sqrt(T) (Brenner-Subrahmanyam)
    approx = 0.4 * 0.50 * math.sqrt(30 / 365)
    got = bs_coin(50_000, 50_000, 50.0, 30 / 365, "call")
    assert got == pytest.approx(approx, rel=0.02)
