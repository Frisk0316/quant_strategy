"""
CLI for the OHLCV Rotation Strategy backtest.

Usage (parquet):
    python scripts/backtest_ohlcv_rotation.py \\
        --backend parquet \\
        --data-dir data/ticks \\
        --bar 1m \\
        --start 2024-01-01 --end 2026-05-11 \\
        --universe BTC-USDT-SWAP ETH-USDT-SWAP SOL-USDT-SWAP \\
        --benchmark BTC-USDT-SWAP

Usage (postgres):
    python scripts/backtest_ohlcv_rotation.py \\
        --backend postgres \\
        --dsn "$TIMESCALE_DSN" \\
        --bar 1m \\
        --start 2024-01-01 --end 2026-05-11 \\
        --universe BTC-USDT-SWAP ETH-USDT-SWAP SOL-USDT-SWAP XRP-USDT-SWAP DOGE-USDT-SWAP BNB-USDT-SWAP \\
        --benchmark BTC-USDT-SWAP \\
        --rebalance-minutes 60 \\
        --top-k 3 --rank-exit-buffer 6 \\
        --fee-bps 2 --slippage-bps 2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "backtesting"))
sys.path.insert(0, str(PROJECT_ROOT))

from data_loader import load_candles
from ohlcv_rotation_backtest import run_ohlcv_rotation_backtest
from okx_quant.strategies.ohlcv_rotation import OHLCVRotationParams


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OHLCV Rotation Strategy backtest")

    parser.add_argument("--backend", choices=["parquet", "postgres", "market"], default="parquet")
    parser.add_argument("--dsn", default=None, help="PostgreSQL DSN (required for postgres/market backend)")
    parser.add_argument("--exchange", default=None,
                        choices=["binance", "okx", "bybit", "coinbase", "kraken"],
                        help="When set, load from market_klines filtered by this exchange (forces backend=market)")
    parser.add_argument("--data-dir", default="data/ticks")
    parser.add_argument("--bar", default="1m")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--universe", nargs="+", required=True)
    parser.add_argument("--benchmark", default="BTC-USDT-SWAP")
    parser.add_argument("--rebalance-minutes", type=int, default=60)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--rank-exit-buffer", type=int, default=6)
    parser.add_argument(
        "--fill-all-signals",
        action="store_true",
        help="Research-only: ignore top-k/position caps and hold every instrument passing entry filters",
    )
    parser.add_argument("--lookback-fast", type=int, default=60)
    parser.add_argument("--lookback-slow", type=int, default=240)
    parser.add_argument("--volume-z-window", type=int, default=60)
    parser.add_argument("--realized-vol-window", type=int, default=240)
    parser.add_argument("--breakout-window", type=int, default=120)
    parser.add_argument("--ema-window", type=int, default=60)
    parser.add_argument("--benchmark-ema-window", type=int, default=240)
    parser.add_argument("--atr-window", type=int, default=60)
    parser.add_argument(
        "--min-volume-z",
        type=float,
        default=1.0,
        help=(
            "Diagnostic volume-z threshold reported in backtest metrics. "
            "Not a hard entry filter; volume affects selection via composite score weight. "
            "Controls the vol_filter_pass_pct diagnostic metric."
        ),
    )
    parser.add_argument("--atr-stop-multiple", type=float, default=2.0)
    parser.add_argument("--max-holding-minutes", type=int, default=480)
    parser.add_argument("--max-position-weight", type=float, default=0.35)
    parser.add_argument("--fee-bps", type=float, default=2.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--initial-equity", type=float, default=5000.0)
    parser.add_argument("--output-dir", default="results/ohlcv_rotation")

    return parser.parse_args()


def _utc_fields(value):
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return int(ts.timestamp() * 1000), ts.isoformat().replace("+00:00", "Z")


def _write_price_series_artifact(out_dir: Path, dfs: dict[str, pd.DataFrame]) -> None:
    rows = []
    for inst_id, df in dfs.items():
        if df is None or df.empty:
            continue
        for ts_value, row in df.sort_index().iterrows():
            ts_ms, dt = _utc_fields(ts_value)
            rows.append({
                "ts": ts_ms,
                "datetime": dt,
                "inst_id": inst_id,
                "open": float(row.get("open", np.nan)),
                "high": float(row.get("high", np.nan)),
                "low": float(row.get("low", np.nan)),
                "close": float(row.get("close", np.nan)),
                "vol": float(row.get("vol", row.get("volume", 0.0))),
            })
    pd.DataFrame(rows, columns=["ts", "datetime", "inst_id", "open", "high", "low", "close", "vol"]).to_csv(
        out_dir / "price_series.csv",
        index=False,
    )


def _write_signal_artifact(
    out_dir: Path,
    target_weights: pd.DataFrame,
    dfs: dict[str, pd.DataFrame],
) -> None:
    close = pd.DataFrame({inst: df["close"] for inst, df in dfs.items() if df is not None and not df.empty})
    weights = target_weights.sort_index()
    aligned_close = close.reindex(weights.index, method="ffill") if not close.empty else pd.DataFrame()
    prev = pd.Series(0.0, index=weights.columns)
    rows = []
    for ts_value, curr in weights.iterrows():
        ts_ms, dt = _utc_fields(ts_value)
        for inst_id in weights.columns:
            before = float(prev.get(inst_id, 0.0) or 0.0)
            after = float(curr.get(inst_id, 0.0) or 0.0)
            side = ""
            if before <= 0.0 and after > 0.0:
                side = "buy"
            elif before > 0.0 and after <= 0.0:
                side = "sell"
            if not side:
                continue
            fair_value = np.nan
            if not aligned_close.empty and ts_value in aligned_close.index and inst_id in aligned_close.columns:
                fair_value = float(aligned_close.loc[ts_value, inst_id])
            rows.append({
                "ts": ts_ms,
                "datetime": dt,
                "strategy": "ohlcv_rotation",
                "inst_id": inst_id,
                "side": side,
                "fair_value": fair_value,
            })
        prev = curr
    pd.DataFrame(rows, columns=["ts", "datetime", "strategy", "inst_id", "side", "fair_value"]).to_csv(
        out_dir / "signals.csv",
        index=False,
    )


def main() -> None:
    args = parse_args()

    # When --exchange is provided we MUST query market_klines (the only layer
    # that retains per-exchange rows). canonical_candles is the merged view.
    if args.exchange:
        args.backend = "market"
    if args.backend in {"postgres", "market"} and not args.dsn:
        sys.exit(f"Error: --dsn is required when --backend={args.backend}")

    # Ensure benchmark is in universe
    universe = list(dict.fromkeys(args.universe))  # preserve order, deduplicate
    if args.benchmark not in universe:
        universe = [args.benchmark] + universe

    print(f"Loading {len(universe)} instruments ({args.bar} bars) …")
    dfs: dict = {}
    for inst in universe:
        try:
            df = load_candles(
                inst_id=inst,
                bar=args.bar,
                data_dir=args.data_dir,
                start=args.start,
                end=args.end,
                backend=args.backend,
                dsn=args.dsn,
                exchange=args.exchange,
            )
        except FileNotFoundError as exc:
            print(f"  WARNING: {exc} — skipping {inst}")
            continue
        # load_candles can legitimately return an empty frame when the bar/window
        # has no rows (e.g. parquet thin-mirror, or 1m→bar derivation yields none).
        # Skip it instead of indexing df.index[0] into an IndexError.
        if df is None or df.empty:
            print(f"  WARNING: no {args.bar} data for {inst} in [{args.start} → {args.end}] — skipping")
            continue
        dfs[inst] = df
        print(f"  {inst}: {len(df):,} bars  {df.index[0]} → {df.index[-1]}")

    if args.benchmark not in dfs:
        sys.exit(f"Error: benchmark '{args.benchmark}' could not be loaded. Aborting.")

    params = OHLCVRotationParams(
        universe=list(dfs.keys()),
        benchmark_inst_id=args.benchmark,
        bar=args.bar,
        rebalance_minutes=args.rebalance_minutes,
        top_k=args.top_k,
        rank_exit_buffer=args.rank_exit_buffer,
        fill_all_signals=args.fill_all_signals,
        lookback_fast_minutes=args.lookback_fast,
        lookback_slow_minutes=args.lookback_slow,
        volume_z_window_minutes=args.volume_z_window,
        realized_vol_window_minutes=args.realized_vol_window,
        breakout_window_minutes=args.breakout_window,
        ema_window_minutes=args.ema_window,
        benchmark_ema_window_minutes=args.benchmark_ema_window,
        atr_window_minutes=args.atr_window,
        min_volume_z=args.min_volume_z,
        atr_stop_multiple=args.atr_stop_multiple,
        max_holding_minutes=args.max_holding_minutes,
        max_position_weight=args.max_position_weight,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
    )

    print("\nRunning backtest …")
    result = run_ohlcv_rotation_backtest(dfs, params)

    # --- save outputs ---
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    import pandas as _pd

    equity_usd = result.equity_curve * args.initial_equity
    returns = equity_usd.pct_change().fillna(0.0)
    rolling_max = equity_usd.cummax()
    denominator = rolling_max.where(rolling_max != 0)
    drawdown = (equity_usd - rolling_max) / denominator
    drawdown = drawdown.fillna(0.0)

    equity_df = _pd.DataFrame({"equity": equity_usd, "drawdown": drawdown})
    equity_df.index.name = "ts"
    equity_df.to_csv(out_dir / "equity_curve.csv")

    returns_df = _pd.DataFrame({"return": returns})
    returns_df["log_return"] = np.log1p(returns)
    returns_df.index.name = "ts"
    returns_df.to_csv(out_dir / "returns.csv")

    drawdown_df = _pd.DataFrame({
        "equity": equity_usd,
        "running_max_equity": rolling_max,
        "drawdown": drawdown,
        "drawdown_pct": drawdown,
    })
    drawdown_df.index.name = "ts"
    drawdown_df.to_csv(out_dir / "drawdown.csv")

    _write_price_series_artifact(out_dir, dfs)
    _write_signal_artifact(out_dir, result.target_weights, dfs)
    result.target_weights.to_csv(out_dir / "target_weights.csv")
    result.positions.to_csv(out_dir / "positions.csv")
    result.trades.to_csv(out_dir / "trades.csv", index=False)

    # JSON-serialise metrics (handle inf/nan)
    clean_metrics: dict = {}
    for k, v in result.metrics.items():
        if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
            clean_metrics[k] = str(v)
        else:
            clean_metrics[k] = v
    with open(out_dir / "summary.json", "w") as fh:
        json.dump(clean_metrics, fh, indent=2)

    # --- print summary ---
    m = result.metrics
    print(
        f"""
╔══════════════════════════════════════════╗
║     OHLCV Rotation — Backtest Summary    ║
╠══════════════════════════════════════════╣
║  Period      {str(args.start):>10} → {str(args.end):>10}  ║
║  Universe    {len(dfs)} instruments                  ║
║  Bar         {args.bar:<5}  Rebalance: {args.rebalance_minutes}m             ║
╠══════════════════════════════════════════╣
║  Total return          {m['total_return']:>+10.2%}        ║
║  Annualised return     {m['annualized_return']:>+10.2%}        ║
║  Annualised vol        {m['annualized_volatility']:>10.2%}        ║
║  Sharpe ratio          {m['sharpe']:>10.3f}        ║
║  Max drawdown          {m['max_drawdown']:>+10.2%}        ║
║  Calmar ratio          {m['calmar']:>10.3f}        ║
╠══════════════════════════════════════════╣
║  Trades                {m['number_of_trades']:>10}        ║
║  Win rate              {m['win_rate']:>10.1%}        ║
║  Profit factor         {m['profit_factor']:>10.3f}        ║
║  Avg holding (min)     {m['average_holding_minutes']:>10.1f}        ║
║  Avg turnover          {m['average_turnover']:>10.4f}        ║
╚══════════════════════════════════════════╝
"""
    )
    print(f"Outputs written to: {out_dir.resolve()}/")


if __name__ == "__main__":
    main()
