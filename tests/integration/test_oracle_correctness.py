from __future__ import annotations

import pandas as pd
import pytest

from backtesting.replay import HistoricalEventFeed, ReplayBacktestEngine, ReplayBacktestResult
from okx_quant.core.config import AppConfig
from okx_quant.core.events import Event, SignalPayload
from okx_quant.strategies.base import Strategy


INITIAL_EQUITY = 10_000.0
MAKER_FEE_RATE = 0.0002
CT_VAL = 0.01
CONTRACTS = 10.0


class OneShotEntryStrategy(Strategy):
    def __init__(self, inst_id: str, side: str, limit_px: float) -> None:
        super().__init__("oracle_buy_and_hold", {})
        self.inst_id = inst_id
        self.side = side
        self.limit_px = limit_px
        self._sent = False

    async def on_market(self, event: Event, book=None):
        payload = event.payload
        if self._sent or payload.channel != "books" or payload.inst_id != self.inst_id:
            return None
        self._sent = True
        return SignalPayload(
            strategy=self.name,
            inst_id=self.inst_id,
            side=self.side,
            strength=1.0,
            fair_value=self.limit_px,
            metadata={"oracle": "one_shot_entry"},
        )

    async def on_fill(self, event: Event) -> None:
        return None


class OracleReplayBacktestEngine(ReplayBacktestEngine):
    def __init__(self, cfg: AppConfig, strategies: list[Strategy], **kwargs) -> None:
        self._oracle_strategies = strategies
        super().__init__(cfg, strategy_names=[s.name for s in strategies], **kwargs)

    def _build_strategies(self) -> list[Strategy]:
        return self._oracle_strategies


def _market_frame(inst_id: str, prices: list[float], freq: str = "1min") -> pd.DataFrame:
    ts = pd.date_range("2024-01-01 00:00:00Z", periods=len(prices), freq=freq)
    ts_ms = [int(pd.Timestamp(value).timestamp() * 1000) for value in ts]
    return pd.DataFrame(
        {
            "ts": ts_ms,
            "inst_id": inst_id,
            "bid_px_0": [px - 0.05 for px in prices],
            "bid_sz_0": [100.0] * len(prices),
            "ask_px_0": [px + 0.05 for px in prices],
            "ask_sz_0": [100.0] * len(prices),
            "mark": prices,
        }
    )


def _funding_events(inst_id: str, funding: pd.DataFrame) -> pd.DataFrame:
    ts_ms = [int(pd.Timestamp(value).timestamp() * 1000) for value in funding["ts"]]
    return pd.DataFrame(
        {
            "ts": ts_ms,
            "inst_id": inst_id,
            "funding_rate": funding["rate"].astype(float),
            "next_funding_time": funding["nextFundingTime"],
            "funding_interval_hours": funding["funding_interval_hours"],
        }
    )


def _oracle_cfg(cfg: AppConfig, inst_id: str, order_notional: float) -> AppConfig:
    cfg = cfg.model_copy(deep=True)
    cfg.system.symbols = [inst_id]
    cfg.system.spot_symbols = []
    cfg.system.equity_usd = INITIAL_EQUITY
    cfg.risk.max_order_notional_usd = order_notional
    cfg.risk.max_pos_pct_equity = 1.0
    cfg.risk.stale_quote_pct = 1.0
    cfg.backtest.order_latency_ms = 0
    cfg.backtest.cancel_latency_ms = 0
    cfg.backtest.queue_fill_fraction = 1.0
    return cfg


def _run_oracle_replay(
    cfg: AppConfig,
    strategy: Strategy,
    market: pd.DataFrame,
    funding: pd.DataFrame | None = None,
    instrument_specs: dict | None = None,
    liquidate_on_end: bool = False,
) -> ReplayBacktestResult:
    feed = HistoricalEventFeed(
        market_events=market.drop(columns=["mark"], errors="ignore"),
        funding_events=funding if funding is not None else pd.DataFrame(),
    )
    specs = instrument_specs or {
        market["inst_id"].iloc[0]: {
            "ctVal": CT_VAL,
            "minSz": 1.0,
            "lotSz": 1.0,
            "tickSz": 0.01,
            "tdMode": "cross",
        }
    }
    engine = OracleReplayBacktestEngine(
        cfg,
        [strategy],
        instrument_specs=specs,
        periods=365 * 24 * 60,
        liquidate_on_end=liquidate_on_end,
    )
    return engine.run_sync(feed)


def _assert_close(actual: float, expected: float, label: str, tol: float = 1e-6) -> None:
    diff = actual - expected
    assert actual == pytest.approx(expected, abs=tol), (
        f"{label}: actual={actual:.12f}, expected={expected:.12f}, diff={diff:.12f}"
    )


def _signed_size(result: ReplayBacktestResult) -> float:
    signed = 0.0
    for row in result.fill_log.itertuples(index=False):
        direction = 1.0 if row.side == "buy" else -1.0
        signed += direction * float(row.fill_sz)
    return signed


def _analytical_funding_sum(result: ReplayBacktestResult) -> float:
    return float(
        sum(
            -float(row.position_size) * float(row.mark_price) * float(row.ct_val) * float(row.rate)
            for row in result.funding_log.itertuples(index=False)
        )
    )


def test_pnl_identity_holds_at_every_timestamp(minimal_cfg, synthetic_funding_frame):
    inst_id = "BTC-USDT-SWAP"
    market = _market_frame(inst_id, [100.00, 99.95, 101.00, 102.00, 103.00, 104.00])
    funding = _funding_events(inst_id, synthetic_funding_frame)
    cfg = _oracle_cfg(minimal_cfg, inst_id, order_notional=CONTRACTS * 100.0 * CT_VAL)
    result = _run_oracle_replay(
        cfg,
        OneShotEntryStrategy(inst_id=inst_id, side="buy", limit_px=100.0),
        market,
        funding,
    )

    assert len(result.fill_log) == 1
    funding_by_ts = result.funding_log.groupby("ts")["cashflow"].sum().to_dict()
    fee_by_ts = result.fill_log.groupby("ts")["fee"].sum().to_dict()
    fill = result.fill_log.iloc[0]
    entry_ts = int(fill["ts"])
    entry_px = float(fill["fill_px"])
    signed_size = _signed_size(result)
    cumulative_funding = 0.0
    cumulative_fees = 0.0

    mark_by_ts = dict(zip(market["ts"].astype("int64"), market["mark"].astype(float)))
    for ts, equity in result.equity_curve.items():
        ts = int(ts)
        cumulative_funding += float(funding_by_ts.get(ts, 0.0))
        cumulative_fees += float(fee_by_ts.get(ts, 0.0))
        mark = mark_by_ts.get(ts, entry_px)
        unrealized = 0.0
        if ts > entry_ts:
            unrealized = signed_size * (mark - entry_px) * CT_VAL
        expected = INITIAL_EQUITY + unrealized + cumulative_funding - cumulative_fees
        _assert_close(float(equity), expected, f"pnl_identity ts={ts}")


@pytest.mark.parametrize(
    ("inst_id", "side"),
    [
        ("BTC-USDT-SWAP", "sell"),
        ("ETH-USDT-SWAP", "buy"),
    ],
)
def test_funding_settlement_matches_formula_exactly(minimal_cfg, synthetic_funding_frame, inst_id, side):
    market = _market_frame(inst_id, [100.00, 99.95, 100.25, 100.50, 100.75, 101.00])
    funding = _funding_events(inst_id, synthetic_funding_frame)
    cfg = _oracle_cfg(minimal_cfg, inst_id, order_notional=CONTRACTS * 100.0 * CT_VAL)
    result = _run_oracle_replay(
        cfg,
        OneShotEntryStrategy(inst_id=inst_id, side=side, limit_px=100.0),
        market,
        funding,
    )

    assert len(result.funding_log) == len(funding)
    for i, row in enumerate(result.funding_log.itertuples(index=False)):
        expected = -float(row.position_size) * CT_VAL * float(row.mark_price) * float(row.rate)
        _assert_close(float(row.cashflow), expected, f"funding_cashflow row={i} inst_id={inst_id}")


@pytest.mark.parametrize(
    ("bar_freq", "prices"),
    [
        ("1min", [100.00, 99.95, 101.00, 102.00, 103.00, 104.00]),
        ("1h", [100.00, 99.95, 100.50, 101.25, 102.00, 102.75]),
    ],
)
def test_buy_and_hold_equity_matches_analytical_formula(
    minimal_cfg,
    synthetic_funding_frame,
    bar_freq,
    prices,
):
    inst_id = "BTC-USDT-SWAP"
    market = _market_frame(inst_id, prices, freq=bar_freq)
    funding_template = synthetic_funding_frame.copy()
    funding_template["ts"] = pd.to_datetime(market["ts"].iloc[2:5], unit="ms", utc=True).to_numpy()
    funding = _funding_events(inst_id, funding_template)
    cfg = _oracle_cfg(minimal_cfg, inst_id, order_notional=CONTRACTS * 100.0 * CT_VAL)
    result = _run_oracle_replay(
        cfg,
        OneShotEntryStrategy(inst_id=inst_id, side="buy", limit_px=100.0),
        market,
        funding,
    )

    assert len(result.fill_log) == 1
    fill = result.fill_log.iloc[0]
    entry_px = float(fill["fill_px"])
    final_mark = float(market["mark"].iloc[-1])
    signed_size = _signed_size(result)
    entry_fee = entry_px * abs(signed_size) * CT_VAL * MAKER_FEE_RATE
    unrealized = signed_size * (final_mark - entry_px) * CT_VAL
    cumulative_funding = _analytical_funding_sum(result)
    expected_final = INITIAL_EQUITY - entry_fee + unrealized + cumulative_funding
    actual_final = float(result.equity_curve.iloc[-1])

    _assert_close(actual_final, expected_final, f"buy_and_hold_final_equity bar_freq={bar_freq}", tol=1e-4)
