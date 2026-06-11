import pytest
import pandas as pd

from okx_quant.core.events import Event, EvtType, FillPayload, MarketPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.strategies.technical_indicators import (
    EMACrossoverStrategy,
    MACDCrossoverStrategy,
    MACrossoverStrategy,
)


def _book(symbol: str, mid: float) -> OkxBook:
    book = OkxBook(symbol)
    book.bids[mid - 0.5] = (str(mid - 0.5), "100")
    book.asks[mid + 0.5] = (str(mid + 0.5), "100")
    return book


def _event(symbol: str, ts: int = 1) -> Event:
    return Event(
        EvtType.MARKET,
        payload=MarketPayload(
            inst_id=symbol,
            ts=ts,
            bids=[],
            asks=[],
            seq_id=0,
            channel="books",
        ),
    )


async def _feed(strategy, symbol: str, prices: list[float]):
    signals = []
    for i, price in enumerate(prices, start=1):
        signal = await strategy.on_market(_event(symbol, i), _book(symbol, price))
        if signal:
            signals.append(signal)
            if signal.side == "buy":
                await strategy.on_fill(Event(
                    EvtType.FILL,
                    payload=FillPayload(
                        cl_ord_id=f"fill-{i}",
                        ord_id=f"fill-{i}",
                        inst_id=symbol,
                        fill_px=price,
                        fill_sz=1.0,
                        fee=0.0,
                        fee_ccy="USDT",
                        side="buy",
                        ts=i,
                        strategy=strategy.name,
                    ),
                ))
    return signals


@pytest.mark.asyncio
async def test_ma_crossover_warms_up_then_emits_entry_and_exit():
    strategy = MACrossoverStrategy({"symbols": ["BTC-USDT-SWAP"], "fast_window": 2, "slow_window": 3})

    first = await _feed(strategy, "BTC-USDT-SWAP", [3, 2])
    assert first == []

    signals = await _feed(strategy, "BTC-USDT-SWAP", [1, 2, 5, 4, 2, 1])

    assert [s.side for s in signals] == ["buy", "sell"]
    assert signals[0].metadata["action"] == "entry"
    assert signals[1].metadata["action"] == "exit"
    assert signals[1].metadata["cancel_existing"] is True


@pytest.mark.asyncio
async def test_long_flat_exit_stays_in_position_until_exit_order_is_filled():
    strategy = MACrossoverStrategy({"symbols": ["BTC-USDT-SWAP"], "fast_window": 2, "slow_window": 3})
    strategy._in_position["BTC-USDT-SWAP"] = True

    await strategy.on_fill(Event(
        EvtType.FILL,
        payload=FillPayload(
            cl_ord_id="partial-exit",
            ord_id="partial-exit",
            inst_id="BTC-USDT-SWAP",
            fill_px=100.0,
            fill_sz=0.5,
            fee=0.0,
            fee_ccy="USDT",
            side="sell",
            ts=1,
            strategy=strategy.name,
            state="partially_filled",
            metadata={"remaining_sz": 0.5},
        ),
    ))

    assert strategy._in_position["BTC-USDT-SWAP"] is True

    await strategy.on_fill(Event(
        EvtType.FILL,
        payload=FillPayload(
            cl_ord_id="filled-exit",
            ord_id="filled-exit",
            inst_id="BTC-USDT-SWAP",
            fill_px=100.0,
            fill_sz=0.5,
            fee=0.0,
            fee_ccy="USDT",
            side="sell",
            ts=2,
            strategy=strategy.name,
            state="filled",
            metadata={"remaining_sz": 0.0},
        ),
    ))

    assert strategy._in_position["BTC-USDT-SWAP"] is False


@pytest.mark.asyncio
async def test_ema_crossover_emits_entry_after_warmup():
    strategy = EMACrossoverStrategy({"symbols": ["BTC-USDT-SWAP"], "fast_span": 2, "slow_span": 4})

    signals = await _feed(strategy, "BTC-USDT-SWAP", [5, 4, 3, 2, 3, 5, 8])

    assert any(s.side == "buy" for s in signals)
    assert all(s.metadata["mode"] == "long_flat" for s in signals)


@pytest.mark.asyncio
async def test_macd_crossover_emits_entry_after_warmup():
    strategy = MACDCrossoverStrategy({
        "symbols": ["BTC-USDT-SWAP"],
        "fast_span": 3,
        "slow_span": 6,
        "signal_span": 3,
    })

    prices = [10, 9, 8, 7, 6, 5, 4, 3, 2, 2, 3, 5, 8, 12, 15]
    signals = await _feed(strategy, "BTC-USDT-SWAP", prices)

    assert any(s.side == "buy" for s in signals)


def test_ema_crossover_incremental_values_match_full_series_after_long_run():
    strategy = EMACrossoverStrategy({
        "symbols": ["BTC-USDT-SWAP"],
        "fast_span": 20,
        "slow_span": 50,
    })
    prices = [100.0 + (idx % 17) * 0.3 - idx * 0.02 for idx in range(260)]

    fast = slow = 0.0
    for price in prices:
        fast, slow, _ = strategy._indicator_values("BTC-USDT-SWAP", price, [])

    series = pd.Series(prices, dtype=float)
    assert fast == pytest.approx(series.ewm(span=20, adjust=False).mean().iloc[-1])
    assert slow == pytest.approx(series.ewm(span=50, adjust=False).mean().iloc[-1])


def test_macd_crossover_incremental_values_match_full_series_after_long_run():
    strategy = MACDCrossoverStrategy({
        "symbols": ["BTC-USDT-SWAP"],
        "fast_span": 12,
        "slow_span": 26,
        "signal_span": 9,
    })
    prices = [100.0 + (idx % 23) * 0.4 - idx * 0.01 for idx in range(220)]

    macd_value = signal_value = 0.0
    for price in prices:
        macd_value, signal_value, _ = strategy._indicator_values("BTC-USDT-SWAP", price, [])

    series = pd.Series(prices, dtype=float)
    fast = series.ewm(span=12, adjust=False).mean()
    slow = series.ewm(span=26, adjust=False).mean()
    macd = fast - slow
    signal = macd.ewm(span=9, adjust=False).mean()
    assert macd_value == pytest.approx(macd.iloc[-1])
    assert signal_value == pytest.approx(signal.iloc[-1])


def test_invalid_fast_slow_params_are_rejected():
    with pytest.raises(ValueError):
        MACrossoverStrategy({"fast_window": 50, "slow_window": 20})
    with pytest.raises(ValueError):
        EMACrossoverStrategy({"fast_span": 50, "slow_span": 20})
    with pytest.raises(ValueError):
        MACDCrossoverStrategy({"fast_span": 26, "slow_span": 12, "signal_span": 9})


@pytest.mark.asyncio
async def test_multi_symbol_state_does_not_leak_between_symbols():
    strategy = MACrossoverStrategy({
        "symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        "fast_window": 2,
        "slow_window": 3,
    })

    btc_signals = await _feed(strategy, "BTC-USDT-SWAP", [3, 2, 1, 2, 5])
    eth_signals = await _feed(strategy, "ETH-USDT-SWAP", [100, 99])

    assert [s.inst_id for s in btc_signals] == ["BTC-USDT-SWAP"]
    assert eth_signals == []
