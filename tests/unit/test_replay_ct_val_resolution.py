import pytest

from backtesting.replay import ReplayBacktestEngine as E


def test_db_specs_win_and_report_db():
    db = {"BTC-USDT-SWAP": {"ct_val": 0.01}}
    assert E._resolve_swap_ct_val("BTC-USDT-SWAP", "okx", db) == (0.01, "db")


def test_binance_base_unit_must_be_seeded_not_okx_fallback():
    with pytest.raises(ValueError):
        E._resolve_swap_ct_val("BTC-USDT-SWAP", "binance", None)


def test_binance_seeded_value_used():
    db = {"BTC-USDT-SWAP": {"ct_val": 1.0}}
    assert E._resolve_swap_ct_val("BTC-USDT-SWAP", "binance", db) == (1.0, "db")


def test_okx_registry_fallback_still_works():
    val, src = E._resolve_swap_ct_val("BTC-USDT-SWAP", "okx", None)
    assert (val, src) == (0.01, "registry")


def test_default_exchange_is_okx_for_backcompat():
    val, src = E._resolve_swap_ct_val("BTC-USDT-SWAP", db_specs=None)
    assert src == "registry" and val == 0.01
