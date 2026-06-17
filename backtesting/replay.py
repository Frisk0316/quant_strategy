"""
Historical replay backtest engine.

Feeds historical market/funding events through the same
Strategy -> Signal -> Order -> Fill -> Position path used elsewhere.
"""
from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from pathlib import Path
from itertools import combinations
from typing import Any, Callable, Iterable, Optional

import pandas as pd
import pyarrow.parquet as pq
from loguru import logger

from backtesting.data_loader import load_candles as load_ohlcv_candles
from backtesting.data_loader import load_feature_events as load_external_feature_events
from backtesting.data_loader import load_funding as load_funding_rates
from backtesting.data_loader import load_trade_ticks as load_raw_trade_ticks
from backtesting.research_controls import (
    FILL_ALL_MAX_ORDER_NOTIONAL_USD,
    FILL_ALL_MAX_POS_PCT_EQUITY,
    FILL_ALL_STALE_QUOTE_PCT,
)
from okx_quant.analytics.dsr import psr
from okx_quant.analytics.performance import summary
from okx_quant.core.bus import EventBus
from okx_quant.core.config import AppConfig, load_config
from okx_quant.core.events import Event, EvtType, FeaturePayload, FillPayload, MarketPayload, OrderPayload
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
from okx_quant.strategies.base import Strategy
from okx_quant.strategies.funding_carry import FundingCarryStrategy
from okx_quant.strategies.external_features import CMEGapFillStrategy, FearGreedSentimentStrategy
from okx_quant.strategies.pairs_trading import PairsTradingStrategy
from okx_quant.strategies.technical_indicators import (
    EMACrossoverStrategy,
    MACDCrossoverStrategy,
    MACrossoverStrategy,
)


TERMINAL_TAKER_FEE_RATE = 0.0005


@dataclass
class ReplayBacktestResult:
    returns: pd.Series
    equity_curve: pd.Series
    metrics: dict
    order_log: pd.DataFrame
    fill_log: pd.DataFrame
    funding_log: pd.DataFrame
    trade_log: pd.DataFrame
    price_log: pd.DataFrame = field(default_factory=pd.DataFrame)
    signal_log: list[dict] = field(default_factory=list)
    risk_event_log: list[dict] = field(default_factory=list)
    rejected_log: list[dict] = field(default_factory=list)
    cancel_log: list[dict] = field(default_factory=list)
    funding_rate_log: pd.DataFrame = field(default_factory=pd.DataFrame)
    feature_event_log: pd.DataFrame = field(default_factory=pd.DataFrame)
    book_snapshot_log: pd.DataFrame = field(default_factory=pd.DataFrame)
    trade_tick_log: pd.DataFrame = field(default_factory=pd.DataFrame)
    validation: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayRecorder:
    initial_equity: float
    order_log: list[dict] = field(default_factory=list)
    fill_log: list[dict] = field(default_factory=list)
    funding_log: list[dict] = field(default_factory=list)
    equity_samples: list[dict] = field(default_factory=list)
    price_log: list[dict] = field(default_factory=list)
    book_snapshot_log: list[dict] = field(default_factory=list)
    trade_tick_log: list[dict] = field(default_factory=list)
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

    def record_price(self, payload: MarketPayload) -> None:
        if not payload.bids or not payload.asks:
            return
        try:
            bid = float(payload.bids[0][0])
            ask = float(payload.asks[0][0])
        except (IndexError, TypeError, ValueError):
            return
        mid = 0.5 * (bid + ask)
        self.price_log.append({
            "ts": int(payload.ts),
            "inst_id": payload.inst_id,
            "open": mid,
            "high": mid,
            "low": mid,
            "close": mid,
            "vol": float(payload.bids[0][1]) + float(payload.asks[0][1]),
        })

    def record_book_snapshot(self, payload: MarketPayload) -> None:
        if not payload.bids and not payload.asks:
            return

        def append_levels(side: str, levels: list) -> None:
            for level, row in enumerate(levels):
                try:
                    px = float(row[0])
                    sz = float(row[1])
                except (IndexError, TypeError, ValueError):
                    continue
                if not math.isfinite(px) or not math.isfinite(sz) or sz <= 0:
                    continue
                self.book_snapshot_log.append({
                    "ts": int(payload.ts),
                    "inst_id": payload.inst_id,
                    "side": side,
                    "level": level,
                    "px": px,
                    "sz": sz,
                    "seq_id": payload.seq_id,
                    "channel": payload.channel,
                    "action": payload.action,
                    "checksum": payload.checksum,
                    "source": "market_payload",
                })

        append_levels("bid", payload.bids)
        append_levels("ask", payload.asks)

    def record_trade_tick(self, payload: MarketPayload) -> None:
        try:
            price = float(payload.trade_price)
            size = float(payload.trade_size)
        except (TypeError, ValueError):
            return
        if not math.isfinite(price) or not math.isfinite(size) or price <= 0 or size <= 0:
            return
        self.trade_tick_log.append({
            "ts": int(payload.ts),
            "inst_id": payload.inst_id,
            "trade_id": payload.trade_id,
            "price": price,
            "size": size,
            "side": payload.trade_side,
            "source": "market_payload",
        })

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
        validation: Optional[dict[str, Any]] = None,
        metric_overrides: Optional[dict[str, Any]] = None,
    ) -> ReplayBacktestResult:
        if not self.equity_samples:
            self.record_equity(0, self.initial_equity)

        equity_df = pd.DataFrame(self.equity_samples).drop_duplicates(subset=["ts"], keep="last")
        equity_df = equity_df.sort_values("ts")
        equity_series = pd.Series(equity_df["equity"].to_numpy(dtype=float), index=equity_df["ts"])
        returns = equity_series.pct_change().fillna(0.0)

        metrics = summary(returns, periods=periods)
        metrics.update(self._execution_metrics(returns))
        if metric_overrides:
            metrics.update(metric_overrides)

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
            price_log=pd.DataFrame(self.price_log),
            book_snapshot_log=pd.DataFrame(self.book_snapshot_log),
            trade_tick_log=pd.DataFrame(self.trade_tick_log),
            signal_log=list(self.signal_log),
            risk_event_log=list(self.risk_event_log),
            rejected_log=rejected_log,
            cancel_log=cancel_log,
            validation=dict(validation or {}),
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
        if isinstance(val, pd.Timestamp) or not isinstance(val, (int, float, str)):
            return int(pd.Timestamp(val).timestamp() * 1000)
        raw = int(float(val))
        magnitude = abs(raw)
        if magnitude == 0:
            return 0
        if magnitude < 100_000_000_000:
            return raw * 1000
        if magnitude >= 100_000_000_000_000:
            return raw // 1_000_000
        return raw
    except (TypeError, ValueError, OSError):
        return 0


def _timestamp_series_to_ms(series: pd.Series) -> pd.Series:
    return series.map(_to_ms_int).astype("int64")


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


def _utc_ms(value: str) -> int:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return int(ts.timestamp() * 1000)


def _compute_data_coverage(
    feed: "HistoricalEventFeed",
    start: Optional[str],
    end: Optional[str],
    bar: str,
) -> dict:
    if feed.market_events.empty or start is None or end is None:
        return {
            "coverage_pct": 1.0,
            "bar": bar,
            "start": start,
            "end": end,
            "symbols": [],
            "note": "no_range_specified",
        }
    bar_seconds = _bar_to_seconds(bar)
    try:
        start_ts = _utc_ms(start)
        end_ts = _utc_ms(end)
    except Exception:
        return {
            "coverage_pct": 1.0,
            "bar": bar,
            "start": start,
            "end": end,
            "symbols": [],
            "note": "invalid_date_range",
        }
    expected_bars = max(1, (end_ts - start_ts) // (bar_seconds * 1000))
    per_symbol = []
    for inst_id, group in feed.market_events.groupby("inst_id"):
        actual = int(group["ts"].nunique())
        pct = round(min(1.0, actual / expected_bars), 4)
        per_symbol.append({
            "inst_id": str(inst_id),
            "actual_bars": actual,
            "expected_bars": int(expected_bars),
            "coverage_pct": pct,
        })
    overall = round(min(s["coverage_pct"] for s in per_symbol) if per_symbol else 1.0, 4)
    return {
        "coverage_pct": overall,
        "bar": bar,
        "start": start,
        "end": end,
        "symbols": per_symbol,
        "features": _feature_coverage(feed),
    }


def _feature_coverage(feed: "HistoricalEventFeed") -> list[dict]:
    feature_events = getattr(feed, "feature_events", pd.DataFrame())
    if feature_events.empty or "dataset_id" not in feature_events.columns:
        return []
    coverage: list[dict] = []
    for dataset_id, group in feature_events.groupby("dataset_id"):
        ts = pd.to_datetime(group["ts"], unit="ms", utc=True, errors="coerce")
        coverage.append({
            "dataset_id": str(dataset_id),
            "event_count": int(group["ts"].nunique()),
            "first_event_ts": ts.min().isoformat() if not ts.dropna().empty else None,
            "last_event_ts": ts.max().isoformat() if not ts.dropna().empty else None,
        })
    return coverage


def _check_data_coverage_gate(coverage: dict) -> None:
    if coverage.get("note") in {"no_range_specified", "invalid_date_range"}:
        return
    pct = float(coverage.get("coverage_pct", 1.0))
    if pct < 0.80:
        symbols = coverage.get("symbols") or []
        worst_symbols = sorted(
            symbols,
            key=lambda item: float(item.get("coverage_pct", 1.0)),
        )[:5]
        worst_msg = "; ".join(
            f"{item.get('inst_id')}={float(item.get('coverage_pct', 0.0)):.1%} "
            f"({item.get('actual_bars')}/{item.get('expected_bars')} bars)"
            for item in worst_symbols
        )
        detail = f" Lowest coverage: {worst_msg}." if worst_msg else ""
        raise ValueError(
            f"Gate 3: data coverage {pct:.1%} is below the 80 % threshold "
            f"(bar={coverage.get('bar')}, range={coverage.get('start')}..{coverage.get('end')}). "
            "Check data_dir, refresh derived candles, or reduce the date range."
            f"{detail}"
        )


def _apply_post_run_gates(
    result: ReplayBacktestResult,
    strategy_names: list[str],
    coverage: dict,
) -> None:
    fill_rate = float(result.metrics.get("fill_rate", 0.0))
    submitted = int(result.metrics.get("submitted_order_count", 0))
    gate2_warn = fill_rate < 0.05 and submitted > 0
    if gate2_warn:
        logger.warning(
            "Gate 2: fill_rate={:.1%} - check order_latency_ms and cancel_latency_ms in config/risk.yaml",
            fill_rate,
        )

    gate4_warn = False
    if "funding_carry" in strategy_names:
        settlements = int(result.metrics.get("funding_settlement_count", 0))
        gate4_warn = settlements == 0
        if gate4_warn:
            logger.warning(
                "Gate 4: funding_carry strategy has zero funding settlements - "
                "strategy may have entered but never collected funding. "
                "Check that the replay period spans at least one 8h settlement window."
            )

    result.validation.update({
        "gate2_fill_rate_warning": gate2_warn,
        "gate2_fill_rate": fill_rate,
        "gate3_data_coverage": coverage,
        "gate4_funding_coverage_warning": gate4_warn,
    })


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
            try:
                candles = load_ohlcv_candles(
                    fallback_inst_id,
                    bar=bar,
                    data_dir=data_dir,
                    start=start,
                    end=end,
                    backend="postgres",
                    dsn=dsn,
                )
            except FileNotFoundError:
                candles = pd.DataFrame()
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
                else _timestamp_series_to_ms(raw_ticks[ts_col])
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
            stored_books["ts"] = _timestamp_series_to_ms(stored_books["ts"])
            stored_books["inst_id"] = inst_id
            return stored_books[["ts", "inst_id", "bid_px_0", "bid_sz_0", "ask_px_0", "ask_sz_0"]]

    try:
        candles = load_ohlcv_candles(
            inst_id,
            bar=bar,
            data_dir=data_dir,
            start=start,
            end=end,
            backend="parquet",
        )
    except FileNotFoundError:
        candles = pd.DataFrame()
    if candles.empty and fallback_inst_id:
        try:
            candles = load_ohlcv_candles(
                fallback_inst_id,
                bar=bar,
                data_dir=data_dir,
                start=start,
                end=end,
                backend="parquet",
            )
        except FileNotFoundError:
            candles = pd.DataFrame()
    if candles.empty:
        return pd.DataFrame(columns=["ts", "inst_id", "bid_px_0", "bid_sz_0", "ask_px_0", "ask_sz_0"])
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
        "ts": _timestamp_series_to_ms(data["ts"]),
        "inst_id": inst_id,
        "bid_px_0": (mid - half_spread).astype(float),
        "bid_sz_0": size,
        "ask_px_0": (mid + half_spread).astype(float),
        "ask_sz_0": size,
    })


def load_trade_events(
    inst_id: str,
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    backend: str = "parquet",
    dsn: Optional[str] = None,
) -> pd.DataFrame:
    columns = ["ts", "inst_id", "trade_id", "price", "size", "side"]
    try:
        ticks = load_raw_trade_ticks(
            inst_id,
            data_dir=data_dir,
            start=start,
            end=end,
            backend=backend,
            dsn=dsn,
        )
    except (FileNotFoundError, ValueError):
        return pd.DataFrame(columns=columns)
    if ticks.empty:
        return pd.DataFrame(columns=columns)
    frame = ticks.copy()
    return pd.DataFrame({
        "ts": _timestamp_series_to_ms(frame["ts"]),
        "inst_id": inst_id,
        "trade_id": frame.get("trade_id", frame.get("tradeId", "")),
        "price": pd.to_numeric(frame["price"], errors="coerce"),
        "size": pd.to_numeric(frame["size"], errors="coerce"),
        "side": frame.get("side", ""),
    }).dropna(subset=["price", "size"])


def load_funding_events(
    inst_id: str,
    data_dir: str = "data/ticks",
    start: Optional[str] = None,
    end: Optional[str] = None,
    backend: str = "parquet",
    dsn: Optional[str] = None,
) -> pd.DataFrame:
    if backend == "postgres":
        try:
            funding = load_funding_rates(
                inst_id=inst_id,
                data_dir=data_dir,
                start=start,
                end=end,
                backend="postgres",
                dsn=dsn,
            )
        except FileNotFoundError:
            # data_loader.load_funding falls back to parquet when no DSN is
            # present; missing local funding files are tolerated.
            return pd.DataFrame(columns=["ts", "inst_id", "funding_rate", "next_funding_time"])
        if funding.empty:
            return pd.DataFrame(columns=["ts", "inst_id", "funding_rate", "next_funding_time"])
        frame = funding.reset_index(names="ts")
        return pd.DataFrame({
            "ts": _timestamp_series_to_ms(frame["ts"]),
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
        "ts": _timestamp_series_to_ms(funding["ts"]),
        "inst_id": inst_id,
        "funding_rate": funding["rate"].astype(float),
        "next_funding_time": funding.get("nextFundingTime", 0),
        "funding_interval_hours": funding.get("funding_interval_hours", None),
    })


class HistoricalEventFeed:
    def __init__(
        self,
        market_events: pd.DataFrame,
        funding_events: pd.DataFrame,
        feature_events: Optional[pd.DataFrame] = None,
        trade_events: Optional[pd.DataFrame] = None,
    ) -> None:
        self.market_events = market_events
        self.funding_events = funding_events
        self.feature_events = feature_events if feature_events is not None else pd.DataFrame()
        self.trade_events = trade_events if trade_events is not None else pd.DataFrame()

    def iter_events(self) -> Iterable[Event]:
        combined: list[tuple[int, int, Event]] = []

        for row in self.feature_events.itertuples(index=False):
            ts_ms = _to_ms_int(getattr(row, "ts", None))
            payload = FeaturePayload(
                dataset_id=str(row.dataset_id),
                ts=ts_ms,
                observed_at=_to_ms_int(getattr(row, "observed_at", None)) or None,
                published_at=_to_ms_int(getattr(row, "published_at", None)) or None,
                value_num=(
                    float(row.value_num)
                    if getattr(row, "value_num", None) is not None
                    and pd.notna(getattr(row, "value_num", None))
                    else None
                ),
                value_text=(
                    str(row.value_text)
                    if getattr(row, "value_text", None) is not None
                    and pd.notna(getattr(row, "value_text", None))
                    else None
                ),
                fields=(
                    getattr(row, "fields", {})
                    if isinstance(getattr(row, "fields", {}), dict)
                    else {}
                ),
                quality_status=str(getattr(row, "quality_status", "raw") or "raw"),
            )
            combined.append((ts_ms, 0, Event(EvtType.FEATURE, payload=payload)))

        for row in self.trade_events.itertuples(index=False):
            ts_ms = _to_ms_int(getattr(row, "ts", None))
            payload = MarketPayload(
                inst_id=row.inst_id,
                ts=ts_ms,
                bids=[],
                asks=[],
                seq_id=0,
                channel="trades",
                trade_id=(
                    str(getattr(row, "trade_id", ""))
                    if getattr(row, "trade_id", None) is not None
                    and pd.notna(getattr(row, "trade_id", None))
                    else None
                ),
                trade_price=float(getattr(row, "price")),
                trade_size=float(getattr(row, "size")),
                trade_side=(
                    str(getattr(row, "side", ""))
                    if getattr(row, "side", None) is not None
                    and pd.notna(getattr(row, "side", None))
                    else None
                ),
            )
            combined.append((ts_ms, 1, Event(EvtType.MARKET, payload=payload)))

        for row in self.market_events.itertuples(index=False):
            ts_ms = _to_ms_int(getattr(row, "ts", None))
            payload = MarketPayload(
                inst_id=row.inst_id,
                ts=ts_ms,
                bids=[[f"{float(row.bid_px_0):.10f}", f"{float(row.bid_sz_0):.10f}"]],
                asks=[[f"{float(row.ask_px_0):.10f}", f"{float(row.ask_sz_0):.10f}"]],
                seq_id=0,
                channel="books",
            )
            combined.append((ts_ms, 2, Event(EvtType.MARKET, payload=payload)))

        for row in self.funding_events.itertuples(index=False):
            ts_ms = _to_ms_int(getattr(row, "ts", None))
            payload = MarketPayload(
                inst_id=row.inst_id,
                ts=ts_ms,
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
            combined.append((ts_ms, 3, Event(EvtType.FUNDING, payload=payload)))

        combined.sort(key=lambda item: (item[0], item[1]))
        for _, _, event in combined:
            yield event


class ReplayBacktestEngine:
    # Authoritative sources whose ct_val came from a verified upstream, an
    # explicit per-symbol config override, or an exchange structural identity.
    # Any other source (OKX registry yaml, BTC/ETH hardcoded fallback) is
    # non-authoritative and downstream live-deployment gates should refuse it.
    AUTHORITATIVE_CT_VAL_SOURCES: tuple[str, ...] = (
        "db",
        "config_override",
        "spot_unit",
        "exchange_base_unit",
    )

    def __init__(
        self,
        cfg: AppConfig,
        strategy_names: Optional[list[str]] = None,
        instrument_specs: Optional[dict] = None,
        periods: int = 365 * 24,
        bar_seconds: int = 3600,
        liquidate_on_end: Optional[bool] = None,
    ) -> None:
        self._cfg = cfg
        self._strategy_names = strategy_names
        self._ct_val_sources: dict[str, dict] = {}
        exchange = str(getattr(self._cfg.storage, "primary_exchange", "okx") or "okx").lower()
        if instrument_specs:
            self._instrument_specs = instrument_specs
            # Caller-supplied specs are treated as per-symbol authoritative
            # overrides — this is the same trust level as a DB-backed value.
            for sym, spec in instrument_specs.items():
                ct_val = spec.get("ctVal") if isinstance(spec, dict) else None
                self._ct_val_sources[sym] = {
                    "value": float(ct_val) if ct_val is not None else None,
                    "source": "config_override",
                    "exchange": exchange,
                }
        else:
            self._instrument_specs = self._default_instrument_specs()
        self._periods = periods
        self._bar_seconds = bar_seconds
        self._liquidate_on_end = cfg.backtest.liquidate_on_end if liquidate_on_end is None else liquidate_on_end

    def _default_instrument_specs(self) -> dict:
        specs = {}
        exchange = str(getattr(self._cfg.storage, "primary_exchange", "okx") or "okx").lower()
        db_specs = self._load_db_instrument_specs(exchange)
        swap_symbols = set(self._cfg.system.symbols)
        swap_symbols.update({
            self._cfg.strategies.funding_carry.perp_symbol,
            self._cfg.strategies.pairs_trading.symbol_y,
            self._cfg.strategies.pairs_trading.symbol_x,
        })
        swap_symbols.update(self._cfg.strategies.ma_crossover.symbols)
        swap_symbols.update(self._cfg.strategies.ema_crossover.symbols)
        swap_symbols.update(self._cfg.strategies.macd_crossover.symbols)
        swap_symbols.update({
            self._cfg.strategies.fear_greed_sentiment.symbol,
            self._cfg.strategies.cme_gap_fill.symbol,
        })
        for symbol in swap_symbols:
            if "SWAP" not in symbol:
                continue
            ct_val, source = self._resolve_swap_ct_val(symbol, exchange, db_specs)
            specs[symbol] = {
                "ctVal": ct_val,
                "minSz": 0.01,
                "lotSz": 0.01,
                "tickSz": 0.1,
                "tdMode": "cross",
            }
            self._ct_val_sources[symbol] = {"value": ct_val, "source": source, "exchange": exchange}
        spot_symbols = set(self._cfg.system.spot_symbols)
        spot_symbols.add(self._cfg.strategies.funding_carry.spot_symbol)
        for symbol in spot_symbols:
            specs[symbol] = {"ctVal": 1.0, "minSz": 0.0001, "lotSz": 0.0001, "tickSz": 0.1, "tdMode": "cross"}
            # USDT spot pairs trade in base units so ctVal=1.0 is exact, not a fallback.
            self._ct_val_sources[symbol] = {"value": 1.0, "source": "spot_unit", "exchange": exchange}
        return specs

    def _load_db_instrument_specs(self, exchange: str = "okx") -> dict:
        """Query venue instrument specs for the run exchange, when DB is reachable.

        Returned shape: {symbol: {"ct_val": float}}. Empty dict when DSN is
        missing, unreachable, or query fails — caller falls through to the
        bundled YAML registry for OKX only. Errors are warnings, not exceptions,
        because the DB-primary architecture must degrade gracefully to parquet.
        """
        dsn = getattr(self._cfg.storage, "timescale_dsn", None)
        if not dsn:
            return {}
        try:
            from backtesting.data_loader import _dsn_reachable
        except Exception:
            return {}
        if not _dsn_reachable(dsn):
            return {}
        try:
            import asyncio

            import asyncpg

            async def _fetch() -> list:
                conn = await asyncpg.connect(dsn)
                try:
                    return await conn.fetch(
                        """
                        SELECT symbol, ct_val
                        FROM venue_instrument_specs
                        WHERE exchange = $1
                          AND ct_val IS NOT NULL
                        """,
                        exchange,
                    )
                finally:
                    await conn.close()

            rows = asyncio.run(_fetch())
        except Exception as exc:  # noqa: BLE001 — DB issues should not crash backtest
            logger.warning("Failed to load instrument ctVal from DB: {}", exc)
            return {}
        out: dict = {}
        for row in rows:
            ct_val = row.get("ct_val") if isinstance(row, dict) else row["ct_val"]
            symbol = row.get("symbol") if isinstance(row, dict) else row["symbol"]
            if ct_val is None:
                continue
            try:
                out[symbol] = {"ct_val": float(ct_val)}
            except (TypeError, ValueError):
                continue
        return out

    @staticmethod
    def _load_instrument_spec_registry() -> dict:
        """Read config/instrument_specs.yaml (bundled OKX SWAP spec registry).

        Cached on the class so repeated lookups don't re-read the file.
        """
        cache_attr = "_INSTRUMENT_SPEC_CACHE"
        cached = getattr(ReplayBacktestEngine, cache_attr, None)
        if cached is not None:
            return cached
        registry: dict = {}
        try:
            import yaml
            specs_path = Path(__file__).resolve().parents[1] / "config" / "instrument_specs.yaml"
            if specs_path.exists():
                data = yaml.safe_load(specs_path.read_text(encoding="utf-8")) or {}
                registry = data.get("swaps", {}) or {}
        except Exception as exc:  # noqa: BLE001 — file IO / yaml errors should not crash backtest
            logger.warning("Failed to load instrument_specs.yaml: {}", exc)
        setattr(ReplayBacktestEngine, cache_attr, registry)
        return registry

    @staticmethod
    def _resolve_swap_ct_val(
        symbol: str, exchange: str | dict = "okx", db_specs: dict | None = None
    ) -> tuple[float, str]:
        """Resolve a swap symbol's ctVal for a venue and report provenance.

        Lookup priority (highest = most authoritative):
          1. `db` — DB-backed `venue_instrument_specs(exchange, symbol)`.
          2. `exchange_base_unit` — Binance/Bybit USDT-M base-unit perps.
          3. `registry` — bundled OKX `config/instrument_specs.yaml` fallback.
          4. `hardcoded_btc_eth` — last-resort OKX 0.01 for BTC/ETH symbols only.
          5. Raise — unknown swap; never silently fall back to 1.0 because the
             ct_val multiplier directly drives PnL / notional / funding.
        """
        if isinstance(exchange, dict) and db_specs is None:
            db_specs = exchange
            exchange = "okx"
        exchange = str(exchange or "okx").lower()
        if db_specs and db_specs.get(symbol, {}).get("ct_val") is not None:
            return float(db_specs[symbol]["ct_val"]), "db"
        if exchange == "okx":
            registry = ReplayBacktestEngine._load_instrument_spec_registry()
            spec = registry.get(symbol)
            if spec and spec.get("ct_val") is not None:
                return float(spec["ct_val"]), "registry"
            if symbol.startswith(("BTC-", "ETH-")):
                logger.warning(
                    "Instrument ctVal missing; falling back to known OKX BTC/ETH swap ctVal=0.01",
                    inst_id=symbol,
                )
                return 0.01, "hardcoded_btc_eth"
        base_symbol = symbol.split("-", 1)[0].upper()
        if (
            exchange in {"binance", "bybit"}
            and symbol.upper().endswith("-USDT-SWAP")
            and not base_symbol.startswith("1000")
        ):
            return 1.0, "exchange_base_unit"
        logger.error(
            "Instrument ctVal missing for swap; seed venue_instrument_specs or add OKX registry fallback",
            inst_id=symbol,
            exchange=exchange,
        )
        raise ValueError(
            f"Missing ctVal for swap '{symbol}' on exchange '{exchange}'. Seed "
            f"venue_instrument_specs(exchange, symbol) or, for OKX, add it to "
            f"config/instrument_specs.yaml."
        )

    @staticmethod
    def _fallback_swap_ct_val(symbol: str, exchange: str = "okx") -> float:
        """Backwards-compatible wrapper that drops the provenance label.

        Existing call sites (and tests) only care about the numeric value;
        new code should call `_resolve_swap_ct_val` directly to also record
        provenance.
        """
        return ReplayBacktestEngine._resolve_swap_ct_val(symbol, exchange)[0]

    def _build_strategies(self) -> list[Strategy]:
        wanted = set(self._strategy_names or [])
        load_all = not wanted
        strategies: list[Strategy] = []
        strat_cfg = self._cfg.strategies
        candidates: list[tuple[str, Strategy]] = [
            ("funding_carry", FundingCarryStrategy(strat_cfg.funding_carry.model_dump())),
            (
                "pairs_trading",
                PairsTradingStrategy({
                    **strat_cfg.pairs_trading.model_dump(),
                    "bar_seconds": self._bar_seconds,
                }),
            ),
            ("ma_crossover", MACrossoverStrategy(strat_cfg.ma_crossover.model_dump())),
            ("ema_crossover", EMACrossoverStrategy(strat_cfg.ema_crossover.model_dump())),
            ("macd_crossover", MACDCrossoverStrategy(strat_cfg.macd_crossover.model_dump())),
            ("fear_greed_sentiment", FearGreedSentimentStrategy(strat_cfg.fear_greed_sentiment.model_dump())),
            ("cme_gap_fill", CMEGapFillStrategy(strat_cfg.cme_gap_fill.model_dump())),
        ]
        enabled = {
            "funding_carry": strat_cfg.funding_carry.enabled,
            "pairs_trading": strat_cfg.pairs_trading.enabled,
            "ma_crossover": strat_cfg.ma_crossover.enabled,
            "ema_crossover": strat_cfg.ema_crossover.enabled,
            "macd_crossover": strat_cfg.macd_crossover.enabled,
            "fear_greed_sentiment": strat_cfg.fear_greed_sentiment.enabled,
            "cme_gap_fill": strat_cfg.cme_gap_fill.enabled,
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
        if feed.market_events.empty and feed.funding_events.empty and feed.feature_events.empty:
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
        fill_all_signals = bool(getattr(self._cfg.backtest, "fill_all_signals", False))
        max_order_notional_usd = self._cfg.risk.max_order_notional_usd
        max_pos_pct_equity = self._cfg.risk.max_pos_pct_equity
        stale_quote_pct = self._cfg.risk.stale_quote_pct
        if fill_all_signals:
            max_order_notional_usd = max(max_order_notional_usd, FILL_ALL_MAX_ORDER_NOTIONAL_USD)
            max_pos_pct_equity = max(max_pos_pct_equity, FILL_ALL_MAX_POS_PCT_EQUITY)
            stale_quote_pct = max(stale_quote_pct, FILL_ALL_STALE_QUOTE_PCT)
        risk_guard = RiskGuard(
            equity_fn=positions.get_equity,
            drawdown_tracker=dd_tracker,
            max_order_notional_usd=max_order_notional_usd,
            max_pos_pct_equity=max_pos_pct_equity,
            max_leverage=self._cfg.risk.max_leverage,
            max_daily_loss_pct=self._cfg.risk.max_daily_loss_pct,
            soft_drawdown_pct=self._cfg.risk.soft_drawdown_pct,
            hard_drawdown_pct=self._cfg.risk.hard_drawdown_pct,
            stale_quote_pct=stale_quote_pct,
        )
        for strategy in strategies:
            risk_guard.register_strategy(strategy.name)

        execution_model = ReplayExecutionModel(
            instrument_specs=self._instrument_specs,
            order_latency_ms=self._cfg.backtest.order_latency_ms,
            cancel_latency_ms=self._cfg.backtest.cancel_latency_ms,
            queue_fill_fraction=self._cfg.backtest.queue_fill_fraction,
            fill_all_on_submit=fill_all_signals,
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
        exec_handler = ExecutionHandler(bus=bus, order_manager=order_manager, stale_quote_pct=stale_quote_pct)
        recorder = ReplayRecorder(initial_equity=self._cfg.system.equity_usd)
        original_risk_check = risk_guard.check
        last_risk_day: str | None = None

        def reset_daily_risk_if_needed(ts: int) -> None:
            nonlocal last_risk_day
            event_day = pd.Timestamp(int(ts), unit="ms", tz="UTC").date().isoformat()
            if last_risk_day is None:
                last_risk_day = event_day
                return
            if event_day != last_risk_day:
                risk_guard.reset_daily()
                last_risk_day = event_day

        def recording_risk_check(
            order: OrderPayload,
            current_pos_notional: float = 0.0,
            current_mid: float = 0.0,
        ) -> bool:
            allowed = original_risk_check(order, current_pos_notional, current_mid)
            if allowed:
                bypass_reason = getattr(risk_guard, "last_bypass_reason", None)
                if bypass_reason:
                    ts = execution_model.current_ts(order.inst_id)
                    recorder.record_risk_event(
                        ts=ts,
                        strategy=order.strategy,
                        inst_id=order.inst_id,
                        side=order.side,
                        px=float(order.px),
                        sz=float(order.sz),
                        notional_usd=order.notional_usd,
                        reason=f"allowed_reduce_only_bypass:{bypass_reason}",
                        current_position=current_pos_notional,
                        position_limit=max_pos_pct_equity * positions.get_equity(),
                        current_equity=positions.get_equity(),
                        metadata={"reduce_only": True},
                    )
                return True
            block_reason = getattr(risk_guard, "last_block_reason", None) or "risk_guard_block"
            ts = execution_model.current_ts(order.inst_id)
            execution_model.rejected_log.append({
                "ts": ts,
                "cl_ord_id": order.cl_ord_id,
                "inst_id": order.inst_id,
                "side": order.side,
                "px": float(order.px),
                "reason": block_reason,
            })
            recorder.record_risk_event(
                ts=ts,
                strategy=order.strategy,
                inst_id=order.inst_id,
                side=order.side,
                px=float(order.px),
                sz=float(order.sz),
                notional_usd=order.notional_usd,
                reason=block_reason,
                current_position=current_pos_notional,
                position_limit=max_pos_pct_equity * positions.get_equity(),
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
        } | {
            symbol
            for strategy in strategies
            for symbol in getattr(strategy, "symbols", [])
        } | {
            getattr(strategy, "symbol", None) for strategy in strategies
        } | set(self._cfg.system.symbols) | set(self._cfg.system.spot_symbols)
        books = {symbol: OkxBook(symbol) for symbol in book_symbols if symbol}

        async def on_market_event(event: Event) -> None:
            payload = event.payload
            if payload.channel == "books":
                reset_daily_risk_if_needed(payload.ts)
                book = books.get(payload.inst_id)
                if book is not None:
                    self._apply_book_snapshot(book, payload)
                await exec_handler.on_market(event)
                portfolio_mgr.on_market(payload)
                dd_tracker.update(positions.get_equity())
                recorder.record_equity(payload.ts, positions.get_equity())
                recorder.record_price(payload)
                recorder.record_book_snapshot(payload)
                for strategy in strategies:
                    if strategy.is_active:
                        signal = await strategy.on_market(event, books.get(payload.inst_id))
                        if signal:
                            recorder.record_signal(signal, payload.ts)
                            await bus.put(Event(EvtType.SIGNAL, payload=signal))
            elif payload.channel == "trades":
                reset_daily_risk_if_needed(payload.ts)
                recorder.record_trade_tick(payload)
                for strategy in strategies:
                    if strategy.is_active:
                        signal = await strategy.on_market(event, books.get(payload.inst_id))
                        if signal:
                            recorder.record_signal(signal, payload.ts)
                            await bus.put(Event(EvtType.SIGNAL, payload=signal))

        async def on_funding_event(event: Event) -> None:
            payload = event.payload
            reset_daily_risk_if_needed(payload.ts)
            self._settle_funding(payload, positions, recorder)
            recorder.record_equity(payload.ts, positions.get_equity())
            for strategy in strategies:
                if strategy.is_active:
                    signal = await strategy.on_market(event)
                    if signal:
                        recorder.record_signal(signal, payload.ts)
                        await bus.put(Event(EvtType.SIGNAL, payload=signal))

        async def on_feature_event(event: Event) -> None:
            payload = event.payload
            reset_daily_risk_if_needed(payload.ts)
            for strategy in strategies:
                if strategy.is_active:
                    signal = await strategy.on_market(event)
                    if signal:
                        recorder.record_signal(signal, payload.ts)
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
        bus.subscribe(EvtType.FEATURE, on_feature_event)
        bus.subscribe(EvtType.SIGNAL, on_signal_event)
        bus.subscribe(EvtType.ORDER, on_order_event)
        bus.subscribe(EvtType.FILL, on_fill_event)

        dispatch_task = asyncio.create_task(bus.dispatch_loop())
        last_event_ts = 0
        try:
            for event in feed.iter_events():
                last_event_ts = int(getattr(event.payload, "ts", last_event_ts) or last_event_ts)
                await bus.put(event)
                # Drain each historical timestamp through downstream
                # signal/order/fill handlers before advancing replay time.
                await bus.join()
        finally:
            dispatch_task.cancel()
            await asyncio.gather(dispatch_task, return_exceptions=True)

        execution_model.close_all()
        terminal_validation, terminal_metrics = self._liquidate_terminal_positions(
            positions=positions,
            recorder=recorder,
            books=books,
            ts=last_event_ts,
            liquidate_on_end=self._liquidate_on_end,
        )
        terminal_validation["fill_all_signals"] = fill_all_signals
        if fill_all_signals:
            terminal_validation["fill_all_signals_controls"] = {
                "max_order_notional_usd": max_order_notional_usd,
                "max_pos_pct_equity": max_pos_pct_equity,
                "stale_quote_pct": stale_quote_pct,
                "execution_model": "fill_all_on_submit",
            }
        feature_validation = self._collect_feature_validation(strategies)
        if feature_validation:
            terminal_validation["external_features"] = feature_validation

        result = recorder.build_result(
            positions,
            periods=self._periods,
            execution_model=execution_model,
            validation=terminal_validation,
            metric_overrides=terminal_metrics,
        )
        result.funding_rate_log = feed.funding_events.copy()
        result.feature_event_log = feed.feature_events.copy()
        return result

    @staticmethod
    def _collect_feature_validation(strategies: list[Strategy]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for strategy in strategies:
            status = getattr(strategy, "coverage_status", None)
            if isinstance(status, dict):
                out[str(strategy.name)] = dict(status)
        return out

    def _liquidate_terminal_positions(
        self,
        *,
        positions: PositionLedger,
        recorder: ReplayRecorder,
        books: dict[str, OkxBook],
        ts: int,
        liquidate_on_end: bool,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        terminal_positions_before = self._position_snapshot(positions.get_all_positions())
        missing_prices: list[dict[str, str]] = []
        price_fallbacks: list[dict[str, Any]] = []
        fill_count = 0
        liquidation_notional = 0.0

        if liquidate_on_end:
            for inst_id, pos in list(positions.get_all_positions().items()):
                if abs(pos.size) < 1e-9:
                    continue
                price, source = self._terminal_liquidation_price(inst_id, pos, books)
                if price <= 0:
                    missing_prices.append({"inst_id": inst_id, "reason": source})
                    continue
                if source != "last_mid":
                    price_fallbacks.append({"inst_id": inst_id, "source": source, "price": price})

                ct_val = self._terminal_ct_val(inst_id, pos.ct_val)
                notional_usd = self._terminal_notional_usd(inst_id, pos.size, price, ct_val)
                fee = notional_usd * TERMINAL_TAKER_FEE_RATE
                side = "sell" if pos.size > 0 else "buy"
                strategy = pos.strategy or "terminal_liquidation"
                metadata = {
                    "action": "terminal_liquidation",
                    "liquidate_on_end": True,
                    "execution_model": "terminal_liquidation",
                    "terminal_price_source": source,
                    "ct_val": ct_val,
                    "fee_rate": TERMINAL_TAKER_FEE_RATE,
                    "notional_usd": notional_usd,
                }
                fill = FillPayload(
                    cl_ord_id=f"terminal-{inst_id.replace('-', '')}-{fill_count + 1}",
                    ord_id=f"terminal-liquidation-{fill_count + 1}",
                    inst_id=inst_id,
                    fill_px=price,
                    fill_sz=abs(pos.size),
                    fee=fee,
                    fee_ccy="USDT",
                    side=side,
                    ts=int(ts),
                    strategy=strategy,
                    state="filled",
                    metadata=metadata,
                )
                recorder.record_fill(fill)
                positions.on_fill(
                    inst_id=fill.inst_id,
                    side=fill.side,
                    fill_px=fill.fill_px,
                    fill_sz=fill.fill_sz,
                    fee=abs(fill.fee),
                    strategy=fill.strategy,
                    ts=fill.ts,
                    metadata=dict(fill.metadata),
                )
                fill_count += 1
                liquidation_notional += notional_usd

        terminal_positions_after = self._position_snapshot(positions.get_all_positions())
        if fill_count > 0:
            recorder.record_equity(int(ts), positions.get_equity())

        terminal_bankrupt = False
        if liquidate_on_end:
            terminal_bankrupt = bool(missing_prices or terminal_positions_after)

        validation = {
            "liquidate_on_end": liquidate_on_end,
            "terminal_positions_before": terminal_positions_before,
            "terminal_positions_after": terminal_positions_after,
            "terminal_liquidation_fill_count": fill_count,
            "terminal_liquidation_notional_usd": liquidation_notional,
            "terminal_liquidation_missing_prices": missing_prices,
            "terminal_liquidation_price_fallbacks": price_fallbacks,
            "terminal_positions_closed": not terminal_positions_after,
        }
        metrics = {
            "bankrupt": terminal_bankrupt,
            "terminal_open_position_count": len(terminal_positions_after),
            "terminal_liquidation_fill_count": fill_count,
            "terminal_liquidation_notional_usd": liquidation_notional,
        }
        return validation, metrics

    def _terminal_liquidation_price(
        self,
        inst_id: str,
        pos,
        books: dict[str, OkxBook],
    ) -> tuple[float, str]:
        book = books.get(inst_id)
        if book is not None:
            bid, _ = book.best_bid()
            ask, _ = book.best_ask()
            if bid > 0 and math.isfinite(ask) and ask > 0:
                return 0.5 * (bid + ask), "last_mid"
        if pos.last_price > 0:
            return float(pos.last_price), "last_price"
        return 0.0, "missing_last_mid_and_last_price"

    def _terminal_ct_val(self, inst_id: str, fallback: float = 1.0) -> float:
        specs = self._instrument_specs.get(inst_id, {})
        raw = specs.get("ctVal", fallback)
        return validate_ct_val(float(raw), inst_id)

    @staticmethod
    def _terminal_notional_usd(inst_id: str, size: float, price: float, ct_val: float) -> float:
        if "SWAP" in inst_id:
            return abs(size) * ct_val * price
        return abs(size) * price

    @staticmethod
    def _position_snapshot(positions: dict) -> dict[str, dict[str, Any]]:
        snapshot: dict[str, dict[str, Any]] = {}
        for inst_id, pos in sorted(positions.items()):
            if abs(pos.size) < 1e-9:
                continue
            snapshot[inst_id] = {
                "inst_id": pos.inst_id,
                "size": float(pos.size),
                "avg_entry": float(pos.avg_entry),
                "ct_val": float(pos.ct_val),
                "last_price": float(pos.last_price),
                "strategy": pos.strategy,
                "unrealized_pnl": float(pos.unrealized_pnl),
                "notional": float(pos.notional),
            }
        return snapshot

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
    feature_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []

    strategy_set = set(strategy_names)
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

    technical_symbols: set[str] = set()
    if "ma_crossover" in strategy_set:
        technical_symbols.update(cfg.strategies.ma_crossover.symbols)
    if "ema_crossover" in strategy_set:
        technical_symbols.update(cfg.strategies.ema_crossover.symbols)
    if "macd_crossover" in strategy_set:
        technical_symbols.update(cfg.strategies.macd_crossover.symbols)
    for symbol in sorted(technical_symbols):
        market_frames.append(load_l1_books(
            symbol,
            data_dir=data_dir,
            start=start,
            end=end,
            bar=bar,
            backend=cfg.storage.candle_backend,
            dsn=cfg.storage.timescale_dsn,
        ))

    if "fear_greed_sentiment" in strategy_set:
        params = cfg.strategies.fear_greed_sentiment
        market_frames.append(load_l1_books(
            params.symbol,
            data_dir=data_dir,
            start=start,
            end=end,
            bar=bar,
            backend=cfg.storage.candle_backend,
            dsn=cfg.storage.timescale_dsn,
        ))
        feature_frames.append(load_external_feature_events(
            params.dataset_id,
            start=start,
            end=end,
            backend="postgres",
            dsn=cfg.storage.timescale_dsn,
            lookback_seconds=params.max_age_seconds,
        ))

    if "cme_gap_fill" in strategy_set:
        params = cfg.strategies.cme_gap_fill
        market_frames.append(load_l1_books(
            params.symbol,
            data_dir=data_dir,
            start=start,
            end=end,
            bar=bar,
            backend=cfg.storage.candle_backend,
            dsn=cfg.storage.timescale_dsn,
        ))
        feature_frames.append(load_external_feature_events(
            params.dataset_id,
            start=start,
            end=end,
            backend="postgres",
            dsn=cfg.storage.timescale_dsn,
            lookback_seconds=params.max_age_seconds,
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
    feature_df = _concat_non_empty(feature_frames)
    trade_df = _concat_non_empty(trade_frames)
    return HistoricalEventFeed(
        market_events=market_df,
        funding_events=funding_df,
        feature_events=feature_df,
        trade_events=trade_df,
    )


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
    frames = [
        df for df in [feed.market_events, feed.funding_events, feed.feature_events, feed.trade_events]
        if not df.empty and "ts" in df.columns
    ]
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
    instrument_specs: Optional[dict] = None,
    liquidate_on_end: Optional[bool] = None,
    runner: ReplayValidationRunner | None = None,
) -> Callable[[pd.DataFrame, pd.DataFrame], dict[str, Any]]:
    """
    Return the strategy_fn expected by WalkForward.evaluate() and CPCV.evaluate().

    The callback replays the supplied OOS/test window through the full event
    stack and returns a dict with a returns Series aligned to test_data.index.
    """
    replay_runner = runner or run_replay_backtest

    def _run_window(start: str, end: str) -> ReplayBacktestResult:
        kwargs = {
            "strategy_names": strategy_names,
            "cfg": cfg,
            "data_dir": data_dir,
            "start": start,
            "end": end,
            "bar": bar,
            "periods": periods,
        }
        if instrument_specs is not None:
            kwargs["instrument_specs"] = instrument_specs
        if liquidate_on_end is not None:
            kwargs["liquidate_on_end"] = liquidate_on_end
        return replay_runner(**kwargs)

    def strategy_fn(train_data: pd.DataFrame, test_data: pd.DataFrame) -> dict[str, Any]:
        is_metrics: dict[str, Any] | None = None
        if include_train_metrics and not train_data.empty:
            is_start, is_end = _window_bounds(train_data)
            try:
                is_result = _run_window(is_start, is_end)
                is_metrics = dict(is_result.metrics)
            except ValueError as exc:
                if "empty historical feed" not in str(exc):
                    raise
                is_metrics = {"empty_replay_window": True}

        oos_start, oos_end = _window_bounds(test_data)
        try:
            oos_result = _run_window(oos_start, oos_end)
        except ValueError as exc:
            if "empty historical feed" not in str(exc):
                raise
            return {
                "returns": pd.Series(0.0, index=_as_utc_index(test_data.index)),
                "is_metrics": is_metrics or {},
                "oos_metrics": {
                    "total_return": 0.0,
                    "sharpe": 0.0,
                    "max_drawdown": 0.0,
                    "empty_replay_window": True,
                },
                "oos_order_count": 0,
                "oos_fill_count": 0,
                "returns_source": "empty_replay_window",
            }
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
    instrument_specs: Optional[dict] = None,
    liquidate_on_end: Optional[bool] = None,
    runner: ReplayValidationRunner | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
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

    def _emit(progress: int, message: str, **extra: Any) -> None:
        if progress_callback:
            progress_callback({
                "progress": max(85, min(99, int(progress))),
                "message": message,
                **extra,
            })

    has_wf = validate_mode in {"wf", "both"}
    has_cpcv = validate_mode in {"cpcv", "both"}
    wf_start, wf_end = (86, 93) if has_cpcv else (86, 99)
    cpcv_start, cpcv_end = (94, 99) if has_wf else (86, 99)

    replay_runner = runner or run_replay_backtest
    if validate_mode in {"wf", "both"}:
        wf = WalkForward(is_days=wf_is_days, oos_days=wf_oos_days)

        def _wf_progress(update: dict[str, Any]) -> None:
            current = int(update.get("current") or 1)
            total = max(int(update.get("total") or 1), 1)
            pct = wf_start + int((current - 1) / total * max(wf_end - wf_start, 1))
            _emit(
                pct,
                f"Walk-Forward window {current}/{total}",
                phase="walk_forward",
                current=current,
                total=total,
            )

        wf_results = wf.evaluate(
            df,
            make_replay_strategy_fn(
                strategy_names=strategy_names,
                cfg=cfg,
                data_dir=data_dir,
                bar=bar,
                periods=periods,
                include_train_metrics=True,
                instrument_specs=instrument_specs,
                liquidate_on_end=liquidate_on_end,
                runner=replay_runner,
            ),
            periods=periods,
            progress_callback=_wf_progress,
        )
        validation["walk_forward"] = _summarize_walk_forward(wf_results)

    if validate_mode in {"cpcv", "both"}:
        cpcv = CPCV(
            n_splits=cpcv_n_splits,
            k_test=cpcv_k_test,
            embargo_pct=cpcv_embargo_pct,
            purge_size=cpcv_purge_size,
        )

        def _cpcv_progress(update: dict[str, Any]) -> None:
            current = int(update.get("current") or 1)
            total = max(int(update.get("total") or 1), 1)
            pct = cpcv_start + int((current - 1) / total * max(cpcv_end - cpcv_start, 1))
            groups = update.get("test_groups")
            group_label = f" groups {list(groups)}" if groups is not None else ""
            _emit(
                pct,
                f"CPCV combination {current}/{total}{group_label}",
                phase="cpcv",
                current=current,
                total=total,
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
                instrument_specs=instrument_specs,
                liquidate_on_end=liquidate_on_end,
                runner=replay_runner,
            ),
            periods=periods,
            n_trials=n_trials,
            progress_callback=_cpcv_progress,
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
    instrument_specs: Optional[dict] = None,
    liquidate_on_end: Optional[bool] = None,
) -> ReplayBacktestResult:
    cfg = cfg or load_config()
    # Safety net for the DB-primary default. Treat both "no DSN" and "DSN
    # unreachable" (DB process not running) as a trigger to drop to parquet,
    # otherwise the very first load_candles call crashes with
    # ConnectionRefusedError.
    if getattr(cfg.storage, "candle_backend", "parquet") == "postgres":
        from backtesting.data_loader import _dsn_reachable as _dsn_probe
        if not cfg.storage.timescale_dsn or not _dsn_probe(cfg.storage.timescale_dsn):
            cfg.storage = cfg.storage.model_copy(update={"candle_backend": "parquet"})
    feed = build_feed_for_strategies(cfg, strategy_names=strategy_names, data_dir=data_dir, start=start, end=end, bar=bar)
    coverage = _compute_data_coverage(feed, start, end, bar)
    _check_data_coverage_gate(coverage)
    engine = ReplayBacktestEngine(
        cfg,
        strategy_names=strategy_names,
        instrument_specs=instrument_specs,
        periods=periods,
        bar_seconds=_bar_to_seconds(bar),
        liquidate_on_end=liquidate_on_end,
    )
    result = engine.run_sync(feed)
    _attach_ct_val_provenance(result, engine)
    _apply_post_run_gates(result, strategy_names, coverage)
    return result


def _attach_ct_val_provenance(result: Any, engine: "ReplayBacktestEngine") -> None:
    """Record the source of every symbol's ctVal on `result.validation`.

    Drives the live-deployment gate: backtests whose ctVal came from anything
    other than DB / config_override / spot_unit must NOT be promoted to live or
    shadow trading without explicit human override. The full per-symbol map is
    preserved so reviewers can audit exactly where each value came from.
    """
    sources = getattr(engine, "_ct_val_sources", {}) or {}
    authoritative = ReplayBacktestEngine.AUTHORITATIVE_CT_VAL_SOURCES
    non_authoritative = {
        sym: info for sym, info in sources.items()
        if info.get("source") not in authoritative
    }
    run_exchanges = {info.get("exchange") for info in sources.values() if info.get("exchange")}
    payload = {
        "ct_val_sources": {
            sym: {"value": info.get("value"), "source": info.get("source"), "exchange": info.get("exchange")}
            for sym, info in sources.items()
        },
        "ct_val_all_authoritative": len(non_authoritative) == 0,
        "ct_val_non_authoritative_symbols": sorted(non_authoritative.keys()),
        "ct_val_gate_passed": len(non_authoritative) == 0,
        "exchange": next(iter(run_exchanges)) if len(run_exchanges) == 1 else "+".join(sorted(map(str, run_exchanges))),
    }
    try:
        existing = getattr(result, "validation", None) or {}
        if not isinstance(existing, dict):
            existing = dict(existing) if existing else {}
        existing.update(payload)
        setattr(result, "validation", existing)
    except Exception as exc:  # noqa: BLE001 — ct_val tracking is informational, never blocks the run
        logger.warning("Failed to attach ct_val provenance to result.validation: {}", exc)
