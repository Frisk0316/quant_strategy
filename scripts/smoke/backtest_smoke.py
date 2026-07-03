"""Tiny no-DB replay smoke for the backtest artifact path."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "backtesting"))

from backtesting.artifacts import save_backtest_artifacts
from backtesting.replay import run_replay_backtest
from backtesting.research_controls import (
    EXECUTION_PROFILE_STRATEGY_FILL,
    apply_execution_profile_controls,
    summarize_risk_events,
)
from okx_quant.core.config import load_config


STRATEGY = "ma_crossover"
SYMBOL = "BTC-USDT-SWAP"
BAR = "1H"
START = "2024-01-01T00:00:00Z"
END = "2024-01-01T09:00:00Z"
RUN_ID = "backtest_smoke_ma_crossover_fixture"
FIXTURE_CSV = REPO_ROOT / "tests" / "fixtures" / "backtest_smoke" / "BTC_USDT_SWAP" / "candles_1H.csv"
REQUIRED_ARTIFACTS = ("result.json", "metrics.json", "fills.csv")
INSTRUMENT_SPECS = {
    SYMBOL: {
        "ctVal": 0.01,
        "minSz": 0.01,
        "lotSz": 0.01,
        "tickSz": 0.1,
        "tdMode": "cross",
    }
}


@contextmanager
def _no_db_file_artifacts():
    previous_mode = os.environ.get("BACKTEST_ARTIFACT_MODE")
    previous_dsn = os.environ.get("DATABASE_URL")
    os.environ["BACKTEST_ARTIFACT_MODE"] = "files"
    os.environ.pop("DATABASE_URL", None)
    try:
        yield
    finally:
        if previous_mode is None:
            os.environ.pop("BACKTEST_ARTIFACT_MODE", None)
        else:
            os.environ["BACKTEST_ARTIFACT_MODE"] = previous_mode
        if previous_dsn is not None:
            os.environ["DATABASE_URL"] = previous_dsn


def _write_temp_parquet(tmp_root: Path) -> Path:
    if not FIXTURE_CSV.exists():
        raise FileNotFoundError(f"Missing smoke fixture: {FIXTURE_CSV.relative_to(REPO_ROOT)}")
    data_dir = tmp_root / "data"
    inst_dir = data_dir / "BTC_USDT_SWAP"
    inst_dir.mkdir(parents=True)
    candles = pd.read_csv(FIXTURE_CSV)
    candles.to_parquet(inst_dir / "candles_1H.parquet", index=False)
    return data_dir


def _smoke_config():
    cfg = load_config(require_secrets=False)
    cfg = cfg.model_copy(deep=True)
    cfg.storage = cfg.storage.model_copy(update={"candle_backend": "parquet", "timescale_dsn": None})
    cfg.system = cfg.system.model_copy(update={"symbols": [SYMBOL], "spot_symbols": []})
    cfg.strategies.ma_crossover = cfg.strategies.ma_crossover.model_copy(
        update={
            "symbols": [SYMBOL],
            "fast_window": 2,
            "slow_window": 3,
            "indicator_db_warmup": False,
        }
    )
    cfg, controls = apply_execution_profile_controls(cfg, EXECUTION_PROFILE_STRATEGY_FILL, allow_internal=True)
    return cfg, controls


def _artifact_args() -> SimpleNamespace:
    return SimpleNamespace(
        strategy=[STRATEGY],
        start=START,
        end=END,
        bar=BAR,
        symbol=[SYMBOL],
        strategy_params={"fast_window": 2, "slow_window": 3},
        risk_overrides=None,
        execution_profile=EXECUTION_PROFILE_STRATEGY_FILL,
        save_artifacts=True,
        output_dir=None,
        run_id=RUN_ID,
        artifact_format="csv",
        validate=None,
        liquidate_on_end=True,
    )


def _check_artifacts(run_dir: Path) -> None:
    missing = [name for name in REQUIRED_ARTIFACTS if not (run_dir / name).exists()]
    if missing:
        raise RuntimeError(f"Missing smoke artifact(s): {', '.join(missing)}")

    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    fills = pd.read_csv(run_dir / "fills.csv")

    if result.get("mode") != "replay_backtest":
        raise RuntimeError("result.json does not describe a replay_backtest run")
    if result.get("strategies") != [STRATEGY]:
        raise RuntimeError(f"Unexpected strategies in result.json: {result.get('strategies')}")
    if result.get("symbols") != [SYMBOL]:
        raise RuntimeError(f"Unexpected symbols in result.json: {result.get('symbols')}")
    if not metrics:
        raise RuntimeError("metrics.json is empty")
    if fills.empty:
        raise RuntimeError("fills.csv has no rows")
    validation = result.get("validation") or {}
    if not validation.get("idealized_fill"):
        raise RuntimeError("smoke artifact did not record idealized_fill=true")


def main() -> int:
    with _no_db_file_artifacts(), tempfile.TemporaryDirectory(prefix="backtest_smoke_") as tmp:
        tmp_root = Path(tmp)
        data_dir = _write_temp_parquet(tmp_root)
        output_dir = tmp_root / "artifacts"
        cfg, controls = _smoke_config()

        result = run_replay_backtest(
            strategy_names=[STRATEGY],
            cfg=cfg,
            data_dir=str(data_dir),
            start=START,
            end=END,
            bar=BAR,
            periods=365 * 24,
            instrument_specs=INSTRUMENT_SPECS,
            liquidate_on_end=True,
        )
        result.validation["execution_profile"] = EXECUTION_PROFILE_STRATEGY_FILL
        result.validation["idealized_fill"] = True
        result.validation["research_fill_all_signals"] = controls.get("research_fill_all_signals", {})
        result.validation["risk_summary"] = summarize_risk_events(result.risk_event_log)

        run_dir = save_backtest_artifacts(
            result=result,
            cfg=cfg,
            args=_artifact_args(),
            output_dir=str(output_dir),
            run_id=RUN_ID,
            strategy_names=[STRATEGY],
            start=START,
            end=END,
            bar=BAR,
        )
        _check_artifacts(run_dir)

        print(f"PASS replay smoke: strategy={STRATEGY} symbol={SYMBOL} bars=9")
        print(f"PASS artifacts: {', '.join(REQUIRED_ARTIFACTS)}")
        print(f"PASS fills: {len(result.fill_log)}")
        print("NOTE fixture uses strategy_fill/idealized_fill and is not promotion evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
