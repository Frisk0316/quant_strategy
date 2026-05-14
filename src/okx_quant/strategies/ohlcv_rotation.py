"""
OHLCV-Only Cross-Sectional Rotation Strategy (Phase 1: research / backtest).

Ranks a universe of perpetual instruments every N minutes using a composite
momentum + volume + volatility score and holds the top-k qualifiers.

Phase 1: vectorised backtest only — on_market() is a no-op stub.
Phase 2 (future): wire CandlePayload into on_market() for live execution.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import zscore

from okx_quant.core.events import Event, SignalPayload
from okx_quant.strategies.base import Strategy


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

@dataclass
class OHLCVRotationParams:
    universe: list[str]
    benchmark_inst_id: str = "BTC-USDT-SWAP"

    bar: str = "1m"
    rebalance_minutes: int = 60

    top_k: int = 3
    rank_exit_buffer: int = 6

    lookback_fast_minutes: int = 60
    lookback_slow_minutes: int = 240
    volume_z_window_minutes: int = 60
    realized_vol_window_minutes: int = 240
    breakout_window_minutes: int = 120
    ema_window_minutes: int = 60
    benchmark_ema_window_minutes: int = 240
    atr_window_minutes: int = 60

    weight_return_slow: float = 0.45
    weight_return_fast: float = 0.25
    weight_volume_z: float = 0.20
    weight_realized_vol: float = -0.10

    min_volume_z: float = 1.0
    atr_stop_multiple: float = 2.0
    max_holding_minutes: int = 480

    long_only: bool = True
    equal_weight: bool = True
    max_position_weight: float = 0.35

    fee_bps: float = 2.0
    slippage_bps: float = 2.0


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def _true_range(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    prev_close = close.shift(1)
    return pd.concat(
        [
            (high - low).rename(columns=lambda c: c),
            (high - prev_close).abs().rename(columns=lambda c: c),
            (low - prev_close).abs().rename(columns=lambda c: c),
        ]
    ).groupby(level=0).max()


def build_feature_panel(
    close: pd.DataFrame,
    high: pd.DataFrame,
    low: pd.DataFrame,
    vol: pd.DataFrame,
    params: OHLCVRotationParams,
) -> dict[str, pd.DataFrame]:
    """
    Compute all per-instrument features. Inputs are wide DataFrames:
        index = tz-naive UTC timestamp (1m bars)
        columns = inst_ids

    Returns a dict of DataFrames with the same shape.
    """
    # --- returns ---
    return_fast = close / close.shift(params.lookback_fast_minutes) - 1
    return_slow = close / close.shift(params.lookback_slow_minutes) - 1

    # --- volume z-score (clamp inf to NaN then fill 0) ---
    vol_mean = vol.rolling(params.volume_z_window_minutes, min_periods=1).mean()
    vol_std = vol.rolling(params.volume_z_window_minutes, min_periods=2).std()
    volume_z = (vol - vol_mean) / vol_std
    volume_z = volume_z.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # --- realized volatility (daily-equivalent = sqrt(1440) annualisation) ---
    log_ret = np.log(close / close.shift(1))
    realized_vol = (
        log_ret.rolling(params.realized_vol_window_minutes, min_periods=2).std()
        * math.sqrt(1440)
    )

    # --- breakout: use high.shift(1) to avoid including current bar ---
    rolling_high = high.shift(1).rolling(params.breakout_window_minutes, min_periods=1).max()

    # --- EMA filter ---
    ema = close.ewm(span=params.ema_window_minutes, adjust=False).mean()

    # --- ATR ---
    tr = _true_range(high, low, close)
    atr = tr.rolling(params.atr_window_minutes, min_periods=1).mean()

    return {
        "return_fast": return_fast,
        "return_slow": return_slow,
        "volume_z": volume_z,
        "realized_vol": realized_vol,
        "rolling_high": rolling_high,
        "ema": ema,
        "atr": atr,
        "close": close,
    }


def compute_benchmark_regime(
    benchmark_close: pd.Series,
    params: OHLCVRotationParams,
) -> pd.Series:
    """True when benchmark is above its long EMA (bull regime)."""
    ema = benchmark_close.ewm(span=params.benchmark_ema_window_minutes, adjust=False).mean()
    return benchmark_close > ema


# ---------------------------------------------------------------------------
# Cross-sectional scoring
# ---------------------------------------------------------------------------

def compute_cross_sectional_scores(
    features: dict[str, pd.DataFrame],
    params: OHLCVRotationParams,
) -> pd.DataFrame:
    """
    Row-wise cross-sectional z-score each feature, then blend with params weights.
    Instruments missing any required feature at a given timestamp get NaN score.
    """
    def _zscore_row(row: pd.Series) -> pd.Series:
        if row.notna().sum() < 2:
            return pd.Series(np.nan, index=row.index)
        # Pass raw values so scipy returns same-length array (NaN preserved).
        arr = zscore(row.values, nan_policy="omit")
        # std=0 (all identical values) → zscore returns NaN at those positions.
        # Treat as 0 contribution so one degenerate feature doesn't kill the score.
        valid_mask = row.notna().values
        result = np.where(np.isnan(arr) & valid_mask, 0.0, arr)
        return pd.Series(result, index=row.index)

    def _row_zscore(df: pd.DataFrame) -> pd.DataFrame:
        return df.apply(_zscore_row, axis=1)

    z_slow = _row_zscore(features["return_slow"])
    z_fast = _row_zscore(features["return_fast"])
    z_vol = _row_zscore(features["volume_z"])
    z_rvol = _row_zscore(features["realized_vol"])

    score = (
        params.weight_return_slow * z_slow
        + params.weight_return_fast * z_fast
        + params.weight_volume_z * z_vol
        + params.weight_realized_vol * z_rvol
    )
    return score


# ---------------------------------------------------------------------------
# Target weight generation (no position-state dependency)
# ---------------------------------------------------------------------------

def generate_target_weights(
    scores: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    regime: pd.Series,
    params: OHLCVRotationParams,
    rebalance_timestamps: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    At each rebalance bar, rank instruments and apply entry filters.
    Returns a DataFrame of target weights at rebalance frequency.
    """
    inst_ids = scores.columns.tolist()
    rows: list[dict] = []

    for ts in rebalance_timestamps:
        if ts not in scores.index:
            continue

        weights: dict[str, float] = {i: 0.0 for i in inst_ids}

        # Regime gate: clear all if benchmark is bearish
        if not regime.get(ts, False):
            rows.append({"ts": ts, **weights})
            continue

        row_score = scores.loc[ts]
        row_feats = {k: features[k].loc[ts] if ts in features[k].index else pd.Series(dtype=float)
                     for k in features}

        close_row = row_feats["close"]
        ema_row = row_feats["ema"]
        rh_row = row_feats["rolling_high"]
        rf_row = row_feats["return_fast"]
        rs_row = row_feats["return_slow"]

        valid = row_score.dropna()
        if valid.empty:
            rows.append({"ts": ts, **weights})
            continue

        # rank: 1 = best
        ranks = valid.rank(ascending=False, method="min")

        selected = []
        for inst in valid.index:
            if ranks[inst] > params.top_k:
                continue
            if rf_row.get(inst, np.nan) <= 0:
                continue
            if rs_row.get(inst, np.nan) <= 0:
                continue
            c = close_row.get(inst, np.nan)
            rh = rh_row.get(inst, np.nan)
            em = ema_row.get(inst, np.nan)
            if not (c > rh and c > em):
                continue
            selected.append(inst)

        if selected:
            w = min(1.0 / len(selected), params.max_position_weight)
            for inst in selected:
                weights[inst] = w

        rows.append({"ts": ts, **weights})

    result = pd.DataFrame(rows).set_index("ts")
    result.index = pd.DatetimeIndex(result.index)
    return result


# ---------------------------------------------------------------------------
# Exit rules (stateful loop over rebalance timestamps)
# ---------------------------------------------------------------------------

def apply_exit_rules(
    raw_weights: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    scores: pd.DataFrame,
    regime: pd.Series,
    params: OHLCVRotationParams,
) -> pd.DataFrame:
    """
    Walk forward over rebalance timestamps applying stateful exit conditions.
    Mutates a copy of raw_weights to zero out positions that hit any exit rule.
    """
    weights = raw_weights.copy()
    inst_ids = weights.columns.tolist()

    # state per instrument
    entry_price: dict[str, float] = {i: 0.0 for i in inst_ids}
    entry_ts: dict[str, Optional[pd.Timestamp]] = {i: None for i in inst_ids}

    for ts in weights.index:
        close_row = features["close"].loc[ts] if ts in features["close"].index else pd.Series(dtype=float)
        ema_row = features["ema"].loc[ts] if ts in features["ema"].index else pd.Series(dtype=float)
        atr_row = features["atr"].loc[ts] if ts in features["atr"].index else pd.Series(dtype=float)
        score_row = scores.loc[ts] if ts in scores.index else pd.Series(dtype=float)

        regime_ok = regime.get(ts, True)

        # Compute ranks at this rebalance bar
        valid_scores = score_row.dropna()
        ranks = valid_scores.rank(ascending=False, method="min") if not valid_scores.empty else pd.Series(dtype=float)

        for inst in inst_ids:
            currently_held = (entry_ts[inst] is not None)

            # New position opened this bar
            target_w = weights.loc[ts, inst]
            if target_w > 0 and not currently_held:
                c = close_row.get(inst, np.nan)
                if not np.isnan(c):
                    entry_price[inst] = c
                    entry_ts[inst] = ts

            # Evaluate exit rules for existing positions
            if currently_held:
                c = close_row.get(inst, np.nan)
                em = ema_row.get(inst, np.nan)
                at = atr_row.get(inst, np.nan)
                rank = ranks.get(inst, np.inf)
                sc = score_row.get(inst, 0.0)
                holding_min = (ts - entry_ts[inst]).total_seconds() / 60 if entry_ts[inst] else 0

                exit_triggered = False
                if not regime_ok:
                    exit_triggered = True
                elif rank > params.rank_exit_buffer:
                    exit_triggered = True
                elif not np.isnan(c) and not np.isnan(em) and c < em:
                    exit_triggered = True
                elif (
                    not np.isnan(c) and not np.isnan(at)
                    and c < entry_price[inst] - params.atr_stop_multiple * at
                ):
                    exit_triggered = True
                elif holding_min > params.max_holding_minutes and sc <= 0:
                    exit_triggered = True

                if exit_triggered:
                    weights.loc[ts, inst] = 0.0
                    entry_price[inst] = 0.0
                    entry_ts[inst] = None

            # If weight dropped to 0 externally (raw weight was 0), clear state
            if weights.loc[ts, inst] == 0.0:
                entry_price[inst] = 0.0
                entry_ts[inst] = None

    return weights


# ---------------------------------------------------------------------------
# Strategy stub (Phase 2 live integration hook)
# ---------------------------------------------------------------------------

class OHLCVRotationStrategy(Strategy):
    """
    Phase 1: no-op stub. All backtest logic lives in build_feature_panel /
    compute_cross_sectional_scores / generate_target_weights / apply_exit_rules.
    Phase 2: implement on_market() to consume CandlePayload events.
    """

    def __init__(self, params: dict) -> None:
        super().__init__("ohlcv_rotation", params)

    async def on_market(
        self,
        event: Event,
        book=None,
    ) -> Optional[SignalPayload]:
        # Phase 2: handle CandlePayload here
        return None

    async def on_fill(self, event: Event) -> None:
        pass
