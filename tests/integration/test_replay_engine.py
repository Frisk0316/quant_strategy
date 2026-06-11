from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backtesting.replay import HistoricalEventFeed, ReplayBacktestEngine, run_replay_backtest
from okx_quant.core.config import StrategiesConfig
from okx_quant.core.events import MarketPayload
from okx_quant.execution.replay_execution import ReplayExecutionModel


def _market(ts: int, bid: float, ask: float, bid_sz: float = 5.0, ask_sz: float = 5.0):
    return MarketPayload(
        inst_id="BTC-USDT-SWAP",
        ts=ts,
        bids=[[str(bid), str(bid_sz)]],
        asks=[[str(ask), str(ask_sz)]],
        seq_id=0,
        channel="books",
    )


def _order(cl_ord_id: str = "order-1", px: str = "100.0"):
    return {
        "cl_ord_id": cl_ord_id,
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "sz": "1",
        "px": px,
        "strategy": "test",
        "metadata": {},
    }


def test_empty_feed_raises_or_warns(minimal_cfg):
    engine = ReplayBacktestEngine(minimal_cfg, strategy_names=["as_market_maker"])
    feed = HistoricalEventFeed(pd.DataFrame(), pd.DataFrame())

    with pytest.raises(ValueError, match="empty historical feed"):
        engine.run_sync(feed)


def test_minimal_candles_produce_orders(minimal_cfg, btc_parquet_dir):
    result = run_replay_backtest(
        strategy_names=["as_market_maker"],
        cfg=minimal_cfg,
        data_dir=str(btc_parquet_dir),
        bar="1H",
    )

    assert len(result.order_log) > 0


def test_funding_carry_settles_correctly(minimal_cfg, btc_parquet_dir):
    result = run_replay_backtest(
        strategy_names=["funding_carry"],
        cfg=minimal_cfg,
        data_dir=str(btc_parquet_dir),
        bar="1H",
    )

    assert len(result.funding_log) >= 1
    assert result.funding_log["cashflow"].sum() > 0
    first = result.funding_log.iloc[0]
    expected = abs(first["position_size"]) * first["mark_price"] * first["ct_val"] * first["rate"]
    assert first["cashflow"] == pytest.approx(expected)


def test_zero_latency_vs_realistic_latency_fill_rate():
    zero = ReplayExecutionModel(
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}},
        order_latency_ms=0,
        queue_fill_fraction=1.0,
    )
    realistic = ReplayExecutionModel(
        instrument_specs={"BTC-USDT-SWAP": {"ctVal": 0.01}},
        order_latency_ms=100,
        queue_fill_fraction=1.0,
    )
    zero.on_market(_market(1_000, 99.0, 101.0))
    realistic.on_market(_market(1_000, 99.0, 101.0))
    zero.submit(_order("zero"))
    realistic.submit(_order("realistic"))

    zero_fills = zero.on_market(_market(1_050, 99.0, 99.5))
    realistic_early = realistic.on_market(_market(1_050, 99.0, 99.5))
    realistic_late = realistic.on_market(_market(1_101, 99.0, 99.5))

    assert len(zero_fills) == 1
    assert realistic_early == []
    assert len(realistic_late) == 1


def test_risk_guard_blocks_are_visible_in_replay_result(minimal_cfg, btc_parquet_dir):
    cfg = minimal_cfg.model_copy(deep=True)
    cfg.risk.stale_quote_pct = 0.001

    result = run_replay_backtest(
        strategy_names=["as_market_maker"],
        cfg=cfg,
        data_dir=str(btc_parquet_dir),
        bar="1H",
    )

    assert result.rejected_log
    assert result.rejected_log[0]["reason"] == "stale_quote"
    assert result.risk_event_log


def test_replay_records_allowed_reduce_only_bypass_event(minimal_cfg, tmp_path: Path):
    cfg = minimal_cfg.model_copy(deep=True)
    cfg.strategies.ma_crossover.fast_window = 2
    cfg.strategies.ma_crossover.slow_window = 3
    cfg.strategies.ma_crossover.symbols = ["BTC-USDT-SWAP"]
    cfg.system.symbols = ["BTC-USDT-SWAP"]
    cfg.risk.max_order_notional_usd = 50_000.0
    cfg.risk.max_pos_pct_equity = 0.80
    cfg.backtest.order_latency_ms = 0
    cfg.backtest.cancel_latency_ms = 0
    cfg.backtest.queue_fill_fraction = 1.0

    data_dir = tmp_path / "ticks"
    inst_dir = data_dir / "BTC_USDT_SWAP"
    inst_dir.mkdir(parents=True)
    prices = [10_000, 9_000, 8_000, 20_000, 19_000, 50_000, 49_000, 48_000, 47_000]
    ts = pd.date_range("2024-01-01", periods=len(prices), freq="1h", tz="UTC")
    pd.DataFrame({
        "ts": ts,
        "open": prices,
        "high": [price * 1.01 for price in prices],
        "low": [price * 0.99 for price in prices],
        "close": prices,
        "vol": [100_000] * len(prices),
    }).to_parquet(inst_dir / "candles_1H.parquet", index=False)

    result = run_replay_backtest(
        strategy_names=["ma_crossover"],
        cfg=cfg,
        data_dir=str(data_dir),
        bar="1H",
    )

    risk_events = (
        result.risk_event_log.to_dict("records")
        if hasattr(result.risk_event_log, "to_dict")
        else list(result.risk_event_log)
    )
    assert risk_events
    reasons = {event["reason"] for event in risk_events}
    assert "allowed_reduce_only_bypass:position_limit" in reasons
    event = next(
        item for item in risk_events
        if item["reason"] == "allowed_reduce_only_bypass:position_limit"
    )
    assert event["strategy"] == "ma_crossover"
    assert event["side"] == "sell"
    assert event["metadata"]["reduce_only"] is True


def test_replay_default_specs_reject_non_btc_eth_pairs_without_metadata(minimal_cfg):
    cfg = minimal_cfg.model_copy(deep=True)
    cfg.strategies = StrategiesConfig(
        pairs_trading={
            "enabled": True,
            "symbol_y": "FOO-USDT-SWAP",
            "symbol_x": "BAR-USDT-SWAP",
        }
    )

    with pytest.raises(ValueError, match="Missing ctVal for swap"):
        ReplayBacktestEngine(cfg, strategy_names=["pairs_trading"])
