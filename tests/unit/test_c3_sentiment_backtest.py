from __future__ import annotations

import asyncio

import pandas as pd

from okx_quant.core.events import Event, EvtType, FeaturePayload, FillPayload, MarketPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.strategies.external_features import FearGreedSentimentStrategy


def _ms(value: str) -> int:
    return int(pd.Timestamp(value, tz="UTC").timestamp() * 1000)


def _close(days: int = 6) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=days * 24, freq="h")
    return pd.DataFrame({"BTC-USDT-SWAP": pd.Series(100.0, index=idx)})


def _funding(index: pd.DatetimeIndex, rate: float = 0.0) -> pd.DataFrame:
    return pd.DataFrame({"BTC-USDT-SWAP": rate}, index=index)


def _fng(rows: list[tuple[str, float, str]]) -> pd.DataFrame:
    observed = pd.to_datetime([day for day, _, _ in rows], utc=True)
    return pd.DataFrame({
        "dataset_id": "fear_greed_btc",
        "observed_at": observed,
        "published_at": observed,
        "value_num": [value for _, value, _ in rows],
        "value_text": [label for _, _, label in rows],
    })


def test_c3_sentiment_trades_next_day_not_same_day_feature():
    from backtesting.c3_sentiment_backtest import C3SentimentParams, run_c3_sentiment_backtest

    close = _close()
    fng = _fng([("2024-01-03", 10.0, "Extreme Fear")])
    result = run_c3_sentiment_backtest(
        close,
        _funding(close.index),
        fng,
        C3SentimentParams(fee_bps=0.0, slippage_bps=0.0),
    )

    assert result.positions.loc["2024-01-03"].abs().sum(axis=1).max() == 0.0
    assert result.positions.loc["2024-01-04"].iloc[1]["BTC-USDT-SWAP"] > 0.0


def test_c3_sentiment_vectorized_logic_matches_event_strategy_entry_hold_exit():
    from backtesting.c3_sentiment_backtest import C3SentimentParams, run_c3_sentiment_backtest

    rows = [
        ("2024-01-01", 10.0, "Extreme Fear"),
        ("2024-01-02", 35.0, "Fear"),
        ("2024-01-03", 50.0, "Neutral"),
        ("2024-01-04", 60.0, "Greed"),
    ]
    close = _close()
    result = run_c3_sentiment_backtest(
        close,
        _funding(close.index),
        _fng(rows),
        C3SentimentParams(fee_bps=0.0, slippage_bps=0.0),
    )

    strategy = FearGreedSentimentStrategy({"max_age_seconds": 172800})
    states = []
    for day, value, label in rows:
        feature = FeaturePayload(
            dataset_id="fear_greed_btc",
            ts=_ms(day),
            observed_at=_ms(day),
            published_at=_ms(day),
            value_num=value,
            value_text=label,
        )
        asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=feature)))
        market = MarketPayload(
            inst_id="BTC-USDT-SWAP",
            ts=_ms(f"{day} 01:00"),
            bids=[["99", "1"]],
            asks=[["101", "1"]],
            seq_id=0,
            channel="books",
        )
        book = OkxBook("BTC-USDT-SWAP")
        book.bids[99.0] = ("99", "1")
        book.asks[101.0] = ("101", "1")
        signal = asyncio.run(strategy.on_market(Event(EvtType.MARKET, payload=market), book))
        if signal is not None:
            asyncio.run(strategy.on_fill(Event(EvtType.FILL, payload=FillPayload(
                cl_ord_id="c1",
                ord_id="o1",
                inst_id="BTC-USDT-SWAP",
                fill_px=100.0,
                fill_sz=1.0,
                fee=0.0,
                fee_ccy="USDT",
                side=signal.side,
                ts=_ms(day),
                strategy=strategy.name,
                state="filled",
                metadata={"remaining_sz": 0.0},
            ))))
        states.append(1.0 if strategy._in_position else 0.0)

    got = result.target_weights["BTC-USDT-SWAP"].reindex(pd.to_datetime([row[0] for row in rows])).tolist()
    assert got == states == [1.0, 1.0, 1.0, 0.0]


def test_c3_long_pays_positive_funding():
    from backtesting.c3_sentiment_backtest import C3SentimentParams, run_c3_sentiment_backtest

    close = _close()
    result = run_c3_sentiment_backtest(
        close,
        _funding(close.index, rate=0.01),
        _fng([("2024-01-01", 10.0, "Extreme Fear")]),
        C3SentimentParams(fee_bps=0.0, slippage_bps=0.0),
    )

    assert result.positions["BTC-USDT-SWAP"].max() > 0.0
    assert result.metrics["funding_cashflow"] < 0.0
