from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from okx_quant.core.events import Event, EvtType, FeaturePayload, FillPayload, MarketPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.strategies.external_features import CMEGapFillStrategy, FearGreedSentimentStrategy
from backtesting.replay import HistoricalEventFeed, _synthetic_l1_from_candles


def _ms(value: str) -> int:
    import pandas as pd

    return int(pd.Timestamp(value, tz="UTC").timestamp() * 1000)


def _book(price: float) -> OkxBook:
    book = OkxBook("BTC-USDT-SWAP")
    book.bids[price - 1] = (str(price - 1), "1")
    book.asks[price + 1] = (str(price + 1), "1")
    return book


def _market(ts: int, price: float = 100.0) -> tuple[Event, OkxBook]:
    payload = MarketPayload(
        inst_id="BTC-USDT-SWAP",
        ts=ts,
        bids=[[str(price - 1), "1"]],
        asks=[[str(price + 1), "1"]],
        seq_id=0,
        channel="books",
    )
    return Event(EvtType.MARKET, payload=payload), _book(price)


def _fill(strategy: str, side: str, action: str) -> Event:
    return Event(EvtType.FILL, payload=FillPayload(
        cl_ord_id="c1",
        ord_id="o1",
        inst_id="BTC-USDT-SWAP",
        fill_px=100.0,
        fill_sz=1.0,
        fee=0.0,
        fee_ccy="USDT",
        side=side,
        ts=_ms("2024-01-01"),
        strategy=strategy,
        state="filled",
        metadata={"action": action},
    ))


def test_fear_greed_generates_entry_and_exit():
    strategy = FearGreedSentimentStrategy({"max_age_seconds": 172800})
    feature = FeaturePayload(
        dataset_id="fear_greed_btc",
        ts=_ms("2024-01-01"),
        observed_at=_ms("2024-01-01"),
        published_at=_ms("2024-01-01"),
        value_num=17.0,
        value_text=" extreme fear ",
    )

    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=feature)))
    event, book = _market(_ms("2024-01-01 01:00"), 100.0)
    signal = asyncio.run(strategy.on_market(event, book))

    assert signal.side == "buy"
    assert signal.metadata["action"] == "entry"

    asyncio.run(strategy.on_fill(_fill(strategy.name, "buy", "entry")))
    feature.value_text = "Greed"
    feature.ts = _ms("2024-01-02")
    feature.observed_at = _ms("2024-01-02")
    feature.published_at = _ms("2024-01-02")
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=feature)))
    event, book = _market(_ms("2024-01-02 01:00"), 110.0)
    exit_signal = asyncio.run(strategy.on_market(event, book))

    assert exit_signal.side == "sell"
    assert exit_signal.metadata["action"] == "exit"


def test_fear_greed_stale_feature_blocks_signal():
    strategy = FearGreedSentimentStrategy({"max_age_seconds": 3600})
    feature = FeaturePayload(
        dataset_id="fear_greed_btc",
        ts=_ms("2024-01-01"),
        observed_at=_ms("2024-01-01"),
        published_at=_ms("2024-01-01"),
        value_text="Extreme Fear",
    )
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=feature)))
    event, book = _market(_ms("2024-01-01 03:00"), 100.0)

    assert asyncio.run(strategy.on_market(event, book)) is None
    assert strategy.coverage_status["stale_no_signal_count"] == 1


def test_cme_gap_fill_detects_up_gap_short_and_exits_on_target():
    strategy = CMEGapFillStrategy({"min_gap_bps": 10, "max_hold_days": 5, "allow_direction": "both"})
    friday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-05"),
        observed_at=_ms("2024-01-05"),
        published_at=_ms("2024-01-05"),
        fields={"open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0},
    )
    monday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-08"),
        observed_at=_ms("2024-01-08"),
        published_at=_ms("2024-01-08"),
        fields={"open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0},
    )
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=monday)))

    event, book = _market(_ms("2024-01-08 01:00"), 102.0)
    entry = asyncio.run(strategy.on_market(event, book))

    assert entry.side == "sell"
    assert entry.metadata["gap_direction"] == "short"
    assert entry.metadata["cme_target_price"] == 100.0
    assert entry.metadata["okx_entry_anchor_price"] == 102.0
    assert entry.metadata["okx_target_price"] == 102.0 * (1.0 - 0.02)

    asyncio.run(strategy.on_fill(_fill(strategy.name, "sell", "entry")))
    event, book = _market(_ms("2024-01-08 02:00"), 99.5)
    exit_signal = asyncio.run(strategy.on_market(event, book))

    assert exit_signal.side == "buy"
    assert exit_signal.metadata["reason"] == "target_fill"


def test_cme_gap_fill_does_not_repeat_exit_signal_while_exit_order_pending():
    strategy = CMEGapFillStrategy({"min_gap_bps": 10, "max_hold_days": 5, "allow_direction": "both"})
    friday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-05"),
        observed_at=_ms("2024-01-05"),
        published_at=_ms("2024-01-05"),
        fields={"open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0},
    )
    monday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-08"),
        observed_at=_ms("2024-01-08"),
        published_at=_ms("2024-01-08"),
        fields={"open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0},
    )
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=monday)))

    event, book = _market(_ms("2024-01-08 01:00"), 102.0)
    asyncio.run(strategy.on_market(event, book))
    asyncio.run(strategy.on_fill(_fill(strategy.name, "sell", "entry")))

    event, book = _market(_ms("2024-01-08 02:00"), 99.5)
    first_exit = asyncio.run(strategy.on_market(event, book))
    event, book = _market(_ms("2024-01-08 03:00"), 99.0)
    repeated_exit = asyncio.run(strategy.on_market(event, book))

    assert first_exit is not None
    assert first_exit.metadata["reason"] == "target_fill"
    assert repeated_exit is None


def test_cme_gap_fill_stop_loss_exits_short_when_adverse_threshold_hit():
    strategy = CMEGapFillStrategy({
        "min_gap_bps": 10,
        "max_hold_days": 5,
        "stop_loss_bps_mult": 1.5,
        "allow_direction": "both",
    })
    friday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-05"),
        observed_at=_ms("2024-01-05"),
        published_at=_ms("2024-01-05"),
        fields={"open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0},
    )
    monday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-08"),
        observed_at=_ms("2024-01-08"),
        published_at=_ms("2024-01-08"),
        fields={"open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0},
    )
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=monday)))

    event, book = _market(_ms("2024-01-08 01:00"), 102.0)
    entry = asyncio.run(strategy.on_market(event, book))
    asyncio.run(strategy.on_fill(_fill(strategy.name, "sell", "entry")))

    event, book = _market(_ms("2024-01-08 02:00"), 106.0)
    exit_signal = asyncio.run(strategy.on_market(event, book))

    assert entry.metadata["stop_loss_price"] == pytest.approx(102.0 * 1.03)
    assert exit_signal.side == "buy"
    assert exit_signal.metadata["reason"] == "stop_loss"


def test_cme_gap_fill_respects_max_gap_bps_filter():
    strategy = CMEGapFillStrategy({
        "min_gap_bps": 10,
        "max_gap_bps": 100,
        "max_hold_days": 5,
    })
    friday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-05"),
        observed_at=_ms("2024-01-05"),
        published_at=_ms("2024-01-05"),
        fields={"open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0},
    )
    monday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-08"),
        observed_at=_ms("2024-01-08"),
        published_at=_ms("2024-01-08"),
        fields={"open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0},
    )
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=monday)))
    event, book = _market(_ms("2024-01-08 01:00"), 102.0)

    assert asyncio.run(strategy.on_market(event, book)) is None
    assert strategy.coverage_status["max_gap_skip_count"] == 1


def test_cme_gap_fill_long_only_skips_up_gaps():
    strategy = CMEGapFillStrategy({
        "min_gap_bps": 10,
        "allow_direction": "long_only",
        "max_hold_days": 5,
    })
    friday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-05"),
        observed_at=_ms("2024-01-05"),
        published_at=_ms("2024-01-05"),
        fields={"open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0},
    )
    monday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-08"),
        observed_at=_ms("2024-01-08"),
        published_at=_ms("2024-01-08"),
        fields={"open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0},
    )
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=monday)))
    event, book = _market(_ms("2024-01-08 01:00"), 102.0)

    assert asyncio.run(strategy.on_market(event, book)) is None
    assert strategy.coverage_status["direction_skip_count"] == 1


def test_cme_gap_fill_default_max_hold_days_is_two_days():
    strategy = CMEGapFillStrategy({"min_gap_bps": 10})
    friday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-05"),
        observed_at=_ms("2024-01-05"),
        published_at=_ms("2024-01-05"),
        fields={"open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0},
    )
    monday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-08"),
        observed_at=_ms("2024-01-08"),
        published_at=_ms("2024-01-08"),
        fields={"open": 98.0, "high": 99.0, "low": 97.0, "close": 98.0},
    )
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=monday)))
    event, book = _market(_ms("2024-01-08 01:00"), 98.0)
    entry = asyncio.run(strategy.on_market(event, book))

    assert entry.metadata["expires_at"] - monday.ts == 2 * 86400 * 1000


def test_cme_gap_fill_default_skips_up_gaps_and_trades_down_gaps():
    up_strategy = CMEGapFillStrategy({"min_gap_bps": 10})
    friday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-05"),
        observed_at=_ms("2024-01-05"),
        published_at=_ms("2024-01-05"),
        fields={"open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0},
    )
    monday_up = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-08"),
        observed_at=_ms("2024-01-08"),
        published_at=_ms("2024-01-08"),
        fields={"open": 102.0, "high": 103.0, "low": 101.0, "close": 102.0},
    )
    asyncio.run(up_strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(up_strategy.on_market(Event(EvtType.FEATURE, payload=monday_up)))
    event, book = _market(_ms("2024-01-08 01:00"), 102.0)

    assert asyncio.run(up_strategy.on_market(event, book)) is None
    assert up_strategy.coverage_status["direction_skip_count"] == 1
    assert up_strategy._active_gap is None

    down_strategy = CMEGapFillStrategy({"min_gap_bps": 10})
    monday_down = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-08"),
        observed_at=_ms("2024-01-08"),
        published_at=_ms("2024-01-08"),
        fields={"open": 98.0, "high": 99.0, "low": 97.0, "close": 98.0},
    )
    asyncio.run(down_strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(down_strategy.on_market(Event(EvtType.FEATURE, payload=monday_down)))
    event, book = _market(_ms("2024-01-08 01:00"), 98.0)
    entry = asyncio.run(down_strategy.on_market(event, book))

    assert entry.side == "buy"
    assert entry.metadata["gap_direction"] == "long"


def test_cme_gap_fill_detects_friday_to_tuesday_holiday_gap():
    strategy = CMEGapFillStrategy({"min_gap_bps": 10, "max_hold_days": 5})
    friday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-12"),
        observed_at=_ms("2024-01-12"),
        published_at=_ms("2024-01-12"),
        fields={"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0},
    )
    tuesday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-16"),
        observed_at=_ms("2024-01-16"),
        published_at=_ms("2024-01-16"),
        fields={"open": 98.0, "high": 99.0, "low": 97.0, "close": 98.5},
    )
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=tuesday)))

    event, book = _market(_ms("2024-01-16 01:00"), 98.0)
    entry = asyncio.run(strategy.on_market(event, book))

    assert entry.side == "buy"
    assert entry.metadata["gap_direction"] == "long"


def test_cme_gap_fill_skips_roll_day_artifacts():
    strategy = CMEGapFillStrategy({"min_gap_bps": 10, "max_hold_days": 5})
    friday = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-05"),
        observed_at=_ms("2024-01-05"),
        published_at=_ms("2024-01-05"),
        fields={"open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0},
    )
    monday_roll = FeaturePayload(
        dataset_id="cme_btc1_continuous",
        ts=_ms("2024-01-08"),
        observed_at=_ms("2024-01-08"),
        published_at=_ms("2024-01-08"),
        fields={"open": 110.0, "high": 111.0, "low": 109.0, "close": 110.0, "is_roll_day": True},
    )
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=friday)))
    asyncio.run(strategy.on_market(Event(EvtType.FEATURE, payload=monday_roll)))
    event, book = _market(_ms("2024-01-08 01:00"), 110.0)

    assert asyncio.run(strategy.on_market(event, book)) is None
    assert strategy.coverage_status["roll_skip_count"] == 1


def test_historical_event_feed_places_features_before_same_timestamp_market():
    ts = _ms("2024-01-01")
    market = pd.DataFrame({
        "ts": [ts],
        "inst_id": ["BTC-USDT-SWAP"],
        "bid_px_0": [99.0],
        "bid_sz_0": [1.0],
        "ask_px_0": [101.0],
        "ask_sz_0": [1.0],
    })
    features = pd.DataFrame({
        "ts": [ts],
        "dataset_id": ["fear_greed_btc"],
        "observed_at": [pd.Timestamp("2024-01-01", tz="UTC")],
        "published_at": [pd.Timestamp("2024-01-01", tz="UTC")],
        "value_num": [17.0],
        "value_text": ["Extreme Fear"],
        "fields": [{}],
        "quality_status": ["raw"],
    })

    feed = HistoricalEventFeed(market_events=market, funding_events=pd.DataFrame(), feature_events=features)
    events = list(feed.iter_events())

    assert [event.type for event in events] == [EvtType.FEATURE, EvtType.MARKET]


def test_historical_event_feed_normalizes_second_precision_market_timestamps():
    ts = _ms("2024-01-01")
    market = pd.DataFrame({
        "ts": [ts // 1000],
        "inst_id": ["BTC-USDT-SWAP"],
        "bid_px_0": [99.0],
        "bid_sz_0": [1.0],
        "ask_px_0": [101.0],
        "ask_sz_0": [1.0],
    })
    features = pd.DataFrame({
        "ts": [ts],
        "dataset_id": ["fear_greed_btc"],
        "observed_at": [pd.Timestamp("2024-01-01", tz="UTC")],
        "published_at": [pd.Timestamp("2024-01-01", tz="UTC")],
        "value_num": [17.0],
        "value_text": ["Extreme Fear"],
        "fields": [{}],
        "quality_status": ["raw"],
    })

    feed = HistoricalEventFeed(market_events=market, funding_events=pd.DataFrame(), feature_events=features)
    events = list(feed.iter_events())

    assert [event.type for event in events] == [EvtType.FEATURE, EvtType.MARKET]
    assert events[1].payload.ts == ts


def test_synthetic_l1_from_candles_returns_epoch_ms_for_second_precision_index():
    idx = pd.DatetimeIndex(["2024-01-01 00:00:00", "2024-01-01 01:00:00"]).astype("datetime64[s]")
    candles = pd.DataFrame({
        "open": [100.0, 101.0],
        "high": [101.0, 102.0],
        "low": [99.0, 100.0],
        "close": [100.0, 101.0],
        "vol": [10.0, 11.0],
    }, index=idx)

    books = _synthetic_l1_from_candles(
        inst_id="BTC-USDT-SWAP",
        candles=candles,
        synthetic_spread_bps=1.0,
    )

    assert books["ts"].tolist() == [_ms("2024-01-01"), _ms("2024-01-01 01:00:00")]
