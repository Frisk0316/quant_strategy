"""
CLI for the daily winner validation strategy.

The script requests 1D candles from the existing data loader. When the DB or
Parquet layer only has 1m candles, data_loader rolls those candles up to 1D.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backtesting"))

from backtesting.daily_winner_backtest import DailyWinnerParams, run_daily_winner_backtest
from data_loader import load_candles


DEFAULT_UNIVERSE = [
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "BNB-USDT-SWAP",
    "SOL-USDT-SWAP",
    "XRP-USDT-SWAP",
    "ADA-USDT-SWAP",
    "DOGE-USDT-SWAP",
    "LINK-USDT-SWAP",
    "AVAX-USDT-SWAP",
    "DOT-USDT-SWAP",
    "LTC-USDT-SWAP",
    "SHIB-USDT-SWAP",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily winner validation backtest")
    parser.add_argument("--backend", choices=["parquet", "postgres", "market"], default="postgres")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN for postgres/market backends")
    parser.add_argument(
        "--exchange",
        choices=["binance", "okx", "bybit", "coinbase", "kraken"],
        default=None,
        help="Exchange filter for backend=market",
    )
    parser.add_argument("--data-dir", default="data/ticks")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--universe", nargs="+", default=DEFAULT_UNIVERSE)
    parser.add_argument("--fee-bps", type=float, default=2.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--initial-equity", type=float, default=5000.0)
    parser.add_argument("--output-dir", default="results/daily_winner")
    parser.add_argument(
        "--fail-if-skipped",
        action="store_true",
        help="Exit non-zero if any expected daily trade is skipped.",
    )
    return parser.parse_args()


def _default_dsn() -> str | None:
    return (
        os.getenv("TIMESCALE_DSN")
        or os.getenv("DATABASE_URL")
        or "postgresql://quant:changeme@127.0.0.1:5432/quant"
    )


def _json_default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _clean_metrics(metrics: dict) -> dict:
    clean = {}
    for key, value in metrics.items():
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            clean[key] = str(value)
        else:
            clean[key] = value
    return clean


def main() -> None:
    args = parse_args()
    dsn = args.dsn or (_default_dsn() if args.backend in {"postgres", "market"} else None)
    if args.backend in {"postgres", "market"} and not dsn:
        sys.exit("Error: --dsn is required for postgres/market backends")

    universe = list(dict.fromkeys(args.universe))
    print(f"Loading {len(universe)} instruments as 1D candles via {args.backend}")
    print("Note: if native 1D candles are absent, the loader derives them from 1m OHLCV.")

    dfs: dict = {}
    for inst in universe:
        try:
            df = load_candles(
                inst_id=inst,
                bar="1D",
                data_dir=args.data_dir,
                start=args.start,
                end=args.end,
                backend=args.backend,
                dsn=dsn,
                exchange=args.exchange,
            )
        except FileNotFoundError as exc:
            print(f"  WARNING: {inst}: {exc}")
            continue
        if df.empty:
            print(f"  WARNING: {inst}: no rows loaded")
            continue
        dfs[inst] = df
        print(f"  {inst}: {len(df):,} daily bars  {df.index[0]} -> {df.index[-1]}")

    if len(dfs) < 2:
        sys.exit("Error: need at least two instruments with daily OHLCV")

    params = DailyWinnerParams(
        universe=list(dfs.keys()),
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        initial_equity=args.initial_equity,
    )
    result = run_daily_winner_backtest(dfs, params)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    result.equity_curve.to_frame("equity").to_csv(out_dir / "equity_curve.csv")
    result.daily_returns.to_frame("return").to_csv(out_dir / "returns.csv")
    result.target_weights.to_csv(out_dir / "target_weights.csv")
    result.positions.to_csv(out_dir / "positions.csv")
    result.trades.to_csv(out_dir / "trades.csv", index=False)

    summary = _clean_metrics(
        {
            **result.metrics,
            "backend": args.backend,
            "bar_requested": "1D",
            "data_note": "1D loaded directly when present; otherwise derived from 1m OHLCV",
            "start": args.start,
            "end": args.end,
        }
    )
    with open(out_dir / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=_json_default)

    print(
        "\nDaily winner summary\n"
        f"  Period: {args.start} -> {args.end or 'latest'}\n"
        f"  Universe: {len(dfs)} instruments\n"
        f"  Trades: {result.metrics['number_of_trades']} / {result.metrics['expected_trade_days']} expected days\n"
        f"  Skipped days: {result.metrics['skipped_trade_days']}\n"
        f"  Total return: {result.metrics['total_return']:+.2%}\n"
        f"  Sharpe: {result.metrics['sharpe']:.3f}\n"
        f"  Outputs: {out_dir.resolve()}"
    )

    if args.fail_if_skipped and result.metrics["skipped_trade_days"] > 0:
        sys.exit("Error: daily winner skipped at least one expected trading day")


if __name__ == "__main__":
    main()
