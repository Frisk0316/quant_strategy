"""Tests for stock minute-bar backtesting and order routing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pandas as pd
import pytest

from okx_quant.stocks import (
    MinuteBarBacktester,
    MinuteBacktestConfig,
    MovingAverageCrossStrategy,
    OrderSide,
    PaperStockBroker,
    StockFeeModel,
    StockMarket,
    StockOrder,
    StockOrderRouter,
    load_minute_bars,
)


def test_load_minute_bars_filters_us_regular_session(tmp_path):
    path = tmp_path / "aapl.csv"
    pd.DataFrame({
        "ts": [
            "2024-01-02 09:29:00",
            "2024-01-02 09:30:00",
            "2024-01-02 15:59:00",
            "2024-01-02 16:00:00",
        ],
        "open": [1, 2, 3, 4],
        "high": [1, 2, 3, 4],
        "low": [1, 2, 3, 4],
        "close": [1, 2, 3, 4],
        "volume": [10, 10, 10, 10],
    }).to_csv(path, index=False)

    bars = load_minute_bars(path, market=StockMarket.US, symbol="AAPL")

    assert len(bars) == 2
    assert list(bars["close"]) == [2, 3]
    assert str(bars.index.tz) == "America/New_York"


def test_minute_backtester_fills_signal_on_next_bar_open():
    idx = pd.date_range("2024-01-02 09:30", periods=5, freq="1min", tz="America/New_York")
    bars = pd.DataFrame({
        "symbol": ["AAPL"] * 5,
        "open": [10.0, 20.0, 30.0, 40.0, 50.0],
        "high": [10.0, 20.0, 30.0, 40.0, 50.0],
        "low": [10.0, 20.0, 30.0, 40.0, 50.0],
        "close": [10.0, 20.0, 30.0, 40.0, 50.0],
        "volume": [100, 100, 100, 100, 100],
    }, index=idx)

    result = MinuteBarBacktester(
        bars,
        strategy=MovingAverageCrossStrategy("AAPL", fast_window=1, slow_window=2),
        config=MinuteBacktestConfig(
            market=StockMarket.US,
            initial_cash=1_000.0,
            fee_model=StockFeeModel(),
            lot_size=1,
        ),
    ).run()

    assert not result.fills.empty
    first_fill = result.fills.iloc[0]
    assert first_fill["ts"] == idx[2]
    assert first_fill["price"] == 30.0
    assert first_fill["side"] == "buy"


def test_tw_fee_model_applies_commission_and_sell_tax():
    model = StockFeeModel(commission_rate=0.001425, min_commission=20.0, sell_tax_rate=0.003)

    buy_fee, buy_tax = model.estimate(OrderSide.BUY, price=100.0, quantity=1000)
    sell_fee, sell_tax = model.estimate(OrderSide.SELL, price=100.0, quantity=1000)

    assert buy_fee == pytest.approx(142.5)
    assert buy_tax == 0.0
    assert sell_fee == pytest.approx(142.5)
    assert sell_tax == pytest.approx(300.0)


@pytest.mark.asyncio
async def test_stock_order_router_dry_run_uses_paper_fill():
    order = StockOrder(
        symbol="2330",
        market=StockMarket.TW,
        side=OrderSide.BUY,
        quantity=1000,
        limit_price=600.0,
        strategy="unit",
    )
    router = StockOrderRouter(
        broker=PaperStockBroker(StockMarket.TW),
        market=StockMarket.TW,
        max_order_notional=1_000_000.0,
        dry_run=True,
    )

    fill = await router.submit(order)

    assert fill is not None
    assert fill.symbol == "2330"
    assert fill.price == 600.0


@pytest.mark.asyncio
async def test_stock_order_router_rejects_oversized_order():
    order = StockOrder(
        symbol="AAPL",
        market=StockMarket.US,
        side=OrderSide.BUY,
        quantity=100,
        limit_price=200.0,
    )
    router = StockOrderRouter(
        broker=PaperStockBroker(StockMarket.US),
        market=StockMarket.US,
        max_order_notional=10_000.0,
        dry_run=True,
    )

    with pytest.raises(ValueError, match="max_order_notional"):
        await router.submit(order)
