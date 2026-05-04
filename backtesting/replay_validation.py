"""Replay-based walk-forward and CPCV validation helpers."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable

import pandas as pd

from backtesting.cpcv import CPCV
from backtesting.replay import ReplayBacktestResult, run_replay_backtest
from backtesting.walk_forward import WalkForward
from okx_quant.core.config import AppConfig


ReplayRunner = Callable[..., ReplayBacktestResult]


@dataclass(frozen=True)
class ASMMReplayParamGrid:
    gamma: tuple[float, ...] = (0.1,)
    kappa: tuple[float, ...] = (1.5,)
    beta_vpin: tuple[float, ...] = (2.0,)

    def combinations(self) -> list[dict[str, float]]:
        return [
            {"gamma": gamma, "kappa": kappa, "beta_vpin": beta_vpin}
            for gamma, kappa, beta_vpin in product(self.gamma, self.kappa, self.beta_vpin)
        ]


def _as_utc_index(index: pd.Index) -> pd.DatetimeIndex:
    dt_index = pd.DatetimeIndex(index)
    if dt_index.tz is None:
        return dt_index.tz_localize("UTC")
    return dt_index.tz_convert("UTC")


def _infer_step(index: pd.DatetimeIndex) -> pd.Timedelta:
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
    end = index[-1] + _infer_step(index)
    return start.isoformat(), end.isoformat()


def _with_asmm_params(cfg: AppConfig, params: dict[str, float]) -> AppConfig:
    asmm = cfg.strategies.as_market_maker.model_copy(update=params)
    strategies = cfg.strategies.model_copy(update={"as_market_maker": asmm})
    return cfg.model_copy(update={"strategies": strategies})


def _align_replay_returns(returns: pd.Series, target_index: pd.Index) -> pd.Series:
    target = _as_utc_index(target_index)
    if returns.empty:
        return pd.Series(0.0, index=target)

    replay_returns = pd.Series(returns.to_numpy(dtype=float), index=returns.index)
    if not isinstance(replay_returns.index, pd.DatetimeIndex):
        replay_returns.index = pd.to_datetime(replay_returns.index, unit="ms", utc=True)
    else:
        replay_returns.index = _as_utc_index(replay_returns.index)

    replay_returns = replay_returns.groupby(level=0).sum().sort_index()
    return replay_returns.reindex(target, fill_value=0.0)


def _run_asmm_replay_window(
    *,
    cfg: AppConfig,
    params: dict[str, float],
    window: pd.DataFrame,
    data_dir: str,
    bar: str,
    periods: int,
    runner: ReplayRunner,
) -> ReplayBacktestResult:
    start, end = _window_bounds(window)
    return runner(
        strategy_names=["as_market_maker"],
        cfg=_with_asmm_params(cfg, params),
        data_dir=data_dir,
        start=start,
        end=end,
        bar=bar,
        periods=periods,
    )


def replay_asmm_parameter_selection_returns(
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
    *,
    cfg: AppConfig,
    data_dir: str = "data/ticks",
    bar: str = "1H",
    periods: int = 365 * 24,
    param_grid: ASMMReplayParamGrid | None = None,
    selection_metric: str = "sharpe",
    runner: ReplayRunner = run_replay_backtest,
) -> dict:
    """Select AS MM params on IS replay and execute the selected params on OOS replay."""
    grid = param_grid or ASMMReplayParamGrid()
    combinations = grid.combinations()
    if not combinations:
        raise ValueError("AS MM replay parameter grid cannot be empty")

    best_params: dict[str, float] | None = None
    best_score = float("-inf")
    is_trials = []

    for params in combinations:
        is_result = _run_asmm_replay_window(
            cfg=cfg,
            params=params,
            window=train_data,
            data_dir=data_dir,
            bar=bar,
            periods=periods,
            runner=runner,
        )
        score = float(is_result.metrics.get(selection_metric, float("-inf")))
        is_trials.append({"params": dict(params), "score": score, "metrics": dict(is_result.metrics)})
        if score > best_score:
            best_score = score
            best_params = dict(params)

    assert best_params is not None
    oos_result = _run_asmm_replay_window(
        cfg=cfg,
        params=best_params,
        window=test_data,
        data_dir=data_dir,
        bar=bar,
        periods=periods,
        runner=runner,
    )
    oos_returns = _align_replay_returns(oos_result.returns, test_data.index)

    return {
        "returns": oos_returns,
        "selected_params": best_params,
        "is_score": best_score,
        "is_trials": is_trials,
        "oos_metrics": dict(oos_result.metrics),
        "oos_order_count": len(oos_result.order_log),
        "oos_fill_count": len(oos_result.fill_log),
        "returns_source": "replay_asmm_parameter_selection",
    }


def evaluate_replay_asmm_cpcv(
    df: pd.DataFrame,
    *,
    cfg: AppConfig,
    data_dir: str = "data/ticks",
    bar: str = "1H",
    periods: int = 365 * 24,
    param_grid: ASMMReplayParamGrid | None = None,
    n_splits: int = 6,
    k_test: int = 2,
    embargo_pct: float = 0.02,
    purge_size: int = 1,
    runner: ReplayRunner = run_replay_backtest,
) -> dict:
    grid = param_grid or ASMMReplayParamGrid()
    cpcv = CPCV(n_splits=n_splits, k_test=k_test, embargo_pct=embargo_pct, purge_size=purge_size)
    results = cpcv.evaluate(
        df,
        lambda train, test: replay_asmm_parameter_selection_returns(
            train,
            test,
            cfg=cfg,
            data_dir=data_dir,
            bar=bar,
            periods=periods,
            param_grid=grid,
            runner=runner,
        ),
        periods=periods,
        n_trials=len(grid.combinations()),
    )
    results.update({
        "returns_source": "replay_asmm_parameter_selection",
        "cost_model_complete": True,
        "calibration_required": True,
        "cost_model_note": (
            "Replay CPCV uses SimBroker plus ReplayExecutionModel for fees, "
            "slippage, missed fills, partial fills, and cancel latency. Queue "
            "and latency parameters still require demo/shadow calibration."
        ),
    })
    return results


def evaluate_replay_asmm_walk_forward(
    df: pd.DataFrame,
    *,
    cfg: AppConfig,
    data_dir: str = "data/ticks",
    bar: str = "1H",
    periods: int = 365 * 24,
    param_grid: ASMMReplayParamGrid | None = None,
    is_days: int = 30,
    oos_days: int = 7,
    runner: ReplayRunner = run_replay_backtest,
) -> pd.DataFrame:
    grid = param_grid or ASMMReplayParamGrid()
    wf = WalkForward(is_days=is_days, oos_days=oos_days)
    return wf.evaluate(
        df,
        lambda train, test: replay_asmm_parameter_selection_returns(
            train,
            test,
            cfg=cfg,
            data_dir=data_dir,
            bar=bar,
            periods=periods,
            param_grid=grid,
            runner=runner,
        ),
        periods=periods,
    )
