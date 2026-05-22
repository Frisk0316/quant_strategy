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

from backtesting.replay import run_replay_backtest, run_replay_validations
from backtesting.research_controls import (
    apply_research_risk_overrides,
    summarize_risk_events,
)
from okx_quant.core.config import load_config
from okx_quant.core.symbols import normalize_spot_symbol, normalize_swap_symbol

BAR_PERIODS = {
    "1m": 525600, "3m": 175200, "5m": 105120, "15m": 35040,
    "30m": 17520, "1H": 8760, "2H": 4380, "4H": 2190, "1D": 365,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", action="append", required=True,
                        choices=[
                            "obi_market_maker",
                            "as_market_maker",
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
                        help="Instrument symbol for single/multi-symbol market-making strategies")
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
    parser.add_argument("--risk-overrides", default=None,
                        help="JSON object with research-only risk overrides for this replay")
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

    if args.symbol:
        args.symbol = [normalize_swap_symbol(symbol) for symbol in args.symbol]
        if "obi_market_maker" in args.strategy:
            cfg.strategies.obi_market_maker.symbols = args.symbol
        if "as_market_maker" in args.strategy:
            cfg.strategies.as_market_maker.symbols = args.symbol
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

    print("PROGRESS:20:Running replay backtest", flush=True)
    result = run_replay_backtest(
        strategy_names=args.strategy,
        cfg=cfg,
        data_dir=args.data_dir,
        start=args.start,
        end=args.end,
        bar=args.bar,
        periods=args.periods or BAR_PERIODS.get(args.bar, 365 * 24),
        liquidate_on_end=args.liquidate_on_end,
    )
    result.validation["risk_summary"] = summarize_risk_events(result.risk_event_log)
    if applied_risk_overrides:
        result.validation["research_risk_overrides"] = applied_risk_overrides
    if args.save_artifacts and args.validate:
        stage = f"Running replay validation ({args.validate}) and saving artifacts"
    elif args.save_artifacts:
        stage = "Saving replay artifacts"
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

    if args.save_artifacts:
        from backtesting.artifacts import save_backtest_artifacts
        output_dir = str(PROJECT_ROOT / args.output_dir) if not Path(args.output_dir).is_absolute() else args.output_dir
        validation_results = None
        if args.validate:
            print(f"Running replay validation: {args.validate}")

            def _print_validation_progress(update: dict) -> None:
                pct = int(update.get("progress", 85))
                message = str(update.get("message") or "Running replay validation")
                print(f"PROGRESS:{pct}:{message}", flush=True)

            validation_results = run_replay_validations(
                strategy_names=args.strategy,
                cfg=cfg,
                data_dir=args.data_dir,
                start=args.start,
                end=args.end,
                bar=args.bar,
                periods=args.periods or BAR_PERIODS.get(args.bar, 365 * 24),
                mode=args.validate,
                liquidate_on_end=args.liquidate_on_end,
                progress_callback=_print_validation_progress,
            )
            print("PROGRESS:99:Saving replay artifacts", flush=True)
        run_dir = save_backtest_artifacts(
            result=result,
            cfg=cfg,
            args=args,
            output_dir=output_dir,
            run_id=args.run_id,
            strategy_names=args.strategy,
            start=args.start,
            end=args.end,
            bar=args.bar,
            validation_results=validation_results,
        )
        print(f"Saved backtest artifacts to {run_dir}")


if __name__ == "__main__":
    main()
