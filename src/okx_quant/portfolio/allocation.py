"""
Multi-strategy weight allocation using Hierarchical Risk Parity (HRP).
From §4.2: rebalance weekly, avoids unstable matrix inversion of MVO.

Reference: López de Prado (2016), PyPortfolioOpt HRPOpt
"""
from __future__ import annotations

import time
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger


def dollar_neutral_long_short_weights(
    scores: pd.Series,
    q: float,
    inverse_vol: Optional[pd.Series] = None,
    gross: float = 1.0,
) -> pd.Series:
    valid = scores.dropna().sort_values(ascending=False)
    weights = pd.Series(0.0, index=scores.index, dtype=float)
    if len(valid) < 2 or q <= 0 or gross <= 0:
        return weights

    leg_n = max(1, min(int(np.floor(len(valid) * q)), len(valid) // 2))
    longs = valid.head(leg_n).index
    shorts = valid.tail(leg_n).index

    def _leg(names: pd.Index) -> pd.Series:
        if inverse_vol is None:
            return pd.Series(1.0 / len(names), index=names, dtype=float)
        raw = pd.to_numeric(inverse_vol.reindex(names), errors="coerce").clip(lower=0).fillna(0.0)
        total = float(raw.sum())
        if total <= 0:
            return pd.Series(1.0 / len(names), index=names, dtype=float)
        return raw / total

    weights.loc[longs] = _leg(longs) * (gross / 2.0)
    weights.loc[shorts] = -_leg(shorts) * (gross / 2.0)
    return weights


class StrategyAllocator:
    def __init__(
        self,
        rebalance_interval_days: int = 7,
    ) -> None:
        self._rebalance_interval = rebalance_interval_days * 86400
        self._last_rebalance: float = 0.0
        self._current_weights: dict[str, float] = {}

    def compute_hrp_weights(self, strategy_returns_df: pd.DataFrame) -> dict[str, float]:
        """
        Compute HRP weights from strategy return matrix.

        Args:
            strategy_returns_df: DataFrame where each column is one strategy's returns.

        Returns:
            Dict of {strategy_name: weight}, weights sum to 1.
        """
        try:
            from pypfopt import HRPOpt
        except ImportError:
            raise ImportError("PyPortfolioOpt required: pip install PyPortfolioOpt")

        if strategy_returns_df.empty or strategy_returns_df.shape[1] < 2:
            # Equal weight fallback
            n = max(strategy_returns_df.shape[1], 1)
            return {col: 1.0 / n for col in strategy_returns_df.columns}

        # Drop columns with all NaN or zero variance
        valid_cols = [
            col for col in strategy_returns_df.columns
            if strategy_returns_df[col].dropna().std() > 1e-10
        ]
        if len(valid_cols) == 0:
            n = strategy_returns_df.shape[1]
            return {col: 1.0 / n for col in strategy_returns_df.columns}

        df_clean = strategy_returns_df[valid_cols].dropna()
        if len(df_clean) < 5:
            n = len(valid_cols)
            return {col: 1.0 / n for col in valid_cols}

        hrp = HRPOpt(returns=df_clean)
        weights = hrp.optimize()
        logger.info("HRP weights computed", weights=weights)
        return dict(weights)

    def rebalance_needed(self) -> bool:
        return time.time() - self._last_rebalance >= self._rebalance_interval

    def update_weights(
        self,
        strategy_returns_df: pd.DataFrame,
        force: bool = False,
    ) -> dict[str, float]:
        """Update weights if rebalance is needed."""
        if not (self.rebalance_needed() or force):
            return self._current_weights

        weights = self.compute_hrp_weights(strategy_returns_df)
        self._current_weights = weights
        self._last_rebalance = time.time()
        return weights

    def get_weights(self) -> dict[str, float]:
        return dict(self._current_weights)
