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


@pytest.mark.parametrize("bad_ct_val", [float("inf"), float("nan"), 1e8, 0.0, -1.0])
def test_on_fill_rejects_invalid_explicit_ct_val(bad_ct_val):
    """R1.5/I34: explicitly provided ct_val must pass the shared validator."""
    ledger = PositionLedger(initial_equity=10_000.0)
    positions_before = ledger.get_all_positions()
    trades_before = ledger.get_trade_log()
    equity_before = ledger.get_equity()

    with pytest.raises(ValueError):
        ledger.on_fill(
            "BTC-USDT-SWAP",
            "buy",
            fill_px=40_000.0,
            fill_sz=0.25,
            fee=0.0,
            metadata={"ct_val": bad_ct_val},
        )

    assert ledger.get_all_positions() == positions_before
    assert ledger.get_trade_log() == trades_before
    assert ledger.get_equity() == equity_before


@pytest.mark.parametrize("bad_ct_val", [float("inf"), float("nan"), 1e8, 0.0, -1.0])
def test_on_fill_rejects_invalid_existing_ct_val_fallback(bad_ct_val):
    ledger = PositionLedger(initial_equity=10_000.0)
    ledger.on_fill(
        "BTC-USDT-SWAP",
        "buy",
        fill_px=40_000.0,
        fill_sz=0.25,
        fee=0.0,
        metadata={"ct_val": 0.01},
    )
    position = ledger.get_position("BTC-USDT-SWAP")
    position.ct_val = bad_ct_val
    size_before = position.size
    trades_before = ledger.get_trade_log()

    with pytest.raises(ValueError):
        ledger.on_fill("BTC-USDT-SWAP", "buy", fill_px=41_000.0, fill_sz=0.25, fee=0.0)

    assert position.size == size_before
    assert ledger.get_trade_log() == trades_before


def test_on_fill_missing_ct_val_uses_fallback():
    ledger = PositionLedger(initial_equity=10_000.0)

    ledger.on_fill("BTC-USDT-SWAP", "buy", fill_px=100.0, fill_sz=1.0, fee=0.0)
    ledger.on_fill("BTC-USDT-SWAP", "buy", fill_px=100.0, fill_sz=1.0, fee=0.0, metadata={})
    ledger.on_fill(
        "BTC-USDT-SWAP", "buy", fill_px=100.0, fill_sz=1.0, fee=0.0, metadata={"ct_val": None}
    )

    assert ledger.get_position("BTC-USDT-SWAP").ct_val == pytest.approx(1.0)
