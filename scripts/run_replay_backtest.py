"""Run replay-based backtests through the event-driven execution stack."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "backtesting"))

from backtesting.artifacts import build_run_id, save_backtest_artifacts
from backtesting.replay import run_replay_backtest, run_replay_validations
from backtesting.research_controls import (
    EXECUTION_PROFILE_DUAL_OUTPUT,
    EXECUTION_PROFILE_REALISTIC,
    EXECUTION_PROFILE_STRATEGY_FILL,
    apply_execution_profile_controls,
    apply_research_risk_overrides,
    normalize_execution_profile,
    summarize_risk_events,
)
from okx_quant.core.config import load_config
from okx_quant.core.symbols import normalize_spot_symbol, normalize_swap_symbol

BAR_PERIODS = {
    "1m": 525600, "3m": 175200, "5m": 105120, "15m": 35040,
    "30m": 17520, "1H": 8760, "2H": 4380, "4H": 2190, "1D": 365,
}

COMPARISON_KEYS = [
    "signal_count",
    "submitted_order_count",
    "real_fill_count",
    "submitted_order_fill_count",
    "terminal_liquidation_fill_count",
    "fill_rate",
    "total_return",
    "max_drawdown",
]


def _profile_from_args(args: argparse.Namespace) -> str:
    if args.fill_all_signals:
        return EXECUTION_PROFILE_STRATEGY_FILL
    return normalize_execution_profile(args.execution_profile, allow_internal=True)


def _comparison_metrics(result) -> dict:
    metrics = dict(getattr(result, "metrics", {}) or {})
    out = {key: metrics.get(key) for key in COMPARISON_KEYS}
    out["signal_count"] = len(getattr(result, "signal_log", []) or [])
    return out


def _delta(left: dict, right: dict, key: str) -> float | None:
    try:
        return float(left.get(key)) - float(right.get(key))
    except (TypeError, ValueError):
        return None


def _write_execution_comparison(
    *,
    output_dir: str,
    base_run_id: str,
    strategy_fill_run_id: str,
    realistic_run_id: str,
    strategy_fill_result,
    realistic_result,
) -> Path:
    strategy_metrics = _comparison_metrics(strategy_fill_result)
    realistic_metrics = _comparison_metrics(realistic_result)
    payload = {
        "base_run_id": base_run_id,
        "execution_profile": EXECUTION_PROFILE_DUAL_OUTPUT,
        "strategy_fill_run_id": strategy_fill_run_id,
        "realistic_execution_run_id": realistic_run_id,
        "metrics": {
            EXECUTION_PROFILE_STRATEGY_FILL: strategy_metrics,
            EXECUTION_PROFILE_REALISTIC: realistic_metrics,
        },
        "deltas": {
            "strategy_minus_realistic_return": _delta(strategy_metrics, realistic_metrics, "total_return"),
            "strategy_minus_realistic_fill_rate": _delta(strategy_metrics, realistic_metrics, "fill_rate"),
        },
    }
    path = Path(output_dir) / f"{base_run_id}_execution_comparison.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _print_validation_progress(update: dict) -> None:
    pct = int(update.get("progress", 85))
    message = str(update.get("message") or "Running replay validation")
    print(f"PROGRESS:{pct}:{message}", flush=True)


def _run_profile_once(
    *,
    args: argparse.Namespace,
    cfg,
    profile: str,
    output_dir: str,
    run_id: str | None,
    strategy_params: dict,
    instrument_specs: dict | None,
    applied_risk_overrides: dict,
) -> tuple[object, Path | None]:
    profile_cfg, profile_controls = apply_execution_profile_controls(
        cfg,
        profile,
        allow_internal=True,
    )
    result = run_replay_backtest(
        strategy_names=args.strategy,
        cfg=profile_cfg,
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
        bar=args.bar,
        periods=args.periods or BAR_PERIODS.get(args.bar, 365 * 24),
        instrument_specs=instrument_specs,
        liquidate_on_end=args.liquidate_on_end,
    )
    result.validation["execution_profile"] = profile
    result.validation["risk_summary"] = summarize_risk_events(result.risk_event_log)
    if applied_risk_overrides:
        result.validation["research_risk_overrides"] = applied_risk_overrides
    if profile_controls.get("idealized_fill"):
        result.validation["idealized_fill"] = True
        result.validation["research_fill_all_signals"] = profile_controls.get("research_fill_all_signals", {})

    validation_results = None
    if args.save_artifacts and args.validate:
        print(f"Running replay validation: {args.validate}")
        validation_results = run_replay_validations(
            strategy_names=args.strategy,
            cfg=profile_cfg,
            data_dir=args.data_dir,
            start=args.start,
            end=args.end,
            bar=args.bar,
            periods=args.periods or BAR_PERIODS.get(args.bar, 365 * 24),
            mode=args.validate,
            instrument_specs=instrument_specs,
            liquidate_on_end=args.liquidate_on_end,
            progress_callback=_print_validation_progress,
        )
        print("PROGRESS:99:Saving replay artifacts", flush=True)

    run_dir = None
    if args.save_artifacts:
        artifact_args = argparse.Namespace(**vars(args))
        artifact_args.execution_profile = profile
        artifact_args.strategy_params = strategy_params
        run_dir = save_backtest_artifacts(
            result=result,
            cfg=profile_cfg,
            args=artifact_args,
            output_dir=output_dir,
            run_id=run_id,
            strategy_names=args.strategy,
            start=args.start,
            end=args.end,
            bar=args.bar,
            validation_results=validation_results,
        )
    return result, run_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", action="append", required=True,
                        choices=[
                            "funding_carry",
                            "pairs_trading",
                            "ma_crossover",
                            "ema_crossover",
                            "macd_crossover",
                            "fear_greed_sentiment",
                            "cme_gap_fill",
                        ])
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--bar", default="1H")
    parser.add_argument("--periods", type=int, default=None,
                        help="Annualization periods for the selected bar size")
    parser.add_argument("--symbol", action="append", default=[],
                        help="Instrument symbol for single/multi-symbol strategies")
    parser.add_argument("--symbol-x", default=None,
                        help="Reference/independent symbol for pairs_trading")
    parser.add_argument("--symbol-y", default=None,
                        help="Trade/spread/dependent symbol for pairs_trading")
    parser.add_argument("--perp-symbol", default=None,
                        help="Perpetual symbol for funding_carry")
    parser.add_argument("--spot-symbol", default=None,
                        help="Spot symbol for funding_carry")
    parser.add_argument("--min-apr-threshold", type=float, default=None,
                        help="Override funding_carry min APR threshold for this replay")
    parser.add_argument("--strategy-params", default=None,
                        help="JSON object with strategy-specific parameter overrides")
    parser.add_argument("--instrument-specs-json", default=None,
                        help="JSON object keyed by inst_id with explicit ctVal/minSz/lotSz/tickSz overrides")
    parser.add_argument("--risk-overrides", default=None,
                        help="JSON object with research-only risk overrides for this replay")
    parser.add_argument("--fill-all-signals", action="store_true",
                        help="Research-only: bypass execution/capacity caps and fill every submitted signal order")
    parser.add_argument("--execution-profile", default=EXECUTION_PROFILE_STRATEGY_FILL,
                        choices=[
                            EXECUTION_PROFILE_STRATEGY_FILL,
                            EXECUTION_PROFILE_DUAL_OUTPUT,
                            EXECUTION_PROFILE_REALISTIC,
                        ],
                        help="Backtest execution profile")
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data" / "ticks"))
    parser.add_argument("--save-artifacts", action="store_true",
                        help="Save all backtest artifacts to --output-dir/<run_id>/")
    parser.add_argument("--output-dir", default="results",
                        help="Directory to write artifact subdirectories (default: results)")
    parser.add_argument("--run-id", default=None,
                        help="Custom run ID; auto-generated if omitted")
    parser.add_argument("--artifact-format", default="csv", choices=["csv"],
                        help="Output format for tabular artifacts (default: csv)")
    parser.add_argument("--validate", choices=["wf", "cpcv", "both"], default=None,
                        help="Run replay-backed Walk-Forward, CPCV, or both and write them into result.json")
    parser.add_argument("--exchange", default=None,
                        choices=["binance", "okx", "bybit", "coinbase", "kraken"],
                        help="Override cfg.storage.primary_exchange for this run (data source selector)")
    liquidation_group = parser.add_mutually_exclusive_group()
    liquidation_group.add_argument("--liquidate-on-end", dest="liquidate_on_end", action="store_true", default=None,
                                   help="Close open replay positions at the final available mid price")
    liquidation_group.add_argument("--no-liquidate-on-end", dest="liquidate_on_end", action="store_false",
                                   help="Leave terminal replay positions open and report them in validation")
    args = parser.parse_args()

    cfg = load_config(require_secrets=False)
    risk_overrides = json.loads(args.risk_overrides) if args.risk_overrides else {}
    cfg, applied_risk_overrides = apply_research_risk_overrides(cfg, risk_overrides)
    if args.exchange:
        cfg.storage = cfg.storage.model_copy(update={"primary_exchange": args.exchange})
    if cfg.storage.candle_backend == "postgres" and not cfg.storage.timescale_dsn:
        cfg.storage.candle_backend = "parquet"
    strategy_params = json.loads(args.strategy_params) if args.strategy_params else {}
    if strategy_params and not isinstance(strategy_params, dict):
        sys.exit("Error: --strategy-params must be a JSON object")
    instrument_specs = json.loads(args.instrument_specs_json) if args.instrument_specs_json else None
    if instrument_specs is not None and not isinstance(instrument_specs, dict):
        sys.exit("Error: --instrument-specs-json must be a JSON object")

    if args.symbol:
        args.symbol = [normalize_swap_symbol(symbol) for symbol in args.symbol]
        if "ma_crossover" in args.strategy:
            cfg.strategies.ma_crossover = cfg.strategies.ma_crossover.model_copy(
                update={"symbols": args.symbol}
            )
        if "ema_crossover" in args.strategy:
            cfg.strategies.ema_crossover = cfg.strategies.ema_crossover.model_copy(
                update={"symbols": args.symbol}
            )
        if "macd_crossover" in args.strategy:
            cfg.strategies.macd_crossover = cfg.strategies.macd_crossover.model_copy(
                update={"symbols": args.symbol}
            )
        if "fear_greed_sentiment" in args.strategy:
            cfg.strategies.fear_greed_sentiment = cfg.strategies.fear_greed_sentiment.model_copy(
                update={"symbol": args.symbol[0]}
            )
        if "cme_gap_fill" in args.strategy:
            cfg.strategies.cme_gap_fill = cfg.strategies.cme_gap_fill.model_copy(
                update={"symbol": args.symbol[0]}
            )
        cfg.system.symbols = args.symbol
    if "pairs_trading" in args.strategy:
        if args.symbol_x:
            cfg.strategies.pairs_trading.symbol_x = normalize_swap_symbol(args.symbol_x)
        if args.symbol_y:
            cfg.strategies.pairs_trading.symbol_y = normalize_swap_symbol(args.symbol_y)
        cfg.system.symbols = [
            cfg.strategies.pairs_trading.symbol_y,
            cfg.strategies.pairs_trading.symbol_x,
        ]
    if "funding_carry" in args.strategy:
        if args.perp_symbol:
            cfg.strategies.funding_carry.perp_symbol = normalize_swap_symbol(args.perp_symbol)
            cfg.system.symbols = [cfg.strategies.funding_carry.perp_symbol]
        if args.spot_symbol:
            cfg.strategies.funding_carry.spot_symbol = normalize_spot_symbol(args.spot_symbol)
            cfg.system.spot_symbols = [cfg.strategies.funding_carry.spot_symbol]
        if args.min_apr_threshold is not None:
            cfg.strategies.funding_carry.min_apr_threshold = args.min_apr_threshold

    technical_names = {"ma_crossover", "ema_crossover", "macd_crossover"}
    single_symbol_names = {"fear_greed_sentiment", "cme_gap_fill"}
    selected_technical = technical_names.intersection(args.strategy)
    if strategy_params:
        if len(args.strategy) != 1:
            sys.exit("Error: --strategy-params is supported only for single-strategy replay runs")
        strategy_name = args.strategy[0]
        if not hasattr(cfg.strategies, strategy_name):
            sys.exit(f"Error: strategy params not supported for {strategy_name}")
        current = getattr(cfg.strategies, strategy_name)
        updates = dict(strategy_params)
        if args.symbol and "symbols" not in updates and strategy_name in technical_names:
            updates["symbols"] = args.symbol
        if args.symbol and "symbol" not in updates and strategy_name in single_symbol_names:
            updates["symbol"] = args.symbol[0]
        setattr(cfg.strategies, strategy_name, current.model_copy(update=updates))
    elif selected_technical and args.symbol:
        cfg.system.symbols = args.symbol

    profile = _profile_from_args(args)
    output_dir = str(PROJECT_ROOT / args.output_dir) if not Path(args.output_dir).is_absolute() else args.output_dir
    base_run_id = build_run_id(args.strategy, args.start, args.end, args.bar, args.run_id)

    print("PROGRESS:20:Running replay backtest", flush=True)
    if profile == EXECUTION_PROFILE_DUAL_OUTPUT:
        strategy_run_id = f"{base_run_id}_{EXECUTION_PROFILE_STRATEGY_FILL}"
        realistic_run_id = f"{base_run_id}_{EXECUTION_PROFILE_REALISTIC}"
        result, run_dir = _run_profile_once(
            args=args,
            cfg=cfg,
            profile=EXECUTION_PROFILE_STRATEGY_FILL,
            output_dir=output_dir,
            run_id=strategy_run_id,
            strategy_params=strategy_params,
            instrument_specs=instrument_specs,
            applied_risk_overrides=applied_risk_overrides,
        )
        realistic_result, _realistic_dir = _run_profile_once(
            args=args,
            cfg=cfg,
            profile=EXECUTION_PROFILE_REALISTIC,
            output_dir=output_dir,
            run_id=realistic_run_id,
            strategy_params=strategy_params,
            instrument_specs=instrument_specs,
            applied_risk_overrides=applied_risk_overrides,
        )
        if args.save_artifacts:
            comparison_path = _write_execution_comparison(
                output_dir=output_dir,
                base_run_id=base_run_id,
                strategy_fill_run_id=strategy_run_id,
                realistic_run_id=realistic_run_id,
                strategy_fill_result=result,
                realistic_result=realistic_result,
            )
            print(f"Saved execution comparison to {comparison_path}")
    else:
        result, run_dir = _run_profile_once(
            args=args,
            cfg=cfg,
            profile=profile,
            output_dir=output_dir,
            run_id=args.run_id,
            strategy_params=strategy_params,
            instrument_specs=instrument_specs,
            applied_risk_overrides=applied_risk_overrides,
        )

    if args.save_artifacts and args.validate:
        stage = f"Saved replay validation ({args.validate}) artifacts"
    elif args.save_artifacts:
        stage = "Saved replay artifacts"
    else:
        stage = "Preparing replay summary"
    print(f"PROGRESS:85:{stage}", flush=True)

    print("=" * 72)
    print("REPLAY BACKTEST SUMMARY")
    print(f"Strategies: {', '.join(args.strategy)}")
    real_fill_count = result.metrics.get("real_fill_count", len(result.fill_log))
    print(f"Orders: {len(result.order_log)} | Real Fills: {real_fill_count}")
    for key, value in result.metrics.items():
        if isinstance(value, float):
            print(f"{key:>28}: {value:.6f}")
        else:
            print(f"{key:>28}: {value}")
    print("=" * 72)

    if args.save_artifacts and run_dir is not None:
        print(f"Saved backtest artifacts to {run_dir}")


if __name__ == "__main__":
    main()
