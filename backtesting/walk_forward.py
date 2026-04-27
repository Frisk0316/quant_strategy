"""
Rolling Walk-Forward validation.
IS window: 30 days, OOS window: 7 days, step: OOS size.

Usage:
    from backtesting.walk_forward import WalkForward
    wf = WalkForward(is_days=30, oos_days=7)
    for is_data, oos_data in wf.split(df):
        # fit on is_data, evaluate on oos_data
"""
from __future__ import annotations

from typing import Callable, Generator
import pandas as pd

from okx_quant.analytics.performance import sharpe
from backtesting.result_utils import extract_returns


class WalkForward:
    def __init__(
        self,
        is_days: int = 30,
        oos_days: int = 7,
    ) -> None:
        self.is_days = is_days
        self.oos_days = oos_days

    def split(
        self,
        df: pd.DataFrame,
    ) -> Generator[tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """
        Yield (in_sample, out_of_sample) DataFrame pairs.
        df must have a DatetimeIndex.
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have a DatetimeIndex")

        start = df.index[0]
        end = df.index[-1]

        window_is = pd.Timedelta(days=self.is_days)
        window_oos = pd.Timedelta(days=self.oos_days)

        cursor = start + window_is
        while cursor + window_oos <= end:
            is_start = cursor - window_is
            oos_end = cursor + window_oos

            # Half-open intervals avoid leaking the boundary timestamp into both sets.
            is_mask = (df.index >= is_start) & (df.index < cursor)
            oos_mask = (df.index >= cursor) & (df.index < oos_end)
            is_data = df.loc[is_mask]
            oos_data = df.loc[oos_mask]
            if len(is_data) > 0 and len(oos_data) > 0:
                yield is_data, oos_data
            cursor += window_oos

    def evaluate(
        self,
        df: pd.DataFrame,
        strategy_fn: Callable[[pd.DataFrame, pd.DataFrame], pd.Series],
        periods: int = 365,
    ) -> pd.DataFrame:
        """
        Run walk-forward evaluation.

        Args:
            df: Full dataset with DatetimeIndex.
            strategy_fn: Callable(is_data, oos_data) → pd.Series of returns.
            periods: Annualization period for Sharpe.

        Returns:
            DataFrame with IS/OOS Sharpe per window.
        """
        results = []
        for i, (is_data, oos_data) in enumerate(self.split(df)):
            raw_result = strategy_fn(is_data, oos_data)
            oos_returns = extract_returns(raw_result)
            results.append({
                "window": i,
                "is_start": is_data.index[0],
                "is_end": is_data.index[-1],
                "oos_start": oos_data.index[0],
                "oos_end": oos_data.index[-1],
                "is_n": len(is_data),
                "oos_sharpe": sharpe(oos_returns, periods=periods),
                "oos_n": len(oos_returns),
                "result": raw_result,
            })
        return pd.DataFrame(results)
