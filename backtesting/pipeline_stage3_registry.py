"""Stage 3 runner registry for pipeline orchestration."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from scripts.run_funding_xs_dispersion_checkpoint import run_funding_xs_dispersion_checkpoint
from scripts.run_oi_positioning_checkpoint import run_oi_positioning_checkpoint
from scripts.run_pipeline_batch2_checkpoint import run_c1, run_c2, run_c3
from backtesting.xvenue_funding_spread_backtest import run_xvenue_funding_spread_checkpoint

Stage3Context = Mapping[str, Any]
Stage3Runner = Callable[[Stage3Context], dict[str, Any]]

_LEGACY_BATCH_ID = "pipeline_batch2_20260625"


def _legacy_runner(fn: Callable[[], dict[str, Any]], family_id: str) -> Stage3Runner:
    def _run(ctx: Stage3Context) -> dict[str, Any]:
        if ctx["batch_id"] != _LEGACY_BATCH_ID:
            raise RuntimeError(
                f"{family_id} Stage3 runner is a refuted-batch demo entry scoped to "
                f"batch_id={_LEGACY_BATCH_ID!r}; refusing to run for "
                f"batch_id={ctx['batch_id']!r} to avoid overwriting the old batch2 "
                "results directory"
            )
        return fn()

    return _run


STAGE3_RUNNERS: dict[str, Stage3Runner] = {
    "F-PAIRS-OU": _legacy_runner(run_c1, "F-PAIRS-OU"),
    "F-FUNDING-CARRY": _legacy_runner(run_c2, "F-FUNDING-CARRY"),
    "F-SENTIMENT": _legacy_runner(run_c3, "F-SENTIMENT"),
    "F-FUNDING-XS-DISPERSION": run_funding_xs_dispersion_checkpoint,
    "F-OI-POSITIONING": run_oi_positioning_checkpoint,
    "F-XVENUE-FUNDING-SPREAD": run_xvenue_funding_spread_checkpoint,
}
