"""
Cross-sectional momentum research strategy.

Phase 1 is vectorised backtest only; live event handling is intentionally a no-op.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from okx_quant.core.events import Event, SignalPayload
from okx_quant.portfolio.allocation import dollar_neutral_long_short_weights
from okx_quant.signals.regime import composite_risk_multiplier
from okx_quant.strategies.base import Strategy

TRADING_DAYS_PER_YEAR = 365.0
MAX_GROSS_LEVERAGE = 2.0


@dataclass
class XSMomentumParams:
    universe: list[str] = field(default_factory=list)
    bar: str = "1m"
    rebalance: str = "weekly"
    lookback_days: int = 28
    skip_days: int = 0
    quantile: float = 0.30
    vol_window_days: int = 28
    inverse_vol: bool = True
    vol_target_annual: float = 0.175
    max_name_weight: float = 0.10
    fee_bps: float = 2.0
    slippage_bps: float = 2.0
    long_only: bool = False


def vol_normalized_momentum(
    close_daily: pd.DataFrame,
    lookback: int,
    skip: int,
    vol_window: int,
) -> pd.DataFrame:
    end = close_daily.shift(skip) if skip else close_daily
    start = close_daily.shift(lookback + skip)
    trailing_return = end / start - 1.0
    realized_vol = np.log(close_daily / close_daily.shift(1)).rolling(
        vol_window,
        min_periods=2,
    ).std()
    return trailing_return / realized_vol.replace(0.0, np.nan)


def _rebalance_mask(index: pd.DatetimeIndex, rebalance: str) -> pd.Series:
    if rebalance.lower() == "weekly":
        return pd.Series(index.weekday == 0, index=index)
    return pd.Series(True, index=index)


def _cap_neutral(weights: pd.Series, cap: float) -> pd.Series:
    capped = weights.clip(lower=-cap, upper=cap)
    pos = capped[capped > 0]
    neg = capped[capped < 0]
    if pos.empty or neg.empty:
        return capped * 0.0
    leg = min(float(pos.sum()), float(-neg.sum()))
    capped.loc[pos.index] = pos / float(pos.sum()) * leg
    capped.loc[neg.index] = neg / float(-neg.sum()) * leg
    return capped


def _market_multipliers(market_close: pd.Series | None, index: pd.DatetimeIndex) -> pd.Series:
    if market_close is None:
        return pd.Series(1.0, index=index)
    aligned = pd.to_numeric(market_close.reindex(index).ffill(), errors="coerce")
    drawdown = (aligned / aligned.cummax() - 1.0).abs().fillna(0.0)
    returns = aligned.pct_change()
    vol = returns.rolling(20, min_periods=2).std()
    median_vol = vol.rolling(126, min_periods=2).median()
    high_vol = (vol > 1.5 * median_vol).fillna(False)
    return pd.Series(
        [
            composite_risk_multiplier(drawdown_pct=float(dd), high_vol=bool(hv))
            for dd, hv in zip(drawdown, high_vol)
        ],
        index=index,
    )


def _portfolio_vol_gross(weights: pd.Series, realized_vol: pd.Series, target_annual: float) -> float:
    vol = pd.to_numeric(realized_vol.reindex(weights.index), errors="coerce")
    active = weights[weights != 0.0].index
    book_daily_vol = float(np.sqrt(((weights.loc[active] * vol.loc[active]) ** 2).dropna().sum()))
    if book_daily_vol <= 0:
        return 1.0
    return min(MAX_GROSS_LEVERAGE, target_annual / (book_daily_vol * np.sqrt(TRADING_DAYS_PER_YEAR)))


def target_weights(
    score_panel: pd.DataFrame,
    membership: pd.DataFrame,
    params: XSMomentumParams,
    realized_vol: pd.DataFrame,
    market_close: pd.Series | None = None,
) -> pd.DataFrame:
    dates = pd.DatetimeIndex(score_panel.index)
    out = pd.DataFrame(0.0, index=dates, columns=score_panel.columns, dtype=float)
    is_rebalance = _rebalance_mask(dates, params.rebalance)
    current = pd.Series(0.0, index=score_panel.columns, dtype=float)
    regime_multiplier = _market_multipliers(market_close, dates)

    member = membership.copy()
    member["date"] = pd.to_datetime(member["date"]).dt.normalize()

    for ts in dates:
        if not bool(is_rebalance.loc[ts]):
            out.loc[ts] = current
            continue

        eligible = member[(member["date"] == ts.normalize()) & (member["eligible"])]
        symbols = [symbol for symbol in eligible["symbol"].tolist() if symbol in score_panel.columns]
        scores = score_panel.loc[ts, symbols].dropna()
        if len(scores) < 2:
            current = current * 0.0
            out.loc[ts] = current
            continue

        inv_vol = None
        vol = pd.to_numeric(realized_vol.loc[ts, scores.index], errors="coerce")
        if params.inverse_vol:
            inv_vol = 1.0 / vol.replace(0.0, np.nan)

        unit = dollar_neutral_long_short_weights(
            scores,
            q=params.quantile,
            inverse_vol=inv_vol,
            gross=1.0,
        )
        unit = _cap_neutral(unit, params.max_name_weight)
        gross = _portfolio_vol_gross(unit, vol, params.vol_target_annual)
        selected = unit * gross * float(regime_multiplier.loc[ts])
        current = pd.Series(0.0, index=score_panel.columns, dtype=float)
        current.loc[selected.index] = _cap_neutral(selected, params.max_name_weight)
        out.loc[ts] = current

    return out


class XSMomentumStrategy(Strategy):
    def __init__(self, params: dict) -> None:
        super().__init__("xs_momentum", params)

    async def on_market(
        self,
        event: Event,
        book=None,
    ) -> Optional[SignalPayload]:
        return None

    async def on_fill(self, event: Event) -> None:
        pass
