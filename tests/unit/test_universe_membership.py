from datetime import date

import pandas as pd

from scripts.build_universe_membership import (
    build_membership,
    daily_dollar_volume_rows_to_candles,
    load_candles_from_db,
)


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


def test_daily_dollar_volume_rows_to_candles_drops_partial_days():
    rows = [
        {"inst_id": "BTC-USDT-SWAP", "day": date(2024, 1, 1), "dollar_volume": 5_000_000.0, "bar_count": 1440},
        {"inst_id": "BTC-USDT-SWAP", "day": date(2024, 1, 2), "dollar_volume": 100.0, "bar_count": 3},
    ]

    candles = daily_dollar_volume_rows_to_candles(rows, min_bar_count=1000)

    assert list(candles) == ["BTC-USDT-SWAP"]
    frame = candles["BTC-USDT-SWAP"]
    assert len(frame) == 1
    assert frame["vol"].iloc[0] == 5_000_000.0
    assert frame["close"].iloc[0] == 1.0


def test_db_and_parquet_sources_feed_the_same_build_membership():
    """P9 acceptance: DB-sourced candles must drive build_membership() (the
    eligibility formula) exactly the same way parquet-sourced ones do -
    only the candle-loading path differs."""
    parquet_candles = {"BTC-USDT-SWAP": _ramp("2024-01-01", 60)}

    db_rows = [
        {"inst_id": "BTC-USDT-SWAP", "day": (pd.Timestamp("2024-01-01") + pd.Timedelta(days=i)).date(),
         "dollar_volume": 100.0 * 1e6, "bar_count": 1440}
        for i in range(60)
    ]

    async def fake_fetch_rows(dsn, *, bar, source_primary, inst_id_pattern):
        assert dsn == "postgresql://fake"
        assert bar == "1m"
        assert source_primary == "binance"
        return db_rows

    db_candles = load_candles_from_db(
        "postgresql://fake",
        source_primary="binance",
        fetch_rows=fake_fetch_rows,
    )

    cfg = {"top_n": 10, "min_adv_usd": 0.0, "warmup_days": 30}
    from_parquet = build_membership(parquet_candles, cfg)
    from_db = build_membership(db_candles, cfg)

    pd.testing.assert_frame_equal(
        from_parquet.reset_index(drop=True), from_db.reset_index(drop=True)
    )


def test_daily_dollar_volume_rows_to_candles_ignores_zero_bar_count_rows():
    rows = [
        {"inst_id": "ETH-USDT-SWAP", "day": date(2024, 1, 1), "dollar_volume": 0.0, "bar_count": 0},
    ]

    candles = daily_dollar_volume_rows_to_candles(rows, min_bar_count=1000)

    assert candles == {}
