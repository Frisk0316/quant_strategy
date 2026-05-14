"""
Daily winner rotation backtest.

This is a deliberately simple validation strategy:
  - observe a basket of daily OHLCV candles
  - rank instruments by yesterday's daily return (close / open - 1)
  - buy the best instrument at today's open
  - sell it at today's close

The goal is to force one round trip per complete trading day so data loading,
1m-to-1D aggregation, cost application, trade extraction, and artifact writing
can be checked without the entry filters used by research strategies.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DailyWinnerParams:
    universe: list[str]
    fee_bps: float = 2.0
    slippage_bps: float = 2.0
    initial_equity: float = 1.0


@dataclass
class DailyWinnerBacktestResult:
    equity_curve: pd.Series
    daily_returns: pd.Series
    target_weights: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict


def _normalize_daily_index(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("daily winner input dataframes must use a DatetimeIndex")
    out = df.sort_index().copy()
    if out.index.tz is not None:
        out.index = out.index.tz_convert("UTC").tz_localize(None)
    out.index = out.index.normalize()
    out = out[~out.index.duplicated(keep="last")]
    return out


def _build_open_close_panels(
    dfs: dict[str, pd.DataFrame],
    universe: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    opens: dict[str, pd.Series] = {}
    closes: dict[str, pd.Series] = {}
    missing: list[str] = []

    for inst in universe:
        df = dfs.get(inst)
        if df is None or df.empty:
            missing.append(inst)
            continue
        required = {"open", "close"}
        if not required.issubset(df.columns):
            raise ValueError(f"{inst} is missing required columns: {sorted(required - set(df.columns))}")
        daily = _normalize_daily_index(df)
        opens[inst] = pd.to_numeric(daily["open"], errors="coerce")
        closes[inst] = pd.to_numeric(daily["close"], errors="coerce")

    if not opens:
        raise ValueError("no daily OHLCV data loaded for daily winner backtest")

    open_panel = pd.DataFrame(opens).sort_index()
    close_panel = pd.DataFrame(closes).sort_index()
    common_index = open_panel.index.intersection(close_panel.index)
    open_panel = open_panel.loc[common_index]
    close_panel = close_panel.loc[common_index]
    return open_panel, close_panel


def _max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    return float(drawdown.min())


def _compute_metrics(
    equity_curve: pd.Series,
    daily_returns: pd.Series,
    trades: pd.DataFrame,
    expected_trade_days: int,
    skipped_trade_days: int,
    universe_size: int,
) -> dict:
    total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1.0) if len(equity_curve) else 0.0

    if len(equity_curve) > 1:
        elapsed_days = max((equity_curve.index[-1] - equity_curve.index[0]).days, 1)
        annualized_return = (1.0 + total_return) ** (365.25 / elapsed_days) - 1.0
    else:
        annualized_return = 0.0

    if len(daily_returns) > 1:
        ret_std = daily_returns.std(ddof=1)
        sharpe = float(daily_returns.mean() / ret_std * math.sqrt(365.25)) if ret_std > 0 else 0.0
        ann_vol = float(ret_std * math.sqrt(365.25))
    else:
        sharpe = 0.0
        ann_vol = 0.0
    max_drawdown = _max_drawdown(equity_curve)
    calmar = annualized_return / abs(max_drawdown) if max_drawdown < 0 else 0.0
    n_trades = int(len(trades))

    if n_trades:
        wins = trades["net_return"][trades["net_return"] > 0]
        losses = trades["net_return"][trades["net_return"] <= 0]
        win_rate = float(len(wins) / n_trades)
        profit_factor = float(wins.sum() / abs(losses.sum())) if not losses.empty and losses.sum() != 0 else np.inf
        most_selected = str(trades["inst_id"].mode().iloc[0])
        first_trade_ts = str(trades["entry_ts"].min())
        last_trade_ts = str(trades["exit_ts"].max())
    else:
        win_rate = 0.0
        profit_factor = 0.0
        most_selected = ""
        first_trade_ts = ""
        last_trade_ts = ""

    return {
        "strategy": "daily_winner",
        "universe_size": int(universe_size),
        "total_return": total_return,
        "annualized_return": float(annualized_return),
        "annualized_volatility": ann_vol,
        "sharpe": float(sharpe),
        "max_drawdown": max_drawdown,
        "calmar": float(calmar),
        "number_of_trades": n_trades,
        "expected_trade_days": int(expected_trade_days),
        "skipped_trade_days": int(skipped_trade_days),
        "daily_trade_coverage_pct": float(n_trades / expected_trade_days) if expected_trade_days else 0.0,
        "average_holding_minutes": 1440.0 if n_trades else 0.0,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "most_selected_inst_id": most_selected,
        "first_trade_ts": first_trade_ts,
        "last_trade_ts": last_trade_ts,
    }


def run_daily_winner_backtest(
    dfs: dict[str, pd.DataFrame],
    params: DailyWinnerParams,
) -> DailyWinnerBacktestResult:
    open_panel, close_panel = _build_open_close_panels(dfs, params.universe)
    universe = list(open_panel.columns)

    if len(open_panel) < 2:
        raise ValueError("daily winner backtest needs at least two daily bars")

    signal_returns = close_panel / open_panel - 1.0
    cost_rate = 2.0 * (params.fee_bps + params.slippage_bps) / 10_000.0

    records: list[dict] = []
    returns: list[float] = []
    return_index: list[pd.Timestamp] = []
    weights = pd.DataFrame(0.0, index=open_panel.index, columns=universe)
    equity_values = [float(params.initial_equity)]
    equity_index = [open_panel.index[0]]
    skipped_trade_days = 0

    for idx in range(1, len(open_panel.index)):
        signal_date = open_panel.index[idx - 1]
        trade_date = open_panel.index[idx]
        signal_row = signal_returns.loc[signal_date].replace([np.inf, -np.inf], np.nan).dropna()

        if signal_row.empty:
            skipped_trade_days += 1
            returns.append(0.0)
            return_index.append(trade_date)
            equity_values.append(equity_values[-1])
            equity_index.append(trade_date)
            continue

        winner = str(signal_row.idxmax())
        entry_price = open_panel.loc[trade_date, winner]
        exit_price = close_panel.loc[trade_date, winner]
        if not np.isfinite(entry_price) or not np.isfinite(exit_price) or entry_price <= 0:
            skipped_trade_days += 1
            returns.append(0.0)
            return_index.append(trade_date)
            equity_values.append(equity_values[-1])
            equity_index.append(trade_date)
            continue

        gross_return = float(exit_price / entry_price - 1.0)
        net_return = gross_return - cost_rate
        returns.append(net_return)
        return_index.append(trade_date)
        equity_values.append(equity_values[-1] * (1.0 + net_return))
        equity_index.append(trade_date)
        weights.loc[trade_date, winner] = 1.0

        records.append(
            {
                "inst_id": winner,
                "signal_date": signal_date,
                "entry_ts": trade_date,
                "exit_ts": trade_date + pd.Timedelta(days=1),
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "yesterday_return": float(signal_row[winner]),
                "gross_return": gross_return,
                "cost_rate": cost_rate,
                "net_return": net_return,
                "holding_minutes": 1440,
            }
        )

    daily_returns = pd.Series(returns, index=pd.DatetimeIndex(return_index), name="return")
    equity_curve = pd.Series(equity_values, index=pd.DatetimeIndex(equity_index), name="equity")
    trades = pd.DataFrame(records)
    metrics = _compute_metrics(
        equity_curve=equity_curve,
        daily_returns=daily_returns,
        trades=trades,
        expected_trade_days=max(len(open_panel.index) - 1, 0),
        skipped_trade_days=skipped_trade_days,
        universe_size=len(universe),
    )

    return DailyWinnerBacktestResult(
        equity_curve=equity_curve,
        daily_returns=daily_returns,
        target_weights=weights,
        positions=weights.copy(),
        trades=trades,
        metrics=metrics,
    )
