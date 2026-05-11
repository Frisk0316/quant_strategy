"""Regression tests for SWAP contract-value position accounting."""

import pytest

from okx_quant.portfolio.positions import PositionLedger


def test_swap_unrealized_pnl_and_notional_use_ct_val():
    ledger = PositionLedger(initial_equity=10_000.0)

    ledger.on_fill(
        "BTC-USDT-SWAP",
        "buy",
        fill_px=40_000.0,
        fill_sz=0.25,
        fee=0.0,
        strategy="ct_val_regression",
        metadata={"ct_val": 0.01},
    )
    ledger.update_price("BTC-USDT-SWAP", 41_000.0)

    position = ledger.get_position("BTC-USDT-SWAP")

    assert position.size == pytest.approx(0.25)
    assert position.avg_entry == pytest.approx(40_000.0)
    assert position.ct_val == pytest.approx(0.01)
    assert position.unrealized_pnl == pytest.approx(2.5)
    assert position.notional == pytest.approx(102.5)
    assert ledger.get_equity() == pytest.approx(10_002.5)


def test_swap_realized_pnl_uses_ct_val_on_close():
    ledger = PositionLedger(initial_equity=10_000.0)

    ledger.on_fill(
        "BTC-USDT-SWAP",
        "buy",
        fill_px=40_000.0,
        fill_sz=0.25,
        fee=0.0,
        strategy="ct_val_regression",
        metadata={"ct_val": 0.01},
    )
    ledger.on_fill(
        "BTC-USDT-SWAP",
        "sell",
        fill_px=41_000.0,
        fill_sz=0.25,
        fee=0.0,
        strategy="ct_val_regression",
        metadata={"ct_val": 0.01},
    )

    close_trade = ledger.get_trade_log()[-1]

    assert ledger.get_position("BTC-USDT-SWAP").size == pytest.approx(0.0)
    assert close_trade["realized_pnl"] == pytest.approx(2.5)
    assert close_trade["net_realized_pnl"] == pytest.approx(2.5)
    assert ledger.get_equity() == pytest.approx(10_002.5)
