"""Research-only Turtle S1/S2 backtest port.

This intentionally mirrors the user's standalone ``turtle_trading_system_full``
semantics. It is not wired into replay, strategy registry, risk, or live gates.
"""
from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd


WINDOW_PARAMS = ("enter_term_sys1", "enter_term_sys2", "leave_term_sys1", "leave_term_sys2")
SWEEP_METRICS = ("mdd", "win_rate", "final_whole_asset", "profit_loss_ratio", "expectancy")
SWEEP_COLUMNS = (
    "enter_term_sys1",
    "enter_term_sys2",
    "leave_term_sys1",
    "leave_term_sys2",
    "win_rate",
    "profit_loss_ratio",
    "expectancy",
    "mdd",
    "final_whole_asset",
    "positive_rate",
    "median_asset",
    "mean_asset",
    "s1_return_median",
    "s1_return_mean",
    "s2_return_median",
    "s2_return_mean",
    "s1_max_consec_win",
    "s1_max_consec_loss",
    "s2_max_consec_win",
    "s2_max_consec_loss",
    "overall_max_consec_win",
    "overall_max_consec_loss",
    "final_win_count",
    "final_loss_count",
    "min_equity",
    "min_realized_pnl",
    "final_equity",
)


@dataclass(frozen=True)
class TurtleParams:
    enter_term_sys1: int = 20
    enter_term_sys2: int = 55
    leave_term_sys1: int = 10
    leave_term_sys2: int = 20
    single_sys_unit_limit: int = 4
    both_sys_unit_limit: int = 4
    own_capital: float = 50_000.0
    invest_pct: float = 0.01
    min_position: float = 0.0001
    fee: float = 0.003
    atr_period: int = 20

    def validate(self) -> None:
        for name in WINDOW_PARAMS + ("atr_period",):
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        if int(self.single_sys_unit_limit) <= 0 or int(self.both_sys_unit_limit) <= 0:
            raise ValueError("unit limits must be positive")
        if not 0 < float(self.invest_pct) <= 1:
            raise ValueError("invest_pct must be within (0, 1]")
        if float(self.own_capital) <= 0:
            raise ValueError("own_capital must be positive")
        if float(self.min_position) <= 0:
            raise ValueError("min_position must be positive")
        if not 0 <= float(self.fee) < 1:
            raise ValueError("fee must be within [0, 1)")


@dataclass
class TurtleResult:
    frame: pd.DataFrame
    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    metrics: dict[str, Any]


def calc_atr(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    out = df.sort_values("date").copy()
    prev_close = out["close"].shift(1)
    true_range = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (prev_close - out["low"]).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=True)
    out["true_range"] = true_range
    out["ATR"] = true_range.rolling(window=period, min_periods=period).mean()
    return out


def calc_unit_size(own_capital: float, atr: float, close: float, invest_pct: float, min_position: float) -> float:
    raw = own_capital * invest_pct / (atr + close)
    return math.floor(raw / min_position) * min_position


def _normalize_daily_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "date" not in out.columns:
        if "ts" in out.columns:
            out["date"] = out["ts"]
        elif isinstance(out.index, pd.DatetimeIndex):
            out["date"] = out.index
        else:
            raise ValueError("turtle daily dataframe requires a date, ts, or DatetimeIndex")
    required = {"date", "open", "high", "low", "close"}
    missing = sorted(required - set(out.columns))
    if missing:
        raise ValueError(f"turtle daily dataframe missing columns: {missing}")
    out["date"] = pd.to_datetime(out["date"], utc=True, errors="coerce").dt.tz_localize(None)
    if out["date"].isna().any():
        raise ValueError("turtle daily dataframe contains invalid dates")
    for col in ("open", "high", "low", "close"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    return out.sort_values("date").reset_index(drop=True)


def _prepare_frame(df: pd.DataFrame, params: TurtleParams) -> pd.DataFrame:
    out = calc_atr(_normalize_daily_frame(df), period=params.atr_period)
    out["last_enter_max_sys1"] = (
        out["high"].rolling(window=params.enter_term_sys1, min_periods=params.enter_term_sys1).max().shift(1)
    )
    out["last_enter_max_sys2"] = (
        out["high"].rolling(window=params.enter_term_sys2, min_periods=params.enter_term_sys2).max().shift(1)
    )
    out["last_leave_min_sys1"] = (
        out["low"].rolling(window=params.leave_term_sys1, min_periods=params.leave_term_sys1).min().shift(1)
    )
    out["last_leave_min_sys2"] = (
        out["low"].rolling(window=params.leave_term_sys2, min_periods=params.leave_term_sys2).min().shift(1)
    )
    return out


def _missing(*values: Any) -> bool:
    return any(value is None or pd.isna(value) for value in values)


def _empty_row(row: dict[str, Any], cumulative_profit: float, money_in_hand: float, realized_pnl: float, own_capital: float, wins: int, losses: int) -> None:
    row.update(
        {
            "s1_buy": 0,
            "s1_sell": 0,
            "s1_profit": 0.0,
            "s2_buy": 0,
            "s2_sell": 0,
            "s2_profit": 0.0,
            "s1_units": 0,
            "s2_units": 0,
            "s1_position": 0.0,
            "s2_position": 0.0,
            "s1_position_value": 0.0,
            "s2_position_value": 0.0,
            "s1_stop_loss": 0.0,
            "s2_stop_loss": 0.0,
            "total_units": 0,
            "whole_asset": cumulative_profit,
            "profit": 0.0,
            "cumulative_profit": cumulative_profit,
            "buy_action": 0,
            "sell_action": 0,
            "whole_asset_plus_initial_fund": cumulative_profit + own_capital,
            "s1_win": 0,
            "s1_loss": 0,
            "s2_win": 0,
            "s2_loss": 0,
            "s1_trade_return": np.nan,
            "s2_trade_return": np.nan,
            "win_today": 0,
            "loss_today": 0,
            "cumulative_win_count": wins,
            "cumulative_loss_count": losses,
            "money_in_hand": money_in_hand,
            "realized_pnl": realized_pnl,
            "equity": money_in_hand,
        }
    )


def _trade_event(
    *,
    row: dict[str, Any],
    system: str,
    action: str,
    reason: str,
    price: float,
    size: float,
    fee: float,
    units_after: int,
    cash_after: float,
    pnl: float | None = None,
) -> dict[str, Any]:
    return {
        "ts": row["date"],
        "datetime": str(row["date"]),
        "system": system,
        "action": action,
        "reason": reason,
        "price": float(price),
        "size": float(size),
        "fee_paid": float(abs(price * size * fee)),
        "units_after": int(units_after),
        "cash_after": float(cash_after),
        "pnl": None if pnl is None else float(pnl),
    }


def run_turtle_backtest(daily_df: pd.DataFrame, params: TurtleParams | None = None) -> TurtleResult:
    params = params or TurtleParams()
    params.validate()
    records = _prepare_frame(daily_df, params).to_dict("records")

    s1_in_position = False
    s1_units = 0
    s1_position = 0.0
    s1_total_cost = 0.0
    s1_last_add_price = 0.0
    s1_stop_loss = 0.0
    s1_skip_next = False

    s2_in_position = False
    s2_units = 0
    s2_position = 0.0
    s2_total_cost = 0.0
    s2_last_add_price = 0.0
    s2_stop_loss = 0.0

    cumulative_profit = 0.0
    cumulative_win_count = 0
    cumulative_loss_count = 0
    money_in_hand = float(params.own_capital)
    realized_pnl = 0.0
    trades: list[dict[str, Any]] = []
    cash_skip_count = 0
    equity_half_count = 0
    realized_loss_half_count = 0

    for row in records:
        s1_win = s1_loss = s2_win = s2_loss = 0
        s1_trade_return = np.nan
        s2_trade_return = np.nan
        s1_buy = s1_sell = s2_buy = s2_sell = 0
        s1_profit = s2_profit = 0.0

        atr = row.get("ATR")
        enter_max_sys1 = row.get("last_enter_max_sys1")
        enter_max_sys2 = row.get("last_enter_max_sys2")
        leave_min_sys1 = row.get("last_leave_min_sys1")
        leave_min_sys2 = row.get("last_leave_min_sys2")
        close = float(row["close"])
        low = float(row["low"])
        high = float(row["high"])

        if _missing(atr, enter_max_sys1, enter_max_sys2, leave_min_sys1, leave_min_sys2):
            _empty_row(
                row,
                cumulative_profit,
                money_in_hand,
                realized_pnl,
                params.own_capital,
                cumulative_win_count,
                cumulative_loss_count,
            )
            continue

        unit_size = calc_unit_size(params.own_capital, float(atr), close, params.invest_pct, params.min_position)
        total_units = s1_units + s2_units

        if not s1_in_position:
            if high > float(enter_max_sys1):
                if s1_skip_next:
                    s1_skip_next = False
                elif total_units + 1 <= params.both_sys_unit_limit:
                    cost = close * unit_size * (1 + params.fee)
                    if cost < money_in_hand:
                        s1_in_position = True
                        s1_units = 1
                        s1_last_add_price = close
                        s1_stop_loss = close - 2 * float(atr)
                        s1_position = unit_size
                        s1_total_cost = cost
                        s1_profit = -cost
                        cumulative_profit += s1_profit
                        money_in_hand += s1_profit
                        s1_buy = 1
                        total_units = s1_units + s2_units
                        trades.append(
                            _trade_event(
                                row=row,
                                system="s1",
                                action="entry",
                                reason="breakout",
                                price=close,
                                size=unit_size,
                                fee=params.fee,
                                units_after=s1_units,
                                cash_after=money_in_hand,
                            )
                        )
                    else:
                        cash_skip_count += 1
        else:
            if low < float(leave_min_sys1) or close <= s1_stop_loss:
                revenue = close * s1_position * (1 - params.fee)
                pnl = revenue - s1_total_cost
                s1_profit = revenue
                cumulative_profit += s1_profit
                money_in_hand += s1_profit
                s1_skip_next = revenue > s1_total_cost
                s1_trade_return = pnl / s1_total_cost if s1_total_cost else np.nan
                realized_pnl += pnl
                if revenue > s1_total_cost:
                    cumulative_win_count += 1
                    s1_win = 1
                else:
                    cumulative_loss_count += 1
                    s1_loss = 1
                reason = "stop_loss" if close <= s1_stop_loss else "exit_rule"
                trades.append(
                    _trade_event(
                        row=row,
                        system="s1",
                        action="exit",
                        reason=reason,
                        price=close,
                        size=s1_position,
                        fee=params.fee,
                        units_after=0,
                        cash_after=money_in_hand,
                        pnl=pnl,
                    )
                )
                s1_in_position = False
                s1_sell = 1
                s1_units = 0
                s1_position = 0.0
                s1_total_cost = 0.0
                s1_stop_loss = 0.0
                total_units = s1_units + s2_units
            elif (
                s1_units < params.single_sys_unit_limit
                and total_units + 1 <= params.both_sys_unit_limit
                and close >= s1_last_add_price + 0.5 * float(atr)
            ):
                cost = close * unit_size * (1 + params.fee)
                if cost < money_in_hand:
                    s1_units += 1
                    s1_last_add_price = close
                    s1_stop_loss = close - 2 * float(atr)
                    s1_position += unit_size
                    s1_total_cost += cost
                    s1_profit = -cost
                    cumulative_profit += s1_profit
                    money_in_hand += s1_profit
                    s1_buy = 1
                    total_units = s1_units + s2_units
                    trades.append(
                        _trade_event(
                            row=row,
                            system="s1",
                            action="pyramid",
                            reason="half_atr_add",
                            price=close,
                            size=unit_size,
                            fee=params.fee,
                            units_after=s1_units,
                            cash_after=money_in_hand,
                        )
                    )
                else:
                    cash_skip_count += 1

        if not s2_in_position:
            if high > float(enter_max_sys2) and total_units + 1 <= params.both_sys_unit_limit:
                cost = close * unit_size * (1 + params.fee)
                if cost < money_in_hand:
                    s2_in_position = True
                    s2_units = 1
                    s2_last_add_price = close
                    s2_stop_loss = close - 2 * float(atr)
                    s2_position = unit_size
                    s2_total_cost = cost
                    s2_profit = -cost
                    cumulative_profit += s2_profit
                    money_in_hand += s2_profit
                    s2_buy = 1
                    total_units = s1_units + s2_units
                    trades.append(
                        _trade_event(
                            row=row,
                            system="s2",
                            action="entry",
                            reason="breakout",
                            price=close,
                            size=unit_size,
                            fee=params.fee,
                            units_after=s2_units,
                            cash_after=money_in_hand,
                        )
                    )
                else:
                    cash_skip_count += 1
        else:
            if low < float(leave_min_sys2) or close <= s2_stop_loss:
                revenue = close * s2_position * (1 - params.fee)
                pnl = revenue - s2_total_cost
                s2_profit = revenue
                cumulative_profit += s2_profit
                money_in_hand += s2_profit
                s2_trade_return = pnl / s2_total_cost if s2_total_cost else np.nan
                realized_pnl += pnl
                if revenue > s2_total_cost:
                    cumulative_win_count += 1
                    s2_win = 1
                else:
                    cumulative_loss_count += 1
                    s2_loss = 1
                reason = "stop_loss" if close <= s2_stop_loss else "exit_rule"
                trades.append(
                    _trade_event(
                        row=row,
                        system="s2",
                        action="exit",
                        reason=reason,
                        price=close,
                        size=s2_position,
                        fee=params.fee,
                        units_after=0,
                        cash_after=money_in_hand,
                        pnl=pnl,
                    )
                )
                s2_in_position = False
                s2_sell = 1
                s2_units = 0
                s2_position = 0.0
                s2_total_cost = 0.0
                s2_stop_loss = 0.0
                total_units = s1_units + s2_units
            elif (
                s2_units < params.single_sys_unit_limit
                and total_units + 1 <= params.both_sys_unit_limit
                and close >= s2_last_add_price + 0.5 * float(atr)
            ):
                cost = close * unit_size * (1 + params.fee)
                if cost < money_in_hand:
                    s2_units += 1
                    s2_last_add_price = close
                    s2_stop_loss = close - 2 * float(atr)
                    s2_position += unit_size
                    s2_total_cost += cost
                    s2_profit = -cost
                    cumulative_profit += s2_profit
                    money_in_hand += s2_profit
                    s2_buy = 1
                    total_units = s1_units + s2_units
                    trades.append(
                        _trade_event(
                            row=row,
                            system="s2",
                            action="pyramid",
                            reason="half_atr_add",
                            price=close,
                            size=unit_size,
                            fee=params.fee,
                            units_after=s2_units,
                            cash_after=money_in_hand,
                        )
                    )
                else:
                    cash_skip_count += 1

        s1_position_value = close * s1_position if s1_in_position else 0.0
        s2_position_value = close * s2_position if s2_in_position else 0.0
        whole_asset = cumulative_profit + s1_position_value + s2_position_value
        equity = money_in_hand + s1_position_value + s2_position_value
        if equity / params.own_capital < 0.5:
            equity_half_count += 1
        if abs(realized_pnl) / params.own_capital >= 0.5 and realized_pnl < 0:
            realized_loss_half_count += 1

        row.update(
            {
                "s1_buy": s1_buy,
                "s1_sell": s1_sell,
                "s1_profit": s1_profit,
                "s1_units": s1_units,
                "s1_position": s1_position,
                "s1_position_value": s1_position_value,
                "s1_stop_loss": s1_stop_loss,
                "s2_buy": s2_buy,
                "s2_sell": s2_sell,
                "s2_profit": s2_profit,
                "s2_units": s2_units,
                "s2_position": s2_position,
                "s2_position_value": s2_position_value,
                "s2_stop_loss": s2_stop_loss,
                "total_units": total_units,
                "whole_asset": whole_asset,
                "profit": s1_profit + s2_profit,
                "cumulative_profit": cumulative_profit,
                "buy_action": 1 if (s1_buy or s2_buy) else 0,
                "sell_action": 1 if (s1_sell or s2_sell) else 0,
                "whole_asset_plus_initial_fund": whole_asset + params.own_capital,
                "s1_win": s1_win,
                "s1_loss": s1_loss,
                "s2_win": s2_win,
                "s2_loss": s2_loss,
                "s1_trade_return": s1_trade_return,
                "s2_trade_return": s2_trade_return,
                "win_today": s1_win + s2_win,
                "loss_today": s1_loss + s2_loss,
                "cumulative_win_count": cumulative_win_count,
                "cumulative_loss_count": cumulative_loss_count,
                "money_in_hand": money_in_hand,
                "realized_pnl": realized_pnl,
                "equity": equity,
            }
        )

    frame = pd.DataFrame(records)
    trades_df = pd.DataFrame(
        trades,
        columns=["ts", "datetime", "system", "action", "reason", "price", "size", "fee_paid", "units_after", "cash_after", "pnl"],
    )
    equity_curve = frame[["date", "equity"]].copy()
    equity_curve["return"] = equity_curve["equity"].pct_change().fillna(0.0)
    equity_curve["drawdown"] = equity_curve["equity"] / equity_curve["equity"].cummax() - 1.0
    metrics = turtle_metrics(frame, params)
    metrics.update(
        {
            "cash_skip_count": int(cash_skip_count),
            "equity_half_count": int(equity_half_count),
            "realized_loss_half_count": int(realized_loss_half_count),
        }
    )
    return TurtleResult(frame=frame, trades=trades_df, equity_curve=equity_curve, metrics=metrics)


def _calc_trade_pnl(result_df: pd.DataFrame, entry_col: str, exit_col: str, profit_col: str) -> np.ndarray:
    entry_actions = result_df[entry_col].to_numpy()
    exit_actions = result_df[exit_col].to_numpy()
    profits = result_df[profit_col].to_numpy(dtype=float)
    trade_pnl: list[float] = []
    in_trade = False
    current_pnl = 0.0
    for entry, exit_, profit in zip(entry_actions, exit_actions, profits):
        if not in_trade:
            if entry == 1:
                in_trade = True
                current_pnl = profit
        else:
            current_pnl += profit
            if exit_ == 1:
                trade_pnl.append(current_pnl)
                in_trade = False
                current_pnl = 0.0
    return np.array(trade_pnl, dtype=float)


def calc_win_rate_full(result_df: pd.DataFrame) -> float:
    pnl = np.concatenate([
        _calc_trade_pnl(result_df, "s1_buy", "s1_sell", "s1_profit"),
        _calc_trade_pnl(result_df, "s2_buy", "s2_sell", "s2_profit"),
    ])
    return float((pnl > 0).sum() / len(pnl)) if len(pnl) else 0.0


def calc_profit_loss_ratio_full(result_df: pd.DataFrame) -> float:
    pnl = np.concatenate([
        _calc_trade_pnl(result_df, "s1_buy", "s1_sell", "s1_profit"),
        _calc_trade_pnl(result_df, "s2_buy", "s2_sell", "s2_profit"),
    ])
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    avg_loss = losses.mean() if len(losses) else 0.0
    return float(wins.mean() / abs(avg_loss)) if len(wins) and avg_loss != 0 else 0.0


def calc_expectancy_full(result_df: pd.DataFrame) -> float:
    pnl = np.concatenate([
        _calc_trade_pnl(result_df, "s1_buy", "s1_sell", "s1_profit"),
        _calc_trade_pnl(result_df, "s2_buy", "s2_sell", "s2_profit"),
    ])
    if not len(pnl):
        return 0.0
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    win_rate = len(wins) / len(pnl)
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = losses.mean() if len(losses) else 0.0
    return float(win_rate * avg_win + (1 - win_rate) * avg_loss)


def calc_mdd(values: pd.Series | np.ndarray, filter_zero: bool = False) -> float:
    arr = np.asarray(values, dtype=float)
    if filter_zero:
        arr = arr[arr != 0]
    if len(arr) == 0:
        return 0.0
    peak = np.maximum.accumulate(arr)
    drawdown = np.where(peak != 0, (arr - peak) / np.where(peak != 0, peak, 1), 0.0)
    return float(np.nanmin(drawdown))


def calc_whole_asset_stats(whole_asset: pd.Series | np.ndarray) -> tuple[float, float, float]:
    arr = np.asarray(whole_asset, dtype=float)
    if len(arr) == 0:
        return 0.0, 0.0, 0.0
    return float((arr > 0).sum() / len(arr)), float(np.median(arr)), float(np.mean(arr))


def get_outcomes_single(result_df: pd.DataFrame, sys: str) -> list[int]:
    outcomes: list[int] = []
    for win, loss in zip(result_df[f"{sys}_win"].to_list(), result_df[f"{sys}_loss"].to_list()):
        if win:
            outcomes.append(1)
        elif loss:
            outcomes.append(0)
    return outcomes


def get_outcomes_overall_v2(result_df: pd.DataFrame) -> list[int]:
    outcomes: list[int] = []
    for win, loss, s1_ret, s2_ret in zip(
        result_df["win_today"].to_list(),
        result_df["loss_today"].to_list(),
        result_df["s1_trade_return"].to_list(),
        result_df["s2_trade_return"].to_list(),
    ):
        if win == 0 and loss == 0:
            continue
        if win > 0 and loss == 0:
            outcomes.append(1)
        elif loss > 0 and win == 0:
            outcomes.append(0)
        else:
            returns = [float(value) for value in (s1_ret, s2_ret) if value is not None and not pd.isna(value)]
            outcomes.append(1 if returns and sum(returns) / len(returns) >= 0 else 0)
    return outcomes


def max_consecutive(outcomes: list[int], target: int) -> int:
    best = cur = 0
    for outcome in outcomes:
        if outcome == target:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def turtle_metric_row(result_df: pd.DataFrame, params: TurtleParams) -> dict[str, Any]:
    whole_asset = pd.to_numeric(result_df["whole_asset"], errors="coerce")
    all_asset = params.own_capital + whole_asset
    positive_rate, median_asset, mean_asset = calc_whole_asset_stats(whole_asset)
    s1_outcomes = get_outcomes_single(result_df, "s1")
    s2_outcomes = get_outcomes_single(result_df, "s2")
    overall_outcomes = get_outcomes_overall_v2(result_df)
    row = {
        "enter_term_sys1": int(params.enter_term_sys1),
        "enter_term_sys2": int(params.enter_term_sys2),
        "leave_term_sys1": int(params.leave_term_sys1),
        "leave_term_sys2": int(params.leave_term_sys2),
        "win_rate": calc_win_rate_full(result_df),
        "profit_loss_ratio": calc_profit_loss_ratio_full(result_df),
        "expectancy": calc_expectancy_full(result_df),
        "mdd": calc_mdd(all_asset, filter_zero=True),
        "final_whole_asset": float(whole_asset.iloc[-1]) if len(whole_asset) else 0.0,
        "positive_rate": positive_rate,
        "median_asset": median_asset,
        "mean_asset": mean_asset,
        "s1_return_median": _finite_or_none(result_df["s1_trade_return"].median()),
        "s1_return_mean": _finite_or_none(result_df["s1_trade_return"].mean()),
        "s2_return_median": _finite_or_none(result_df["s2_trade_return"].median()),
        "s2_return_mean": _finite_or_none(result_df["s2_trade_return"].mean()),
        "s1_max_consec_win": max_consecutive(s1_outcomes, 1),
        "s1_max_consec_loss": max_consecutive(s1_outcomes, 0),
        "s2_max_consec_win": max_consecutive(s2_outcomes, 1),
        "s2_max_consec_loss": max_consecutive(s2_outcomes, 0),
        "overall_max_consec_win": max_consecutive(overall_outcomes, 1),
        "overall_max_consec_loss": max_consecutive(overall_outcomes, 0),
        "final_win_count": int(result_df["cumulative_win_count"].iloc[-1]) if len(result_df) else 0,
        "final_loss_count": int(result_df["cumulative_loss_count"].iloc[-1]) if len(result_df) else 0,
        "min_equity": float(result_df["equity"].min()) if len(result_df) else 0.0,
        "min_realized_pnl": float(result_df["realized_pnl"].min()) if len(result_df) else 0.0,
        "final_equity": float(result_df["equity"].iloc[-1]) if len(result_df) else params.own_capital,
    }
    return row


def turtle_metrics(result_df: pd.DataFrame, params: TurtleParams) -> dict[str, Any]:
    row = turtle_metric_row(result_df, params)
    equity = pd.to_numeric(result_df["equity"], errors="coerce") if len(result_df) else pd.Series(dtype=float)
    returns = equity.pct_change().fillna(0.0)
    ret_std = returns.std(ddof=1) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / ret_std * math.sqrt(365.25)) if ret_std and ret_std > 0 else 0.0
    return {
        **row,
        "strategy": "turtle",
        "total_return": float(equity.iloc[-1] / params.own_capital - 1.0) if len(equity) else 0.0,
        "sharpe": sharpe,
        "max_drawdown": row["mdd"],
        "profit_factor": row["profit_loss_ratio"],
        "order_count": int(result_df["buy_action"].sum() + result_df["sell_action"].sum()) if len(result_df) else 0,
        "fill_count": int(result_df["buy_action"].sum() + result_df["sell_action"].sum()) if len(result_df) else 0,
        "fill_rate": 1.0 if len(result_df) and (result_df["buy_action"].sum() + result_df["sell_action"].sum()) else 0.0,
        "bankrupt": bool(len(result_df) and result_df["equity"].min() <= 0),
        "funding_cashflow": 0.0,
        "funding_settlement_count": 0,
        "funding_mode": "not_modeled",
        "validation_only": True,
    }


def _finite_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _parse_values(value: Any, *, percent: bool = False) -> tuple[list[float | int], int]:
    if isinstance(value, dict):
        if "fixed" in value:
            return _parse_values(value["fixed"], percent=percent)
        if "range" in value:
            return _parse_values(value["range"], percent=percent)
    if isinstance(value, (int, float)):
        parsed = [float(value) if percent else int(value)]
        if percent and parsed[0] > 1:
            parsed[0] = parsed[0] / 100.0
        return parsed, 1
    text = str(value).strip()
    if not text:
        raise ValueError("empty turtle grid value")
    raw_count = 0
    parsed_values: list[float | int] = []
    for part in text.replace("..", "~").split(","):
        token = part.strip()
        if not token:
            continue
        if "~" in token:
            bounds, _, step_text = token.partition(":")
            lo_text, hi_text = bounds.split("~", 1)
            step = float(step_text) if step_text else 1.0
            lo = float(lo_text)
            hi = float(hi_text)
            if step <= 0:
                raise ValueError("range step must be positive")
            count = int(math.floor((hi - lo) / step)) + 1
            raw_count += max(count, 0)
            current = lo
            while current <= hi + 1e-12:
                parsed_values.append(current / 100.0 if percent else int(current))
                current += step
        else:
            raw_count += 1
            scalar = float(token)
            parsed_values.append(scalar / 100.0 if percent and scalar > 1 else (scalar if percent else int(scalar)))
    return parsed_values, raw_count


def _is_fixed_grid_value(value: Any) -> bool:
    if isinstance(value, dict):
        return "fixed" in value and "range" not in value
    return isinstance(value, (int, float)) or ("~" not in str(value) and "," not in str(value))


def _valid_turtle_windows(combo: dict[str, int]) -> bool:
    return (
        combo["enter_term_sys1"] > combo["leave_term_sys1"]
        and combo["enter_term_sys2"] > combo["leave_term_sys2"]
        and combo["enter_term_sys2"] > combo["enter_term_sys1"]
        and combo["leave_term_sys1"] >= 5
        and combo["leave_term_sys2"] >= 5
        and combo["leave_term_sys2"] > combo["leave_term_sys1"]
    )


def expand_turtle_grid(
    spec: dict[str, Any],
    *,
    max_combinations: int = 5000,
    max_raw_candidates: int = 20000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    invest_pct_is_axis = "invest_pct" in spec and not _is_fixed_grid_value(spec.get("invest_pct"))
    if invest_pct_is_axis and not all(_is_fixed_grid_value(spec.get(name)) for name in WINDOW_PARAMS):
        raise ValueError("invest_pct axis requires all 4 window params fixed")
    values: dict[str, list[Any]] = {}
    raw_count = 1
    defaults = {
        "enter_term_sys1": 20,
        "enter_term_sys2": 55,
        "leave_term_sys1": 10,
        "leave_term_sys2": 20,
    }
    for name in WINDOW_PARAMS:
        parsed, count = _parse_values(spec.get(name, defaults[name]))
        values[name] = parsed
        raw_count *= max(count, 1)
    if "invest_pct" in spec:
        parsed, count = _parse_values(spec["invest_pct"], percent=True)
        values["invest_pct"] = parsed
        raw_count *= max(count, 1)
    if raw_count > max_raw_candidates:
        raise ValueError(f"turtle sweep raw candidates exceed cap: {raw_count} > {max_raw_candidates}")

    combos: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    keys = list(values)
    for items in product(*(values[key] for key in keys)):
        combo = {key: value for key, value in zip(keys, items)}
        window_combo = {key: int(combo[key]) for key in WINDOW_PARAMS}
        if not _valid_turtle_windows(window_combo):
            skipped.append({"params": combo, "reason": "invalid turtle window constraints"})
            continue
        combos.append({**combo, **window_combo})
        if len(combos) > max_combinations:
            raise ValueError(f"turtle sweep valid combinations exceed cap: {len(combos)} > {max_combinations}")
    return combos, skipped


def _free_window_params(spec: dict[str, Any]) -> list[str]:
    return [name for name in WINDOW_PARAMS if not _is_fixed_grid_value(spec.get(name, ""))]


def run_turtle_sweep(
    daily_df: pd.DataFrame,
    spec: dict[str, Any],
    base_params: TurtleParams | None = None,
    *,
    output_dir: Path | None = None,
    sweep_id: str | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    base_params = base_params or TurtleParams()
    started = time.time()
    combos, skipped = expand_turtle_grid(spec)
    rows: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    for index, combo in enumerate(combos, start=1):
        params = TurtleParams(**{**asdict(base_params), **combo})
        result = run_turtle_backtest(daily_df, params)
        metric = turtle_metric_row(result.frame, params)
        if "invest_pct" in combo:
            metric["invest_pct"] = combo["invest_pct"]
            for _, eq_row in result.equity_curve.iterrows():
                equity_rows.append(
                    {
                        "invest_pct": combo["invest_pct"],
                        # ISO string, not Timestamp: this payload goes through
                        # json.dumps in the sweep job status/summary writers.
                        "date": pd.Timestamp(eq_row["date"]).date().isoformat(),
                        "equity": float(eq_row["equity"]),
                    }
                )
        rows.append(metric)
        if progress_callback and (index == 1 or index == len(combos) or index % 50 == 0):
            progress_callback({"progress": int(index / max(len(combos), 1) * 90), "completed_count": index})

    ranked = sorted(rows, key=lambda row: row.get("final_equity") or 0.0, reverse=True)
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    free_params = _free_window_params(spec)
    artifacts: dict[str, str] = {}
    sweep_id = sweep_id or f"turtle_sweep_{int(started)}"
    surface_html = ""
    if len(free_params) == 2 and "invest_pct" not in spec:
        surface_html = render_surface_html(rows, free_params[0], free_params[1])
    summary = {
        "sweep_id": sweep_id,
        "strategy": "turtle",
        "params": asdict(base_params),
        "grid": spec,
        "completed_count": len(rows),
        "failed_count": 0,
        "skipped_count": len(skipped),
        "skipped": skipped[:100],
        "elapsed_seconds": time.time() - started,
        "top_results": ranked[:10],
        "free_params": free_params,
        "artifacts": artifacts,
    }
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_csv(output_dir / "rows.csv", rows)
        artifacts["rows"] = "rows.csv"
        if equity_rows:
            _write_csv(output_dir / "equity_curves.csv", equity_rows)
            artifacts["equity_curves"] = "equity_curves.csv"
        if surface_html:
            (output_dir / "surface.html").write_text(surface_html, encoding="utf-8")
            artifacts["surface"] = "surface.html"
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        artifacts["summary"] = "summary.json"
    return summary | {"rows": rows, "equity_curves": equity_rows}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_surface_html(rows: list[dict[str, Any]], x_col: str, y_col: str) -> str:
    payload = json.dumps(rows, default=str)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Turtle Sweep Surface</title>
  <script src="/vendor/plotly.min.js"></script>
  <style>body{{font-family:system-ui,sans-serif;margin:24px}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(280px,1fr));gap:16px}}.chart{{height:360px}}</style>
</head>
<body>
  <h1>Turtle Sweep Surface</h1>
  <div id="grid" class="grid"></div>
  <script>
    const rows = {payload};
    const metrics = {json.dumps(list(SWEEP_METRICS))};
    const metricNames = ["MDD", "Win Rate", "Final Asset", "Profit/Loss Ratio", "Expectancy"];
    const xs = [...new Set(rows.map(r => r[{json.dumps(x_col)}]))].sort((a,b) => a-b);
    const ys = [...new Set(rows.map(r => r[{json.dumps(y_col)}]))].sort((a,b) => a-b);
    const byKey = new Map(rows.map(r => [`${{r[{json.dumps(x_col)}]}}|${{r[{json.dumps(y_col)}]}}`, r]));
    const root = document.getElementById("grid");
    metrics.forEach((metric, i) => {{
      const div = document.createElement("div");
      div.className = "chart";
      root.appendChild(div);
      const z = ys.map(y => xs.map(x => (byKey.get(`${{x}}|${{y}}`) || {{}})[metric] ?? null));
      Plotly.newPlot(div, [{{type:"surface", x:xs, y:ys, z, colorscale:"Viridis", showscale:false}}], {{
        title: metricNames[i],
        scene: {{xaxis:{{title:{json.dumps(x_col)}}}, yaxis:{{title:{json.dumps(y_col)}}}, zaxis:{{title:metricNames[i]}}}},
        margin: {{l:0, r:0, b:0, t:40}}
      }}, {{responsive:true}});
    }});
  </script>
</body>
</html>
"""


def turtle_trading_system_full(daily_df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
    """Compatibility wrapper returning only the per-day frame."""
    return run_turtle_backtest(daily_df, TurtleParams(**kwargs)).frame
