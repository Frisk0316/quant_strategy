"""
Historical replay backtest engine.

Feeds historical market/funding events through the same
Strategy -> Signal -> Order -> Fill -> Position path used elsewhere.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import pyarrow.parquet as pq
from loguru import logger

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


@dataclass
class ReplayRecorder:
    initial_equity: float
    order_log: list[dict] = field(default_factory=list)
    fill_log: list[dict] = field(default_factory=list)
    funding_log: list[dict] = field(default_factory=list)
    equity_samples: list[dict] = field(default_factory=list)

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

    def build_result(self, positions: PositionLedger, periods: int) -> ReplayBacktestResult:
        if not self.equity_samples:
            self.record_equity(0, self.initial_equity)

        equity_df = pd.DataFrame(self.equity_samples).drop_duplicates(subset=["ts"], keep="last")
        equity_df = equity_df.sort_values("ts")
        equity_series = pd.Series(equity_df["equity"].to_numpy(dtype=float), index=equity_df["ts"])
        returns = equity_series.pct_change().fillna(0.0)

        metrics = summary(returns, periods=periods)
        metrics.update(self._execution_metrics(returns))

        return ReplayBacktestResult(
            returns=returns,
            equity_curve=equity_series,
            metrics=metrics,
            order_log=pd.DataFrame(self.order_log),
            fill_log=pd.DataFrame(self.fill_log),
            funding_log=pd.DataFrame(self.funding_log),
            trade_log=pd.DataFrame(positions.get_trade_log()),
        )

    def _execution_metrics(self, returns: pd.Series) -> dict:
        """
        Compute replay-level execution and significance metrics.

        The replay ``dsr`` here is a single-run diagnostic equivalent in spirit
        to PSR(0), not a multiple-comparison-corrected DSR. True DSR must be
        computed via ``backtesting/cpcv.py`` with N equal to the actual number
        of parameter/strategy trials.
        """
        order_count = len(self.order_log)
        fill_count = len(self.fill_log)
        total_fees = float(sum(row["fee"] for row in self.fill_log))
        fill_notional = float(sum(row.get("notional_usd", 0.0) for row in self.fill_log))
        funding_cashflow = float(sum(row["cashflow"] for row in self.funding_log))
        ret_arr = returns.to_numpy(dtype=float)
        if len(ret_arr) < 4 or float(returns.std()) == 0.0:
            psr_val = 0.0
            dsr_val = 0.0
        else:
            psr_val = psr(ret_arr, sr_benchmark=0.0)
            dsr_val = psr_val
        return {
            "order_count": order_count,
            "fill_count": fill_count,
            "fill_rate": fill_count / order_count if order_count else 0.0,
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
) -> pd.DataFrame:
    """
    Load top-of-book snapshots.

    Preference order:
    1. ``ob_ticks_*.parquet`` snapshots
    2. FeedStore-style ``*/books.parquet`` files
    3. Synthetic L1 books derived from candle closes
    """
    inst_dir = Path(data_dir) / inst_id.replace("-", "_")
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
    mid = candles["close"].astype(float)
    half_spread = mid * synthetic_spread_bps / 20_000.0
    size = candles["vol"].astype(float).clip(lower=1.0) if "vol" in candles.columns else 1.0
    return pd.DataFrame({
        "ts": candles["ts"].astype("int64") // 1_000_000,
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
) -> pd.DataFrame:
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
                next_funding_time=int(getattr(row, "next_funding_time", 0) or 0),
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
    ) -> None:
        self._cfg = cfg
        self._strategy_names = strategy_names
        self._instrument_specs = instrument_specs or self._default_instrument_specs()
        self._periods = periods

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
            ("pairs_trading", PairsTradingStrategy(strat_cfg.pairs_trading.model_dump())),
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

        portfolio_mgr = PortfolioManager(
            bus=bus,
            positions=positions,
            risk_guard=risk_guard,
            target_ann_vol=0.20,
            instrument_specs=self._instrument_specs,
        )
        execution_model = ReplayExecutionModel(
            instrument_specs=self._instrument_specs,
            order_latency_ms=self._cfg.backtest.order_latency_ms,
            cancel_latency_ms=self._cfg.backtest.cancel_latency_ms,
            queue_fill_fraction=self._cfg.backtest.queue_fill_fraction,
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

        book_symbols = {
            getattr(strategy, "perp_symbol", None) for strategy in strategies
        } | {
            getattr(strategy, "spot_symbol", None) for strategy in strategies
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

        return recorder.build_result(positions, periods=self._periods)

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
        ct_val = validate_ct_val(float(specs.get("ctVal", 1.0)), payload.inst_id)
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
            ts=payload.ts / 1000,
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
            market_frames.append(load_l1_books(symbol, data_dir=data_dir, start=start, end=end, bar=bar))

    if "as_market_maker" in strategy_set:
        for symbol in cfg.strategies.as_market_maker.symbols:
            market_frames.append(load_l1_books(symbol, data_dir=data_dir, start=start, end=end, bar=bar))

    if "pairs_trading" in strategy_set:
        market_frames.append(load_l1_books(cfg.strategies.pairs_trading.symbol_y, data_dir=data_dir, start=start, end=end, bar=bar))
        market_frames.append(load_l1_books(cfg.strategies.pairs_trading.symbol_x, data_dir=data_dir, start=start, end=end, bar=bar))

    if "funding_carry" in strategy_set:
        perp = cfg.strategies.funding_carry.perp_symbol
        spot = cfg.strategies.funding_carry.spot_symbol
        market_frames.append(load_l1_books(perp, data_dir=data_dir, start=start, end=end, bar=bar))
        market_frames.append(
            load_l1_books(
                spot,
                data_dir=data_dir,
                start=start,
                end=end,
                bar=bar,
                fallback_inst_id=perp,
            )
        )
        funding_frames.append(load_funding_events(perp, data_dir=data_dir, start=start, end=end))

    market_df = _concat_non_empty(market_frames)
    funding_df = _concat_non_empty(funding_frames)
    return HistoricalEventFeed(market_events=market_df, funding_events=funding_df)


def _concat_non_empty(frames: list[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [df for df in frames if not df.empty]
    if not non_empty:
        return pd.DataFrame()
    return pd.concat(non_empty, ignore_index=True)


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
    engine = ReplayBacktestEngine(cfg, strategy_names=strategy_names, periods=periods)
    return engine.run_sync(feed)
