"""
Historical replay backtest engine.

Feeds historical market/funding events through the same
Strategy -> Signal -> Order -> Fill -> Position path used elsewhere.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from itertools import combinations
from typing import Any, Callable, Iterable, Optional

import pandas as pd
import pyarrow.parquet as pq
from loguru import logger

from backtesting.data_loader import load_candles as load_ohlcv_candles
from backtesting.data_loader import load_funding as load_funding_rates
from okx_quant.analytics.dsr import psr
from okx_quant.analytics.performance import summary
from okx_quant.core.bus import EventBus
from okx_quant.core.config import AppConfig, load_config
from okx_quant.core.events import Event, EvtType, FillPayload, MarketPayload, OrderPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.execution.broker import SimBroker
from okx_quant.execution.execution_handler import ExecutionHandler
from okx_quant.execution.order_manager import OrderManager
from okx_quant.execution.rate_limiter import RateLimiter
from okx_quant.execution.replay_execution import ReplayExecutionModel
from okx_quant.portfolio.portfolio_manager import PortfolioManager
from okx_quant.portfolio.positions import PositionLedger
from okx_quant.portfolio.sizing import validate_ct_val
from okx_quant.risk.drawdown_tracker import DrawdownTracker
from okx_quant.risk.risk_guard import RiskGuard
from okx_quant.strategies.as_market_maker import ASMarketMaker
from okx_quant.strategies.base import Strategy
from okx_quant.strategies.funding_carry import FundingCarryStrategy
from okx_quant.strategies.obi_market_maker import OBIMarketMaker
from okx_quant.strategies.pairs_trading import PairsTradingStrategy


@dataclass
class ReplayBacktestResult:
    returns: pd.Series
    equity_curve: pd.Series
    metrics: dict
    order_log: pd.DataFrame
    fill_log: pd.DataFrame
    funding_log: pd.DataFrame
    trade_log: pd.DataFrame
    signal_log: list[dict] = field(default_factory=list)
    risk_event_log: list[dict] = field(default_factory=list)
    rejected_log: list[dict] = field(default_factory=list)
    cancel_log: list[dict] = field(default_factory=list)


@dataclass
class ReplayRecorder:
    initial_equity: float
    order_log: list[dict] = field(default_factory=list)
    fill_log: list[dict] = field(default_factory=list)
    funding_log: list[dict] = field(default_factory=list)
    equity_samples: list[dict] = field(default_factory=list)
    signal_log: list[dict] = field(default_factory=list)
    risk_event_log: list[dict] = field(default_factory=list)

    def record_order(self, order: OrderPayload, ts: int) -> None:
        self.order_log.append({
            "ts": ts,
            "cl_ord_id": order.cl_ord_id,
            "inst_id": order.inst_id,
            "side": order.side,
            "px": float(order.px),
            "sz": order.sz,
            "strategy": order.strategy,
            "notional_usd": order.notional_usd,
        })

    def record_fill(self, fill: FillPayload) -> None:
        notional_usd = float(fill.metadata.get("notional_usd", fill.fill_px * fill.fill_sz))
        self.fill_log.append({
            "ts": fill.ts,
            "cl_ord_id": fill.cl_ord_id,
            "ord_id": fill.ord_id,
            "inst_id": fill.inst_id,
            "side": fill.side,
            "fill_px": fill.fill_px,
            "fill_sz": fill.fill_sz,
            "fee": fill.fee,
            "notional_usd": notional_usd,
            "strategy": fill.strategy,
            "state": fill.state,
            "metadata": dict(fill.metadata),
        })

    def record_funding(
        self,
        *,
        ts: int,
        inst_id: str,
        rate: float,
        position_size: float,
        mark_price: float,
        ct_val: float,
        cashflow: float,
    ) -> None:
        self.funding_log.append({
            "ts": ts,
            "inst_id": inst_id,
            "rate": rate,
            "position_size": position_size,
            "mark_price": mark_price,
            "ct_val": ct_val,
            "notional_usd": abs(position_size) * mark_price * ct_val,
            "cashflow": cashflow,
        })

    def record_equity(self, ts: int, equity: float) -> None:
        self.equity_samples.append({"ts": ts, "equity": equity})

    def record_signal(self, signal, ts: int) -> None:
        from okx_quant.core.events import SignalPayload
        if not isinstance(signal, SignalPayload):
            return
        self.signal_log.append({
            "ts": ts,
            "strategy": signal.strategy,
            "inst_id": signal.inst_id,
            "side": signal.side,
            "strength": signal.strength,
            "fair_value": signal.fair_value,
            "target_bid": signal.target_bid,
            "target_ask": signal.target_ask,
            "metadata": dict(signal.metadata) if signal.metadata else {},
        })

    def record_risk_event(
        self,
        *,
        ts: int,
        strategy: str,
        inst_id: str,
        side: str,
        px: float,
        sz: float,
        notional_usd: float,
        reason: str,
        current_position: float = 0.0,
        position_limit: float = 0.0,
        current_equity: float = 0.0,
        metadata: dict | None = None,
    ) -> None:
        self.risk_event_log.append({
            "ts": ts,
            "strategy": strategy,
            "inst_id": inst_id,
            "side": side,
            "px": px,
            "sz": sz,
            "notional_usd": notional_usd,
            "reason": reason,
            "current_position": current_position,
            "position_limit": position_limit,
            "current_equity": current_equity,
            "metadata": metadata or {},
        })

    def build_result(
        self,
        positions: PositionLedger,
        periods: int,
        execution_model: Optional["ReplayExecutionModel"] = None,
    ) -> ReplayBacktestResult:
        if not self.equity_samples:
            self.record_equity(0, self.initial_equity)

        equity_df = pd.DataFrame(self.equity_samples).drop_duplicates(subset=["ts"], keep="last")
        equity_df = equity_df.sort_values("ts")
        equity_series = pd.Series(equity_df["equity"].to_numpy(dtype=float), index=equity_df["ts"])
        returns = equity_series.pct_change().fillna(0.0)

        metrics = summary(returns, periods=periods)
        metrics.update(self._execution_metrics(returns))

        rejected_log = list(execution_model.rejected_log) if execution_model else []
        cancel_log = list(execution_model.cancel_log) if execution_model else []

        return ReplayBacktestResult(
            returns=returns,
            equity_curve=equity_series,
            metrics=metrics,
            order_log=pd.DataFrame(self.order_log),
            fill_log=pd.DataFrame(self.fill_log),
            funding_log=pd.DataFrame(self.funding_log),
            trade_log=pd.DataFrame(positions.get_trade_log()),
            signal_log=list(self.signal_log),
            risk_event_log=list(self.risk_event_log),
            rejected_log=rejected_log,
            cancel_log=cancel_log,
        )

    def _execution_metrics(self, returns: pd.Series) -> dict:
        """
        Compute replay-level execution and significance metrics.

        The replay ``dsr`` here is a single-run diagnostic equivalent in spirit
        to PSR(0), not a multiple-comparison-corrected DSR. True DSR must be
        computed via ``backtesting/cpcv.py`` with N equal to the actual number
        of parameter/strategy trials.
        """
        submitted_order_count = len(self.order_log)
        real_fills = [
            row for row in self.fill_log
            if float(row.get("fill_sz", 0)) > 0
            and row.get("state") in {"filled", "partially_filled"}
        ]
        pending_fills = [row for row in self.fill_log if row.get("state") == "pending"]
        partial_fills = [row for row in real_fills if row.get("state") == "partially_filled"]
        real_fill_count = len(real_fills)
        filled_order_ids = {row.get("cl_ord_id") for row in real_fills if row.get("cl_ord_id")}
        orders_filled_count = len(filled_order_ids)
        total_fees = float(sum(row["fee"] for row in real_fills))
        fill_notional = float(sum(row.get("notional_usd", 0.0) for row in real_fills))
        funding_cashflow = float(sum(row["cashflow"] for row in self.funding_log))
        fill_rate = orders_filled_count / submitted_order_count if submitted_order_count else 0.0
        ret_arr = returns.to_numpy(dtype=float)
        if len(ret_arr) < 4 or float(returns.std()) == 0.0:
            psr_val = 0.0
            dsr_val = 0.0
        else:
            psr_val = psr(ret_arr, sr_benchmark=0.0)
            dsr_val = psr_val
        return {
            "submitted_order_count": submitted_order_count,
            "order_count": submitted_order_count,
            "orders_filled_count": orders_filled_count,
            "real_fill_count": real_fill_count,
            "fill_count": real_fill_count,
            "pending_fill_event_count": len(pending_fills),
            "partial_fill_count": len(partial_fills),
            "fill_rate": fill_rate,
            "total_fees": total_fees,
            "fill_notional_usd": fill_notional,
            "funding_cashflow": funding_cashflow,
            "funding_settlement_count": len(self.funding_log),
            "psr": psr_val,
            "dsr": dsr_val,
        }


def _normalize_time_filter(df: pd.DataFrame, ts_col: str = "ts", start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
    if df.empty:
        return df

    data = df.copy()
    if ts_col in data.columns:
        data[ts_col] = pd.to_datetime(data[ts_col], utc=True, errors="coerce")
        data = data.dropna(subset=[ts_col])
    else:
        data.index = pd.to_datetime(data.index, utc=True, errors="coerce")
        data = data[~data.index.isna()].reset_index(names=ts_col)

    if start:
        data = data[data[ts_col] >= pd.Timestamp(start, tz="UTC")]
    if end:
        data = data[data[ts_col] < pd.Timestamp(end, tz="UTC")]
    return data.sort_values(ts_col)


def _to_ms_int(val) -> int:
    """Convert a timestamp value (Timestamp, int, float, None) to milliseconds integer."""
    if val is None:
        return 0
    try:
        if isinstance(val, pd.Timestamp):
            return int(val.timestamp() * 1000)
        return int(float(val))
    except (TypeError, ValueError, OSError):
        return 0


def _bar_to_seconds(bar: str) -> int:
    text = str(bar or "1H").strip()
    if len(text) < 2:
        return 3600
    try:
        qty = int(text[:-1])
    except ValueError:
        return 3600
    unit = text[-1]
    multipliers = {
        "s": 1,
        "m": 60,
        "H": 3600,
        "h": 3600,
        "D": 86400,
        "d": 86400,
    }
    return max(qty * multipliers.get(unit, 3600), 1)


def _load_parquet_frames(paths: Iterable[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if path.exists():
            frames.append(pq.read_table(path).to_pandas())
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_l1_books(
    inst_id: str,
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    bar: str = "1H",
    synthetic_spread_bps: float = 1.0,
    fallback_inst_id: Optional[str] = None,
    backend: str = "parquet",
    dsn: Optional[str] = None,
) -> pd.DataFrame:
    """
    Load top-of-book snapshots.

    Preference order:
    1. ``ob_ticks_*.parquet`` snapshots
    2. FeedStore-style ``*/books.parquet`` files
    3. Synthetic L1 books derived from candle closes
    """
    inst_dir = Path(data_dir) / inst_id.replace("-", "_")
    if backend == "postgres":
        try:
            candles = load_ohlcv_candles(
                inst_id,
                bar=bar,
                data_dir=data_dir,
                start=start,
                end=end,
                backend="postgres",
                dsn=dsn,
            )
        except FileNotFoundError:
            candles = pd.DataFrame()
        if candles.empty and fallback_inst_id:
            candles = load_ohlcv_candles(
                fallback_inst_id,
                bar=bar,
                data_dir=data_dir,
                start=start,
                end=end,
                backend="postgres",
                dsn=dsn,
            )
        if not candles.empty:
            return _synthetic_l1_from_candles(
                inst_id=inst_id,
                candles=candles,
                synthetic_spread_bps=synthetic_spread_bps,
            )

    if inst_dir.exists():
        raw_ticks = _load_parquet_frames(sorted(inst_dir.glob("ob_ticks_*.parquet")))
        if not raw_ticks.empty:
            ts_col = "server_ts" if "server_ts" in raw_ticks.columns else "ts"
            raw_ticks = _normalize_time_filter(raw_ticks, ts_col=ts_col, start=start, end=end)
            ts_ms = (
                raw_ticks[ts_col].astype("int64")
                if ts_col == "server_ts"
                else (raw_ticks[ts_col].astype("int64") // 1_000_000)
            )
            return pd.DataFrame({
                "ts": ts_ms.astype("int64"),
                "inst_id": inst_id,
                "bid_px_0": raw_ticks["best_bid"].astype(float),
                "bid_sz_0": raw_ticks.get("bid_sz", 1.0).astype(float),
                "ask_px_0": raw_ticks["best_ask"].astype(float),
                "ask_sz_0": raw_ticks.get("ask_sz", 1.0).astype(float),
            })

        stored_books = _load_parquet_frames(sorted(inst_dir.glob("*/books.parquet")))
        if not stored_books.empty:
            stored_books = _normalize_time_filter(stored_books, ts_col="ts", start=start, end=end)
            stored_books["ts"] = stored_books["ts"].astype("int64") // 1_000_000
            stored_books["inst_id"] = inst_id
            return stored_books[["ts", "inst_id", "bid_px_0", "bid_sz_0", "ask_px_0", "ask_sz_0"]]

    candle_path = inst_dir / f"candles_{bar}.parquet"
    if not candle_path.exists() and fallback_inst_id:
        candle_path = Path(data_dir) / fallback_inst_id.replace("-", "_") / f"candles_{bar}.parquet"
    if not candle_path.exists():
        return pd.DataFrame(columns=["ts", "inst_id", "bid_px_0", "bid_sz_0", "ask_px_0", "ask_sz_0"])

    candles = pq.read_table(candle_path).to_pandas()
    candles = _normalize_time_filter(candles, ts_col="ts", start=start, end=end)
    return _synthetic_l1_from_candles(
        inst_id=inst_id,
        candles=candles,
        synthetic_spread_bps=synthetic_spread_bps,
    )


def _synthetic_l1_from_candles(
    *,
    inst_id: str,
    candles: pd.DataFrame,
    synthetic_spread_bps: float,
) -> pd.DataFrame:
    data = candles.copy()
    if "ts" not in data.columns:
        data = data.reset_index(names="ts")
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    data = data.dropna(subset=["ts"]).sort_values("ts")
    if data.empty:
        return pd.DataFrame(columns=["ts", "inst_id", "bid_px_0", "bid_sz_0", "ask_px_0", "ask_sz_0"])
    mid = data["close"].astype(float)
    half_spread = mid * synthetic_spread_bps / 20_000.0
    size = data["vol"].astype(float).clip(lower=1.0) if "vol" in data.columns else 1.0
    return pd.DataFrame({
        "ts": data["ts"].astype("int64") // 1_000_000,
        "inst_id": inst_id,
        "bid_px_0": (mid - half_spread).astype(float),
        "bid_sz_0": size,
        "ask_px_0": (mid + half_spread).astype(float),
        "ask_sz_0": size,
    })


def load_funding_events(
    inst_id: str,
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    backend: str = "parquet",
    dsn: Optional[str] = None,
) -> pd.DataFrame:
    if backend == "postgres":
        funding = load_funding_rates(
            inst_id=inst_id,
            data_dir=data_dir,
            start=start,
            end=end,
            backend="postgres",
            dsn=dsn,
        )
        if funding.empty:
            return pd.DataFrame(columns=["ts", "inst_id", "funding_rate", "next_funding_time"])
        frame = funding.reset_index(names="ts")
        return pd.DataFrame({
            "ts": frame["ts"].astype("int64") // 1_000_000,
            "inst_id": inst_id,
            "funding_rate": frame["rate"].astype(float),
            "next_funding_time": frame.get("nextFundingTime", 0),
            "funding_interval_hours": frame.get("funding_interval_hours", None),
        })

    path = Path(data_dir) / inst_id.replace("-", "_") / "funding.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["ts", "inst_id", "funding_rate", "next_funding_time"])
    funding = pq.read_table(path).to_pandas()
    funding = _normalize_time_filter(funding, ts_col="ts", start=start, end=end)
    return pd.DataFrame({
        "ts": funding["ts"].astype("int64") // 1_000_000,
        "inst_id": inst_id,
        "funding_rate": funding["rate"].astype(float),
        "next_funding_time": funding.get("nextFundingTime", 0),
        "funding_interval_hours": funding.get("funding_interval_hours", None),
    })


class HistoricalEventFeed:
    def __init__(self, market_events: pd.DataFrame, funding_events: pd.DataFrame) -> None:
        self.market_events = market_events
        self.funding_events = funding_events

    def iter_events(self) -> Iterable[Event]:
        combined: list[tuple[int, int, Event]] = []

        for row in self.market_events.itertuples(index=False):
            payload = MarketPayload(
                inst_id=row.inst_id,
                ts=int(row.ts),
                bids=[[f"{float(row.bid_px_0):.10f}", f"{float(row.bid_sz_0):.10f}"]],
                asks=[[f"{float(row.ask_px_0):.10f}", f"{float(row.ask_sz_0):.10f}"]],
                seq_id=0,
                channel="books",
            )
            combined.append((int(row.ts), 0, Event(EvtType.MARKET, payload=payload)))

        for row in self.funding_events.itertuples(index=False):
            payload = MarketPayload(
                inst_id=row.inst_id,
                ts=int(row.ts),
                bids=[],
                asks=[],
                seq_id=0,
                channel="funding-rate",
                funding_rate=float(row.funding_rate),
                next_funding_time=_to_ms_int(getattr(row, "next_funding_time", 0)),
                funding_interval_hours=(
                    float(row.funding_interval_hours)
                    if getattr(row, "funding_interval_hours", None) is not None
                    and pd.notna(getattr(row, "funding_interval_hours", None))
                    else None
                ),
            )
            combined.append((int(row.ts), 1, Event(EvtType.FUNDING, payload=payload)))

        combined.sort(key=lambda item: (item[0], item[1]))
        for _, _, event in combined:
            yield event


class ReplayBacktestEngine:
    def __init__(
        self,
        cfg: AppConfig,
        strategy_names: Optional[list[str]] = None,
        instrument_specs: Optional[dict] = None,
        periods: int = 365 * 24,
        bar_seconds: int = 3600,
    ) -> None:
        self._cfg = cfg
        self._strategy_names = strategy_names
        self._instrument_specs = instrument_specs or self._default_instrument_specs()
        self._periods = periods
        self._bar_seconds = bar_seconds

    def _default_instrument_specs(self) -> dict:
        specs = {}
        swap_symbols = set(self._cfg.system.symbols)
        swap_symbols.update(self._cfg.strategies.obi_market_maker.symbols)
        swap_symbols.update(self._cfg.strategies.as_market_maker.symbols)
        swap_symbols.update({
            self._cfg.strategies.funding_carry.perp_symbol,
            self._cfg.strategies.pairs_trading.symbol_y,
            self._cfg.strategies.pairs_trading.symbol_x,
        })
        for symbol in swap_symbols:
            if "SWAP" not in symbol:
                continue
            specs[symbol] = {
                "ctVal": self._fallback_swap_ct_val(symbol),
                "minSz": 0.01,
                "lotSz": 0.01,
                "tickSz": 0.1,
                "tdMode": "cross",
            }
        spot_symbols = set(self._cfg.system.spot_symbols)
        spot_symbols.add(self._cfg.strategies.funding_carry.spot_symbol)
        for symbol in spot_symbols:
            specs[symbol] = {"ctVal": 1.0, "minSz": 0.0001, "lotSz": 0.0001, "tickSz": 0.1, "tdMode": "cross"}
        return specs

    @staticmethod
    def _fallback_swap_ct_val(symbol: str) -> float:
        if symbol.startswith(("BTC-", "ETH-")):
            logger.warning("Instrument ctVal missing; falling back to known BTC/ETH swap ctVal=0.01", inst_id=symbol)
            return 0.01
        logger.error("Instrument ctVal missing for non-BTC/ETH swap; refusing silent fallback", inst_id=symbol)
        raise ValueError(f"Missing ctVal for non-BTC/ETH swap: {symbol}")

    def _build_strategies(self) -> list[Strategy]:
        wanted = set(self._strategy_names or [])
        load_all = not wanted
        strategies: list[Strategy] = []
        strat_cfg = self._cfg.strategies
        candidates: list[tuple[str, Strategy]] = [
            ("obi_market_maker", OBIMarketMaker(strat_cfg.obi_market_maker.model_dump())),
            ("as_market_maker", ASMarketMaker(strat_cfg.as_market_maker.model_dump())),
            ("funding_carry", FundingCarryStrategy(strat_cfg.funding_carry.model_dump())),
            (
                "pairs_trading",
                PairsTradingStrategy({
                    **strat_cfg.pairs_trading.model_dump(),
                    "bar_seconds": self._bar_seconds,
                }),
            ),
        ]
        enabled = {
            "obi_market_maker": strat_cfg.obi_market_maker.enabled,
            "as_market_maker": strat_cfg.as_market_maker.enabled,
            "funding_carry": strat_cfg.funding_carry.enabled,
            "pairs_trading": strat_cfg.pairs_trading.enabled,
        }

        for name, strategy in candidates:
            if load_all:
                if enabled[name]:
                    strategies.append(strategy)
            elif name in wanted:
                strategies.append(strategy)
        return strategies

    @staticmethod
    def _apply_book_snapshot(book: OkxBook, payload: MarketPayload) -> None:
        book.bids.clear()
        book.asks.clear()
        for px, sz, *_ in payload.bids:
            if float(sz) > 0:
                book.bids[float(px)] = (px, sz)
        for px, sz, *_ in payload.asks:
            if float(sz) > 0:
                book.asks[float(px)] = (px, sz)

    async def run(self, feed: HistoricalEventFeed) -> ReplayBacktestResult:
        if feed.market_events.empty and feed.funding_events.empty:
            raise ValueError("ReplayBacktestEngine received an empty historical feed")

        bus = EventBus()
        strategies = self._build_strategies()
        positions = PositionLedger(initial_equity=self._cfg.system.equity_usd)
        dd_tracker = DrawdownTracker(
            soft_drawdown_pct=self._cfg.risk.soft_drawdown_pct,
            hard_drawdown_pct=self._cfg.risk.hard_drawdown_pct,
            max_daily_loss_pct=self._cfg.risk.max_daily_loss_pct,
        )
        dd_tracker.set_initial_equity(self._cfg.system.equity_usd)
        risk_guard = RiskGuard(
            equity_fn=positions.get_equity,
            drawdown_tracker=dd_tracker,
            max_order_notional_usd=self._cfg.risk.max_order_notional_usd,
            max_pos_pct_equity=self._cfg.risk.max_pos_pct_equity,
            max_leverage=self._cfg.risk.max_leverage,
            max_daily_loss_pct=self._cfg.risk.max_daily_loss_pct,
            soft_drawdown_pct=self._cfg.risk.soft_drawdown_pct,
            hard_drawdown_pct=self._cfg.risk.hard_drawdown_pct,
            stale_quote_pct=self._cfg.risk.stale_quote_pct,
        )
        for strategy in strategies:
            risk_guard.register_strategy(strategy.name)

        execution_model = ReplayExecutionModel(
            instrument_specs=self._instrument_specs,
            order_latency_ms=self._cfg.backtest.order_latency_ms,
            cancel_latency_ms=self._cfg.backtest.cancel_latency_ms,
            queue_fill_fraction=self._cfg.backtest.queue_fill_fraction,
        )
        portfolio_mgr = PortfolioManager(
            bus=bus,
            positions=positions,
            risk_guard=risk_guard,
            target_ann_vol=0.20,
            instrument_specs=self._instrument_specs,
        )
        order_manager = OrderManager(
            SimBroker(
                slippage_bps=2.0,
                fill_probability=1.0,
                instrument_specs=self._instrument_specs,
                execution_model=execution_model,
            ),
            RateLimiter(),
        )
        exec_handler = ExecutionHandler(bus=bus, order_manager=order_manager, stale_quote_pct=self._cfg.risk.stale_quote_pct)
        recorder = ReplayRecorder(initial_equity=self._cfg.system.equity_usd)
        original_risk_check = risk_guard.check

        def recording_risk_check(
            order: OrderPayload,
            current_pos_notional: float = 0.0,
            current_mid: float = 0.0,
        ) -> bool:
            allowed = original_risk_check(order, current_pos_notional, current_mid)
            if allowed:
                return True
            ts = execution_model.current_ts(order.inst_id)
            execution_model.rejected_log.append({
                "ts": ts,
                "cl_ord_id": order.cl_ord_id,
                "inst_id": order.inst_id,
                "side": order.side,
                "px": float(order.px),
                "reason": "risk_guard_block",
            })
            recorder.record_risk_event(
                ts=ts,
                strategy=order.strategy,
                inst_id=order.inst_id,
                side=order.side,
                px=float(order.px),
                sz=float(order.sz),
                notional_usd=order.notional_usd,
                reason="risk_guard_block",
                current_position=current_pos_notional,
                position_limit=self._cfg.risk.max_pos_pct_equity * positions.get_equity(),
                current_equity=positions.get_equity(),
            )
            return False

        risk_guard.check = recording_risk_check  # type: ignore[method-assign]

        book_symbols = {
            getattr(strategy, "perp_symbol", None) for strategy in strategies
        } | {
            getattr(strategy, "spot_symbol", None) for strategy in strategies
        } | {
            getattr(strategy, "symbol_y", None) for strategy in strategies
        } | {
            getattr(strategy, "symbol_x", None) for strategy in strategies
        } | set(self._cfg.system.symbols) | set(self._cfg.system.spot_symbols)
        books = {symbol: OkxBook(symbol) for symbol in book_symbols if symbol}

        async def on_market_event(event: Event) -> None:
            payload = event.payload
            if payload.channel == "books":
                book = books.get(payload.inst_id)
                if book is not None:
                    self._apply_book_snapshot(book, payload)
                await exec_handler.on_market(event)
                portfolio_mgr.on_market(payload)
                dd_tracker.update(positions.get_equity())
                recorder.record_equity(payload.ts, positions.get_equity())
                for strategy in strategies:
                    if strategy.is_active:
                        signal = await strategy.on_market(event, books.get(payload.inst_id))
                        if signal:
                            recorder.record_signal(signal, payload.ts)
                            await bus.put(Event(EvtType.SIGNAL, payload=signal))

        async def on_funding_event(event: Event) -> None:
            payload = event.payload
            self._settle_funding(payload, positions, recorder)
            recorder.record_equity(payload.ts, positions.get_equity())
            for strategy in strategies:
                if strategy.is_active:
                    signal = await strategy.on_market(event)
                    if signal:
                        await bus.put(Event(EvtType.SIGNAL, payload=signal))

        async def on_signal_event(event: Event) -> None:
            await portfolio_mgr.on_signal(event)

        async def on_order_event(event: Event) -> None:
            order_ts = execution_model.current_ts(event.payload.inst_id)
            recorder.record_order(event.payload, order_ts)
            await exec_handler.on_order(event)

        async def on_fill_event(event: Event) -> None:
            if isinstance(event.payload, dict):
                await exec_handler.on_fill_ws(event.payload)
                return
            fill = event.payload
            recorder.record_fill(fill)
            await portfolio_mgr.on_fill(event)
            dd_tracker.update(positions.get_equity())
            recorder.record_equity(fill.ts, positions.get_equity())
            for strategy in strategies:
                if strategy.name == fill.strategy:
                    await strategy.on_fill(event)

        bus.subscribe(EvtType.MARKET, on_market_event)
        bus.subscribe(EvtType.FUNDING, on_funding_event)
        bus.subscribe(EvtType.SIGNAL, on_signal_event)
        bus.subscribe(EvtType.ORDER, on_order_event)
        bus.subscribe(EvtType.FILL, on_fill_event)

        dispatch_task = asyncio.create_task(bus.dispatch_loop())
        try:
            for event in feed.iter_events():
                await bus.put(event)
                # Drain each historical timestamp through downstream
                # signal/order/fill handlers before advancing replay time.
                await bus.join()
        finally:
            dispatch_task.cancel()
            await asyncio.gather(dispatch_task, return_exceptions=True)

        return recorder.build_result(positions, periods=self._periods, execution_model=execution_model)

    def run_sync(self, feed: HistoricalEventFeed) -> ReplayBacktestResult:
        return asyncio.run(self.run(feed))

    def _settle_funding(
        self,
        payload: MarketPayload,
        positions: PositionLedger,
        recorder: ReplayRecorder,
    ) -> None:
        rate = float(payload.funding_rate or 0.0)
        if rate == 0.0:
            return

        pos = positions.get_position(payload.inst_id)
        if abs(pos.size) < 1e-12:
            return

        specs = self._instrument_specs.get(payload.inst_id, {})
        ct_val_raw = specs.get("ctVal")
        if ct_val_raw is None:
            raise ValueError(f"Missing ctVal for {payload.inst_id}")
        ct_val = validate_ct_val(float(ct_val_raw), payload.inst_id)
        mark_price = pos.last_price
        if mark_price <= 0:
            if pos.avg_entry > 0:
                logger.warning(
                    "Funding settlement mark price missing; falling back to avg_entry",
                    inst_id=payload.inst_id,
                    mark_price=mark_price,
                    avg_entry=pos.avg_entry,
                )
                mark_price = pos.avg_entry
            else:
                logger.warning(
                    "Funding settlement skipped because mark price and avg_entry are unavailable",
                    inst_id=payload.inst_id,
                    mark_price=mark_price,
                    avg_entry=pos.avg_entry,
                )
                return

        cashflow = -pos.size * mark_price * ct_val * rate
        positions.apply_cashflow(
            cashflow,
            inst_id=payload.inst_id,
            reason="funding",
            strategy=pos.strategy,
            ts=payload.ts,
            metadata={"funding_rate": rate, "ct_val": ct_val, "mark_price": mark_price},
        )
        recorder.record_funding(
            ts=payload.ts,
            inst_id=payload.inst_id,
            rate=rate,
            position_size=pos.size,
            mark_price=mark_price,
            ct_val=ct_val,
            cashflow=cashflow,
        )


def build_feed_for_strategies(
    cfg: AppConfig,
    strategy_names: list[str],
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    bar: str = "1H",
) -> HistoricalEventFeed:
    market_frames: list[pd.DataFrame] = []
    funding_frames: list[pd.DataFrame] = []

    strategy_set = set(strategy_names)
    if "obi_market_maker" in strategy_set:
        for symbol in cfg.strategies.obi_market_maker.symbols:
            market_frames.append(load_l1_books(
                symbol,
                data_dir=data_dir,
                start=start,
                end=end,
                bar=bar,
                backend=cfg.storage.candle_backend,
                dsn=cfg.storage.timescale_dsn,
            ))

    if "as_market_maker" in strategy_set:
        for symbol in cfg.strategies.as_market_maker.symbols:
            market_frames.append(load_l1_books(
                symbol,
                data_dir=data_dir,
                start=start,
                end=end,
                bar=bar,
                backend=cfg.storage.candle_backend,
                dsn=cfg.storage.timescale_dsn,
            ))

    if "pairs_trading" in strategy_set:
        market_frames.append(load_l1_books(
            cfg.strategies.pairs_trading.symbol_y,
            data_dir=data_dir,
            start=start,
            end=end,
            bar=bar,
            backend=cfg.storage.candle_backend,
            dsn=cfg.storage.timescale_dsn,
        ))
        market_frames.append(load_l1_books(
            cfg.strategies.pairs_trading.symbol_x,
            data_dir=data_dir,
            start=start,
            end=end,
            bar=bar,
            backend=cfg.storage.candle_backend,
            dsn=cfg.storage.timescale_dsn,
        ))

    if "funding_carry" in strategy_set:
        perp = cfg.strategies.funding_carry.perp_symbol
        spot = cfg.strategies.funding_carry.spot_symbol
        market_frames.append(load_l1_books(
            perp,
            data_dir=data_dir,
            start=start,
            end=end,
            bar=bar,
            backend=cfg.storage.candle_backend,
            dsn=cfg.storage.timescale_dsn,
        ))
        market_frames.append(
            load_l1_books(
                spot,
                data_dir=data_dir,
                start=start,
                end=end,
                bar=bar,
                fallback_inst_id=perp,
                backend=cfg.storage.candle_backend,
                dsn=cfg.storage.timescale_dsn,
            )
        )
        funding_frames.append(load_funding_events(
            perp,
            data_dir=data_dir,
            start=start,
            end=end,
            backend=cfg.storage.candle_backend,
            dsn=cfg.storage.timescale_dsn,
        ))

    market_df = _concat_non_empty(market_frames)

    # Load funding for all SWAP symbols that appear in market data,
    # not only for funding_carry. Missing funding data is non-fatal.
    swap_symbols_with_funding: set[str] = set()
    if not market_df.empty and "inst_id" in market_df.columns:
        swap_symbols_with_funding = {
            s for s in market_df["inst_id"].unique()
            if isinstance(s, str) and "SWAP" in s
        }
    for sym in swap_symbols_with_funding:
        if any(
            not df.empty and "inst_id" in df.columns and sym in df["inst_id"].values
            for df in funding_frames
        ):
            continue
        try:
            extra = load_funding_events(
                sym,
                data_dir=data_dir,
                start=start,
                end=end,
                backend=cfg.storage.candle_backend,
                dsn=cfg.storage.timescale_dsn,
            )
            if not extra.empty:
                funding_frames.append(extra)
        except Exception:
            logger.warning("No funding data available for {}", sym)

    funding_df = _concat_non_empty(funding_frames)
    return HistoricalEventFeed(market_events=market_df, funding_events=funding_df)


def _concat_non_empty(frames: list[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [df for df in frames if not df.empty]
    if not non_empty:
        return pd.DataFrame()
    return pd.concat(non_empty, ignore_index=True)


def _as_utc_index(index: pd.Index) -> pd.DatetimeIndex:
    dt_index = pd.DatetimeIndex(index)
    if dt_index.tz is None:
        return dt_index.tz_localize("UTC")
    return dt_index.tz_convert("UTC")


def _infer_index_step(index: pd.DatetimeIndex) -> pd.Timedelta:
    if len(index) < 2:
        return pd.Timedelta(hours=1)
    diffs = index.to_series().diff().dropna()
    if diffs.empty:
        return pd.Timedelta(hours=1)
    return pd.Timedelta(diffs.median())


def _window_bounds(data: pd.DataFrame) -> tuple[str, str]:
    if data.empty:
        raise ValueError("Replay validation window cannot be empty")
    index = _as_utc_index(data.index)
    start = index[0]
    end = index[-1] + _infer_index_step(index)
    return start.isoformat(), end.isoformat()


def _returns_to_datetime_index(returns: pd.Series) -> pd.Series:
    if returns.empty:
        return returns
    normalized = pd.Series(returns.to_numpy(dtype=float), index=returns.index)
    if isinstance(normalized.index, pd.DatetimeIndex):
        normalized.index = _as_utc_index(normalized.index)
        return normalized.sort_index()
    normalized.index = pd.to_datetime(normalized.index, unit="ms", utc=True, errors="coerce")
    normalized = normalized[~normalized.index.isna()]
    return normalized.sort_index()


def _align_replay_returns(returns: pd.Series, target_index: pd.Index) -> pd.Series:
    target = _as_utc_index(target_index)
    if returns.empty:
        return pd.Series(0.0, index=target)
    replay_returns = _returns_to_datetime_index(returns).groupby(level=0).sum()
    return replay_returns.reindex(target, fill_value=0.0)


def build_replay_validation_frame(
    cfg: AppConfig,
    strategy_names: list[str],
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    bar: str = "1H",
) -> pd.DataFrame:
    """
    Build the timestamp frame used by WF/CPCV splitters for replay validation.

    The validators only need a leak-free DatetimeIndex. The strategy callback
    replays the actual market data for each train/test window.
    """
    feed = build_feed_for_strategies(
        cfg=cfg,
        strategy_names=strategy_names,
        data_dir=data_dir,
        start=start,
        end=end,
        bar=bar,
    )
    frames = [df for df in [feed.market_events, feed.funding_events] if not df.empty and "ts" in df.columns]
    if not frames:
        return pd.DataFrame(columns=["event_count"], index=pd.DatetimeIndex([], tz="UTC"))

    ts = pd.concat([df["ts"] for df in frames], ignore_index=True)
    idx = pd.to_datetime(ts, unit="ms", utc=True, errors="coerce")
    idx = idx[~idx.isna()]
    if len(idx) == 0:
        return pd.DataFrame(columns=["event_count"], index=pd.DatetimeIndex([], tz="UTC"))

    validation_frame = pd.DataFrame({"event_count": 1}, index=idx)
    return validation_frame.groupby(level=0).sum().sort_index()


ReplayValidationRunner = Callable[..., ReplayBacktestResult]


def make_replay_strategy_fn(
    *,
    strategy_names: list[str],
    cfg: AppConfig,
    data_dir: str = "data/ticks",
    bar: str = "1H",
    periods: int = 365 * 24,
    include_train_metrics: bool = False,
    runner: ReplayValidationRunner | None = None,
) -> Callable[[pd.DataFrame, pd.DataFrame], dict[str, Any]]:
    """
    Return the strategy_fn expected by WalkForward.evaluate() and CPCV.evaluate().

    The callback replays the supplied OOS/test window through the full event
    stack and returns a dict with a returns Series aligned to test_data.index.
    """
    replay_runner = runner or run_replay_backtest

    def strategy_fn(train_data: pd.DataFrame, test_data: pd.DataFrame) -> dict[str, Any]:
        is_metrics: dict[str, Any] | None = None
        if include_train_metrics and not train_data.empty:
            is_start, is_end = _window_bounds(train_data)
            is_result = replay_runner(
                strategy_names=strategy_names,
                cfg=cfg,
                data_dir=data_dir,
                start=is_start,
                end=is_end,
                bar=bar,
                periods=periods,
            )
            is_metrics = dict(is_result.metrics)

        oos_start, oos_end = _window_bounds(test_data)
        oos_result = replay_runner(
            strategy_names=strategy_names,
            cfg=cfg,
            data_dir=data_dir,
            start=oos_start,
            end=oos_end,
            bar=bar,
            periods=periods,
        )
        return {
            "returns": _align_replay_returns(oos_result.returns, test_data.index),
            "is_metrics": is_metrics or {},
            "oos_metrics": dict(oos_result.metrics),
            "oos_order_count": len(oos_result.order_log),
            "oos_fill_count": len(oos_result.fill_log),
            "returns_source": "replay_window",
        }

    return strategy_fn


def _jsonable_validation_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable_validation_value(v) for k, v in value.items() if k != "returns"}
    if isinstance(value, list):
        return [_jsonable_validation_value(v) for v in value]
    if isinstance(value, tuple):
        return [_jsonable_validation_value(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _summarize_walk_forward(results: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if results.empty:
        return rows
    for row in results.to_dict(orient="records"):
        result = row.get("result", {}) or {}
        is_metrics = result.get("is_metrics", {}) if isinstance(result, dict) else {}
        oos_metrics = result.get("oos_metrics", {}) if isinstance(result, dict) else {}
        window = row.get("window")
        rows.append(_jsonable_validation_value({
            "window": window,
            "i": window,
            "is_start": row.get("is_start"),
            "is_end": row.get("is_end"),
            "oos_start": row.get("oos_start"),
            "oos_end": row.get("oos_end"),
            "is_n": row.get("is_n"),
            "oos_n": row.get("oos_n"),
            "is_sharpe": is_metrics.get("sharpe"),
            "oos_sharpe": row.get("oos_sharpe"),
            "oos_return": oos_metrics.get("total_return"),
            "oos_mdd": oos_metrics.get("max_drawdown"),
            "oos_metrics": oos_metrics,
            "oos_order_count": result.get("oos_order_count") if isinstance(result, dict) else None,
            "oos_fill_count": result.get("oos_fill_count") if isinstance(result, dict) else None,
        }))
    return rows


def _summarize_cpcv(results: dict[str, Any], n_splits: int, k_test: int) -> dict[str, Any]:
    sharpe_list = [float(v) for v in results.get("sharpe_list", [])]
    path_sharpes = [float(v) for v in results.get("path_sharpes", [])]
    test_groups = list(combinations(range(n_splits), k_test))
    std_oos = float(pd.Series(sharpe_list).std(ddof=1)) if len(sharpe_list) > 1 else 0.0

    payload = {
        key: _jsonable_validation_value(value)
        for key, value in results.items()
        if key not in {"sharpe_list", "path_sharpes"}
    }
    payload.update({
        "sharpe_list": sharpe_list,
        "path_sharpes": path_sharpes,
        "combos": [
            {
                "i": i,
                "test_groups": list(test_groups[i]) if i < len(test_groups) else [],
                "sharpe": sr,
            }
            for i, sr in enumerate(sharpe_list)
        ],
        "paths": [
            {"i": i, "sharpe": sr}
            for i, sr in enumerate(path_sharpes)
        ],
        "std_oos_sharpe": std_oos,
        "n_research_trials": int(results.get("n_trials", 1) or 1),
    })
    return payload


def run_replay_validations(
    *,
    strategy_names: list[str],
    cfg: AppConfig,
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    bar: str = "1H",
    periods: int = 365 * 24,
    mode: str = "both",
    wf_is_days: int = 30,
    wf_oos_days: int = 7,
    cpcv_n_splits: int = 6,
    cpcv_k_test: int = 2,
    cpcv_embargo_pct: float = 0.02,
    cpcv_purge_size: int = 1,
    n_trials: int = 1,
    runner: ReplayValidationRunner | None = None,
) -> dict[str, Any]:
    """Run replay-backed WF/CPCV validation and return result.json-ready data."""
    from backtesting.cpcv import CPCV
    from backtesting.walk_forward import WalkForward

    validate_mode = mode.lower()
    if validate_mode not in {"wf", "cpcv", "both"}:
        raise ValueError("--validate must be one of: wf, cpcv, both")

    df = build_replay_validation_frame(
        cfg=cfg,
        strategy_names=strategy_names,
        data_dir=data_dir,
        start=start,
        end=end,
        bar=bar,
    )
    if df.empty:
        raise ValueError("Replay validation cannot run because no market/funding data was loaded")

    validation: dict[str, Any] = {
        "validation_frame_rows": int(len(df)),
        "validation_frame_start": df.index[0].isoformat(),
        "validation_frame_end": df.index[-1].isoformat(),
    }

    replay_runner = runner or run_replay_backtest
    if validate_mode in {"wf", "both"}:
        wf = WalkForward(is_days=wf_is_days, oos_days=wf_oos_days)
        wf_results = wf.evaluate(
            df,
            make_replay_strategy_fn(
                strategy_names=strategy_names,
                cfg=cfg,
                data_dir=data_dir,
                bar=bar,
                periods=periods,
                include_train_metrics=True,
                runner=replay_runner,
            ),
            periods=periods,
        )
        validation["walk_forward"] = _summarize_walk_forward(wf_results)

    if validate_mode in {"cpcv", "both"}:
        cpcv = CPCV(
            n_splits=cpcv_n_splits,
            k_test=cpcv_k_test,
            embargo_pct=cpcv_embargo_pct,
            purge_size=cpcv_purge_size,
        )
        cpcv_results = cpcv.evaluate(
            df,
            make_replay_strategy_fn(
                strategy_names=strategy_names,
                cfg=cfg,
                data_dir=data_dir,
                bar=bar,
                periods=periods,
                include_train_metrics=False,
                runner=replay_runner,
            ),
            periods=periods,
            n_trials=n_trials,
        )
        validation["cpcv"] = _summarize_cpcv(cpcv_results, cpcv_n_splits, cpcv_k_test)

    return validation


def run_replay_backtest(
    strategy_names: list[str],
    cfg: Optional[AppConfig] = None,
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    bar: str = "1H",
    periods: int = 365 * 24,
) -> ReplayBacktestResult:
    cfg = cfg or load_config()
    feed = build_feed_for_strategies(cfg, strategy_names=strategy_names, data_dir=data_dir, start=start, end=end, bar=bar)
    engine = ReplayBacktestEngine(
        cfg,
        strategy_names=strategy_names,
        periods=periods,
        bar_seconds=_bar_to_seconds(bar),
    )
    return engine.run_sync(feed)
