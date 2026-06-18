import pytest

from backtesting.replay import ReplayBacktestEngine as E


def test_db_specs_win_and_report_db():
    db = {"BTC-USDT-SWAP": {"ct_val": 0.01}}
    assert E._resolve_swap_ct_val("BTC-USDT-SWAP", "okx", db) == (0.01, "db")


def test_binance_usdt_m_perp_uses_exchange_base_unit():
    assert E._resolve_swap_ct_val("BNB-USDT-SWAP", "binance", None) == (1.0, "exchange_base_unit")


def test_bybit_usdt_m_perp_uses_exchange_base_unit():
    assert E._resolve_swap_ct_val("SOL-USDT-SWAP", "bybit", None) == (1.0, "exchange_base_unit")


def test_binance_seeded_value_used():
    db = {"BTC-USDT-SWAP": {"ct_val": 1.0}}
    assert E._resolve_swap_ct_val("BTC-USDT-SWAP", "binance", db) == (1.0, "db")


def test_db_override_wins_for_binance():
    db = {"X": {"ct_val": 1000.0}}
    assert E._resolve_swap_ct_val("X", "binance", db) == (1000.0, "db")


def test_binance_multiplier_contract_requires_db_row():
    with pytest.raises(ValueError):
        E._resolve_swap_ct_val("1000SHIB-USDT-SWAP", "binance", None)


def test_okx_registry_fallback_still_works():
    val, src = E._resolve_swap_ct_val("BTC-USDT-SWAP", "okx", None)
    assert (val, src) == (0.01, "registry")


def test_default_exchange_is_okx_for_backcompat():
    val, src = E._resolve_swap_ct_val("BTC-USDT-SWAP", db_specs=None)
    assert src == "registry" and val == 0.01


def test_exchange_base_unit_is_authoritative():
    assert "exchange_base_unit" in E.AUTHORITATIVE_CT_VAL_SOURCES
