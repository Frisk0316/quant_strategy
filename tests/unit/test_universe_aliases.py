import hashlib

import pandas as pd

from backtesting.universe_aliases import collapse_same_asset_aliases


def test_binance_alias_collapse_preserves_membership_parquet_bytes(tmp_path):
    membership_path = tmp_path / "universe_membership.parquet"
    pd.DataFrame(
        [
            {"symbol": "BTC-USDT-SWAP"},
            {"symbol": "SHIB-USDT-SWAP"},
            {"symbol": "ETH-USDT-SWAP"},
            {"symbol": "1000SHIB-USDT-SWAP"},
        ]
    ).to_parquet(membership_path, index=False)
    before = hashlib.sha256(membership_path.read_bytes()).hexdigest()

    symbols = pd.read_parquet(membership_path)["symbol"]
    collapsed = collapse_same_asset_aliases(symbols, exchange="binance")

    assert collapsed == (
        "BTC-USDT-SWAP",
        "1000SHIB-USDT-SWAP",
        "ETH-USDT-SWAP",
    )
    assert collapse_same_asset_aliases(symbols, exchange="okx") == tuple(symbols)
    assert hashlib.sha256(membership_path.read_bytes()).hexdigest() == before
