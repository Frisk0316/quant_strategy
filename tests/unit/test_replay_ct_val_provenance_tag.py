from backtesting.replay import _attach_ct_val_provenance


class _FakeEngine:
    _ct_val_sources = {
        "BTC-USDT-SWAP": {"value": 1.0, "source": "db", "exchange": "binance"}
    }


class _Result:
    validation = {}


def test_provenance_carries_run_exchange():
    result = _Result()
    _attach_ct_val_provenance(result, _FakeEngine())

    assert result.validation["ct_val_all_authoritative"] is True
    assert result.validation["exchange"] == "binance"
    assert result.validation["ct_val_sources"]["BTC-USDT-SWAP"]["exchange"] == "binance"
