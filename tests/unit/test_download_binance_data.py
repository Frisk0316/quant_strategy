from scripts import download_binance_data as dl


def test_spot_symbols_use_binance_spot_klines_endpoint():
    cfg = dl.market_config_for_inst("BTC-USDT")

    assert cfg.base_url == "https://api.binance.com"
    assert cfg.endpoint == "/api/v3/klines"
    assert cfg.max_limit == 1000


def test_swap_symbols_keep_binance_futures_klines_endpoint():
    cfg = dl.market_config_for_inst("BTC-USDT-SWAP")

    assert cfg.base_url == "https://fapi.binance.com"
    assert cfg.endpoint == "/fapi/v1/klines"
    assert cfg.max_limit == 1500
