"""Vectorized C3 Fear & Greed long/flat research backtest."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backtesting.data_loader import load_candles, load_external_observations, load_funding
from backtesting.ohlcv_rotation_backtest import BacktestResult, compute_metrics, compute_turnover
from okx_quant.strategies.external_features import _canonical_fng_label, _optional_float


@dataclass
class C3SentimentParams:
    symbol: str = "BTC-USDT-SWAP"
    dataset_id: str = "fear_greed_btc"
    bar: str = "1m"
    max_age_seconds: int = 48 * 3600
    extreme_fear_label: str = "Extreme Fear"
    exit_labels: tuple[str, ...] = ("Greed", "Extreme Greed")
    extreme_fear_threshold: float = 25.0
    exit_value_threshold: float = 51.0
    fee_bps: float = 2.0
    slippage_bps: float = 2.0


def _daily_close(close: pd.DataFrame) -> pd.DataFrame:
    return close.sort_index().resample("1D").last().dropna(how="all")


def _normalize_fng(fng: pd.DataFrame) -> pd.DataFrame:
    if fng.empty:
        return pd.DataFrame(columns=["published_at", "value_num", "value_text"])
    out = fng.copy()
    observed = pd.to_datetime(out.get("observed_at"), utc=True, errors="coerce")
    published = pd.to_datetime(out.get("published_at"), utc=True, errors="coerce").fillna(observed)
    out["published_at"] = published.dt.tz_convert("UTC").dt.tz_localize(None)
    out["published_day"] = out["published_at"].dt.normalize()
    out["value_text"] = out.get("value_text", "").map(_canonical_fng_label)
    out["value_num"] = out.get("value_num").map(_optional_float)
    return out.dropna(subset=["published_at"]).sort_values("published_at")


def _target_weights(close_daily: pd.DataFrame, fng: pd.DataFrame, params: C3SentimentParams) -> pd.DataFrame:
    out = pd.DataFrame(0.0, index=close_daily.index, columns=[params.symbol])
    events = _normalize_fng(fng).drop_duplicates("published_day", keep="last").set_index("published_day")
    active = False
    exit_labels = {_canonical_fng_label(label) for label in params.exit_labels}
    entry_label = _canonical_fng_label(params.extreme_fear_label)
    for ts in out.index:
        day = pd.Timestamp(ts).normalize()
        if day in events.index:
            row = events.loc[day]
            age = (pd.Timestamp(ts) - pd.Timestamp(row["published_at"])).total_seconds()
            if 0 <= age <= params.max_age_seconds:
                label = _canonical_fng_label(row.get("value_text", ""))
                value_num = _optional_float(row.get("value_num"))
                is_entry = label == entry_label or (
                    value_num is not None and value_num <= params.extreme_fear_threshold
                )
                is_exit = label in exit_labels or (
                    value_num is not None and value_num >= params.exit_value_threshold
                )
                if is_entry and not active:
                    active = True
                elif is_exit and active:
                    active = False
        out.loc[ts, params.symbol] = 1.0 if active else 0.0
    return out


def _funding_returns(positions: pd.DataFrame, funding: pd.DataFrame, symbol: str) -> pd.Series:
    rates = funding.reindex(index=positions.index, columns=[symbol]).fillna(0.0)
    return -(positions[symbol] * rates[symbol])


def run_c3_sentiment_backtest(
    close: pd.DataFrame,
    funding: pd.DataFrame,
    fng: pd.DataFrame,
    params: C3SentimentParams,
) -> BacktestResult:
    close = close.sort_index().reindex(columns=[params.symbol])
    target_daily = _target_weights(_daily_close(close), fng, params)
    target = target_daily.shift(1).reindex(close.index).ffill().fillna(0.0)
    positions = target.shift(1).fillna(0.0)
    gross_returns = (positions[params.symbol] * close[params.symbol].pct_change().fillna(0.0))
    funding_return = _funding_returns(positions, funding, params.symbol)
    cost = compute_turnover(target) * (params.fee_bps + params.slippage_bps) / 10_000
    returns = gross_returns + funding_return - cost
    equity = (1.0 + returns).cumprod()
    daily_returns = (1.0 + returns).resample("1D").prod() - 1.0
    metrics = compute_metrics(equity, returns, target, pd.DataFrame(), params.bar)
    metrics.update({
        "validation_status": "research_backtest",
        "idealized_fill": False,
        "funding_cashflow": float(funding_return.sum()),
    })
    return BacktestResult(equity, daily_returns, positions, target_daily, pd.DataFrame(), metrics)


def load_c3_inputs(
    symbol: str = "BTC-USDT-SWAP",
    *,
    dataset_id: str = "fear_greed_btc",
    bar: str = "1m",
    data_dir: str = "data/ticks",
    start: str | None = None,
    end: str | None = None,
    backend: str = "postgres",
    dsn: str | None = None,
    exchange: str = "binance",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candles = load_candles(
        symbol,
        bar=bar,
        data_dir=data_dir,
        start=start,
        end=end,
        backend=backend,  # type: ignore[arg-type]
        dsn=dsn,
        exchange=exchange,
    )
    funding = load_funding(symbol, data_dir=data_dir, start=start, end=end, backend=backend, dsn=dsn)["rate"]
    fng = load_external_observations(
        dataset_id,
        start=start,
        end=end,
        backend="postgres",
        dsn=dsn,
        lookback_seconds=48 * 3600,
    )
    return pd.DataFrame({symbol: candles["close"]}), pd.DataFrame({symbol: funding}), fng
