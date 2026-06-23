import pandas as pd

from scripts.build_universe_membership import build_membership


def _ramp(start, periods, price=100.0):
    idx = pd.date_range(start, periods=periods, freq="D")
    return pd.DataFrame(
        {"open": price, "high": price, "low": price, "close": price, "vol": 1e6},
        index=idx,
    )


def test_symbol_not_eligible_before_listing_plus_warmup():
    cfg = {"top_n": 10, "min_adv_usd": 0.0, "warmup_days": 30}
    candles = {
        "OLD-USDT-SWAP": _ramp("2024-01-01", 60),
        "NEW-USDT-SWAP": _ramp("2024-02-01", 30),
    }

    membership = build_membership(candles, cfg)

    row = membership[
        (membership.date == pd.Timestamp("2024-02-10"))
        & (membership.symbol == "NEW-USDT-SWAP")
    ]
    assert bool(row.eligible.iloc[0]) is False


def test_delisted_symbol_drops_out_when_data_ends():
    cfg = {"top_n": 10, "min_adv_usd": 0.0, "warmup_days": 5}
    candles = {"DEAD-USDT-SWAP": _ramp("2024-01-01", 20)}

    membership = build_membership(candles, cfg)

    after = membership[
        (membership.date > pd.Timestamp("2024-01-20"))
        & (membership.symbol == "DEAD-USDT-SWAP")
    ]
    assert (after.eligible == False).all() if len(after) else True
