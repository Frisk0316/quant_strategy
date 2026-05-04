"""
Combinatorial Purged Cross-Validation (CPCV).
Implements López de Prado's AFML framework for overfitting-resistant validation.

Settings from §3.5: N=6, k=2, embargo=2%
C(6,2) = 15 test combinations → 5 complete OOS paths.

Reference: López de Prado - "Advances in Financial Machine Learning" (2018)
"""
from __future__ import annotations

from itertools import combinations
from math import comb
from typing import Callable, Generator

import numpy as np
import pandas as pd

from okx_quant.analytics.dsr import deflated_sharpe, psr
from okx_quant.analytics.performance import sharpe
from backtesting.result_utils import extract_returns


class CPCV:
    def __init__(
        self,
        n_splits: int = 6,
        k_test: int = 2,
        embargo_pct: float = 0.02,
        purge_size: int = 1,
    ) -> None:
        """
        Args:
            n_splits: Number of groups to split data into (N=6 from plan).
            k_test: Number of test groups per combination (k=2 from plan).
            embargo_pct: Fraction of data to embargo after each test block.
            purge_size: Number of samples to purge immediately before each
                test block to account for forward-label overlap.
        """
        self.n_splits = n_splits
        self.k_test = k_test
        self.embargo_pct = embargo_pct
        self.purge_size = purge_size

    def _build_groups(self, n: int) -> list[np.ndarray]:
        if self.n_splits < 2:
            raise ValueError("n_splits must be at least 2")
        if not 1 <= self.k_test < self.n_splits:
            raise ValueError("k_test must be between 1 and n_splits - 1")
        if n < self.n_splits:
            raise ValueError("Dataset must contain at least n_splits rows")

        group_size = n // self.n_splits
        groups = []
        for i in range(self.n_splits):
            start = i * group_size
            end = (i + 1) * group_size if i < self.n_splits - 1 else n
            groups.append(np.arange(start, end))
        return groups

    def _apply_purge_and_embargo(
        self,
        n: int,
        groups: list[np.ndarray],
        test_groups: tuple[int, ...],
    ) -> tuple[np.ndarray, np.ndarray]:
        embargo_size = int(np.ceil(n * self.embargo_pct))
        train_mask = np.ones(n, dtype=bool)

        for group_id in test_groups:
            test_indices = groups[group_id]
            if len(test_indices) == 0:
                continue

            group_start = int(test_indices[0])
            group_end_exclusive = int(test_indices[-1]) + 1

            train_mask[test_indices] = False

            if self.purge_size > 0:
                purge_start = max(0, group_start - self.purge_size)
                train_mask[purge_start:group_start] = False

            if embargo_size > 0:
                embargo_end = min(n, group_end_exclusive + embargo_size)
                train_mask[group_end_exclusive:embargo_end] = False

        test_indices = np.concatenate([groups[g] for g in test_groups])
        train_indices = np.flatnonzero(train_mask)
        return train_indices, test_indices

    @staticmethod
    def _coerce_oos_returns(
        test_data: pd.DataFrame,
        oos_returns: pd.Series | np.ndarray | list[float] | dict | object,
    ) -> pd.Series:
        normalized = extract_returns(oos_returns)
        series = normalized if isinstance(normalized, pd.Series) else pd.Series(normalized)
        series = series.dropna()
        if series.empty:
            return pd.Series(dtype=float)

        if len(series) == len(test_data):
            return pd.Series(series.to_numpy(dtype=float), index=test_data.index)

        common_index = test_data.index.intersection(series.index)
        if len(common_index) == len(series):
            aligned = series.loc[common_index]
            return pd.Series(aligned.to_numpy(dtype=float), index=common_index)

        raise ValueError(
            "strategy_fn must return a Series aligned to test_data.index "
            "or a return vector with the same length as test_data"
        )

    def _path_combo_indices(self) -> list[list[int]]:
        if self.n_splits % self.k_test != 0:
            return []

        combo_groups = list(combinations(range(self.n_splits), self.k_test))
        n_paths = comb(self.n_splits - 1, self.k_test - 1)
        combos_per_path = self.n_splits // self.k_test

        paths: list[list[int]] = [[] for _ in range(n_paths)]
        path_groups: list[set[int]] = [set() for _ in range(n_paths)]
        combo_order = list(range(len(combo_groups)))

        def backtrack(position: int) -> bool:
            if position == len(combo_order):
                return all(len(groups) == self.n_splits for groups in path_groups)

            combo_idx = combo_order[position]
            combo_set = set(combo_groups[combo_idx])
            seen_states: set[tuple[int, ...]] = set()

            for path_idx in range(n_paths):
                state_key = tuple(sorted(path_groups[path_idx]))
                if state_key in seen_states:
                    continue
                seen_states.add(state_key)

                if len(paths[path_idx]) >= combos_per_path:
                    continue
                if combo_set & path_groups[path_idx]:
                    continue

                paths[path_idx].append(combo_idx)
                previous_groups = set(path_groups[path_idx])
                path_groups[path_idx].update(combo_set)

                if backtrack(position + 1):
                    return True

                paths[path_idx].pop()
                path_groups[path_idx] = previous_groups

            return False

        if not backtrack(0):
            return []

        return paths

    def split(
        self,
        df: pd.DataFrame,
    ) -> Generator[tuple[np.ndarray, np.ndarray], None, None]:
        """
        Yield (train_idx, test_idx) arrays for all C(N, k) combinations.
        Purging and embargo are applied per test block, not across the full span.
        """
        n = len(df)
        groups = self._build_groups(n)

        for test_groups in combinations(range(self.n_splits), self.k_test):
            train_indices, test_indices = self._apply_purge_and_embargo(n, groups, test_groups)
            if len(train_indices) > 0 and len(test_indices) > 0:
                yield train_indices, test_indices

    def evaluate(
        self,
        df: pd.DataFrame,
        strategy_fn: Callable[[pd.DataFrame, pd.DataFrame], pd.Series],
        periods: int = 365,
        n_trials: int | None = None,
    ) -> dict:
        """
        Run CPCV evaluation and compute OOS combination/path metrics.

        Args:
            df: Full dataset with DatetimeIndex.
            strategy_fn: Callable(train_data, test_data) → pd.Series of returns.
            periods: Annualization period.
            n_trials: Number of strategy/parameter trials actually researched.
                Used as N in Deflated Sharpe Ratio. When omitted, falls back to
                the number of CPCV paths or combinations for backward
                compatibility.

        Returns:
            dict with combination-level and path-level OOS metrics.
        """
        n = len(df)
        groups = self._build_groups(n)
        combo_groups = list(combinations(range(self.n_splits), self.k_test))
        combo_results = []

        for test_groups in combo_groups:
            train_idx, test_idx = self._apply_purge_and_embargo(n, groups, test_groups)
            train_data = df.iloc[train_idx]
            test_data = df.iloc[test_idx]
            strategy_result = strategy_fn(train_data, test_data)
            normalized_returns = self._coerce_oos_returns(test_data, strategy_result)

            if normalized_returns.empty:
                continue

            group_return_map = {}
            for group_id in test_groups:
                group_index = df.index[groups[group_id]]
                group_returns = normalized_returns.reindex(group_index).dropna()
                group_return_map[group_id] = group_returns

            combo_results.append({
                "test_groups": test_groups,
                "returns": normalized_returns,
                "sharpe": sharpe(normalized_returns, periods=periods),
                "group_returns": group_return_map,
                "result": strategy_result,
            })

        if not combo_results:
            return {
                "sharpe_list": [],
                "overall_oos_sharpe": 0.0,
                "dsr": 0.0,
                "n_combinations": 0,
                "mean_oos_sharpe": 0.0,
                "psr": 0.0,
                "n_paths": 0,
                "path_sharpes": [],
                "n_trials": int(n_trials or 0),
            }

        combo_sharpes = [result["sharpe"] for result in combo_results]
        combo_by_groups = {result["test_groups"]: result for result in combo_results}
        path_sharpes = []
        path_returns_list = []

        for combo_idx_list in self._path_combo_indices():
            path_chunks = []
            for combo_idx in combo_idx_list:
                group_ids = combo_groups[combo_idx]
                result = combo_by_groups.get(group_ids)
                if result is None:
                    path_chunks = []
                    break
                for group_id in sorted(group_ids):
                    group_returns = result["group_returns"].get(group_id)
                    if group_returns is not None and not group_returns.empty:
                        path_chunks.append(group_returns)

            if path_chunks:
                path_returns = pd.concat(path_chunks)
                path_returns_list.append(path_returns)
                path_sharpes.append(sharpe(path_returns, periods=periods))

        if path_returns_list:
            combined_returns = pd.concat(path_returns_list, ignore_index=True)
            overall_sr = float(np.mean(path_sharpes))
            dsr_val = deflated_sharpe(
                returns=np.asarray(combined_returns, dtype=float),
                sr=overall_sr,
                sr_list=path_sharpes,
                N=max(int(n_trials or len(path_sharpes)), 1),
            )
            psr_val = float(
                np.mean([psr(np.asarray(path_returns, dtype=float)) for path_returns in path_returns_list])
            )
        else:
            combined_returns = pd.concat([result["returns"] for result in combo_results], ignore_index=True)
            overall_sr = sharpe(combined_returns, periods=periods)
            dsr_val = deflated_sharpe(
                returns=np.asarray(combined_returns, dtype=float),
                sr=overall_sr,
                sr_list=combo_sharpes,
                N=max(int(n_trials or len(combo_sharpes)), 1),
            )
            psr_val = psr(np.asarray(combined_returns, dtype=float))

        return {
            "sharpe_list": combo_sharpes,
            "overall_oos_sharpe": overall_sr,
            "dsr": dsr_val,
            "n_combinations": len(combo_results),
            "mean_oos_sharpe": float(np.mean(combo_sharpes)) if combo_sharpes else 0.0,
            "psr": psr_val,
            "n_paths": len(path_sharpes),
            "path_sharpes": path_sharpes,
            "n_trials": max(int(n_trials or 0), 0),
        }
