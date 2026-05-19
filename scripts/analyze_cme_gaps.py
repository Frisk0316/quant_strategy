"""Analyze weekend CME BTC futures gap-fill statistics."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

import click
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from backtesting.data_loader import load_candles
from okx_quant.core.config import load_config
from okx_quant.data.external_store import ExternalDataStore


def detect_weekend_gaps(
    cme_df: pd.DataFrame,
    *,
    min_gap_bps: float = 10.0,
    max_fill_days: int = 5,
    exclude_roll_days: bool = True,
) -> pd.DataFrame:
    """Detect Friday-close to Sunday/Monday-open gaps and whether they filled."""
    columns = [
        "prev_close_at", "open_at", "prev_close", "gap_open", "gap_bps",
        "direction", "is_roll_day", "filled", "filled_at", "time_to_fill_days",
    ]
    bars = _normalize_cme_bars(cme_df)
    if bars.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict] = []
    for idx in range(1, len(bars)):
        prev = bars.iloc[idx - 1]
        cur = bars.iloc[idx]
        prev_ts = pd.Timestamp(prev["ts"])
        cur_ts = pd.Timestamp(cur["ts"])
        if not _is_weekend_reopen(prev_ts, cur_ts):
            continue
        roll_pair = bool(prev.get("is_roll_day", False) or cur.get("is_roll_day", False))
        if roll_pair and exclude_roll_days:
            continue
        prev_close = float(prev["close"])
        gap_open = float(cur["open"])
        if prev_close <= 0 or gap_open <= 0:
            continue
        gap_bps = abs(gap_open - prev_close) / prev_close * 10_000.0
        if gap_bps < min_gap_bps:
            continue
        direction = "up" if gap_open > prev_close else "down"
        search = bars.iloc[idx: idx + max_fill_days + 1]
        filled_at = None
        if direction == "up":
            hits = search[search["low"].astype(float) <= prev_close]
        else:
            hits = search[search["high"].astype(float) >= prev_close]
        if not hits.empty:
            filled_at = pd.Timestamp(hits.iloc[0]["ts"])
        rows.append({
            "prev_close_at": prev_ts.isoformat(),
            "open_at": cur_ts.isoformat(),
            "prev_close": prev_close,
            "gap_open": gap_open,
            "gap_bps": gap_bps,
            "direction": direction,
            "is_roll_day": roll_pair,
            "filled": filled_at is not None,
            "filled_at": filled_at.isoformat() if filled_at is not None else None,
            "time_to_fill_days": (
                (filled_at - cur_ts).total_seconds() / 86400.0
                if filled_at is not None else None
            ),
        })
    return pd.DataFrame(rows, columns=columns)


def summarize_gaps(
    gaps: pd.DataFrame,
    *,
    thresholds: Iterable[float] = (10, 25, 50, 100),
    exclude_roll_days: bool = True,
) -> dict:
    """Summarize fill probability and time-to-fill by threshold bucket."""
    if exclude_roll_days and not gaps.empty and "is_roll_day" in gaps.columns:
        gaps = gaps[~gaps["is_roll_day"].astype(bool)].copy()
    if gaps.empty:
        return {
            "gap_count": 0,
            "fill_probability": None,
            "median_time_to_fill_days": None,
            "thresholds": [],
        }
    summary = {
        "gap_count": int(len(gaps)),
        "fill_probability": float(gaps["filled"].mean()),
        "median_time_to_fill_days": _optional_float(gaps.loc[gaps["filled"], "time_to_fill_days"].median()),
        "thresholds": [],
    }
    for threshold in thresholds:
        subset = gaps[gaps["gap_bps"] >= float(threshold)]
        summary["thresholds"].append({
            "min_gap_bps": float(threshold),
            "gap_count": int(len(subset)),
            "fill_probability": (
                float(subset["filled"].mean()) if not subset.empty else None
            ),
            "median_time_to_fill_days": (
                _optional_float(subset.loc[subset["filled"], "time_to_fill_days"].median())
                if not subset.empty else None
            ),
        })
    return summary


def time_to_fill_distribution(
    gaps: pd.DataFrame,
    *,
    buckets_days: Iterable[float] = (1, 2, 3, 5),
) -> dict:
    """Bucket filled gaps by time-to-fill in days and count unfilled gaps."""
    if gaps.empty:
        return {"filled_count": 0, "unfilled_count": 0, "buckets": []}
    filled = gaps[gaps["filled"].astype(bool)].copy()
    out = {
        "filled_count": int(len(filled)),
        "unfilled_count": int((~gaps["filled"].astype(bool)).sum()),
        "buckets": [],
    }
    previous = 0.0
    for bucket in buckets_days:
        bucket = float(bucket)
        lower_mask = (
            filled["time_to_fill_days"].astype(float) >= previous
            if previous == 0.0
            else filled["time_to_fill_days"].astype(float) > previous
        )
        count = int(
            (lower_mask & (filled["time_to_fill_days"].astype(float) <= bucket)).sum()
        )
        out["buckets"].append({
            "label": f"{'[' if previous == 0.0 else '('}{previous:g}, {bucket:g}] days",
            "min_days_exclusive": None if previous == 0.0 else previous,
            "max_days_inclusive": bucket,
            "count": count,
            "pct_of_filled": _ratio(count, len(filled)),
            "pct_of_all": _ratio(count, len(gaps)),
        })
        previous = bucket
    tail_count = int((filled["time_to_fill_days"].astype(float) > previous).sum())
    out["buckets"].append({
        "label": f">{previous:g} days",
        "min_days_exclusive": previous,
        "max_days_inclusive": None,
        "count": tail_count,
        "pct_of_filled": _ratio(tail_count, len(filled)),
        "pct_of_all": _ratio(tail_count, len(gaps)),
    })
    return out


def simulate_reverse_gap_trades(
    gaps: pd.DataFrame,
    okx_candles: pd.DataFrame,
    *,
    max_hold_days: int = 5,
    fee_bps_per_side: float = 5.0,
    slippage_bps_per_side: float = 1.0,
    entry_lag_hours: float = 0.0,
) -> pd.DataFrame:
    """Simulate one reverse OKX trade for every detected CME gap.

    Up CME gap -> short OKX; down CME gap -> long OKX. The target is based on
    OKX entry anchor +/- the CME gap percentage, not the absolute CME price.
    """
    columns = [
        "open_at", "direction", "side", "gap_bps", "entry_ts", "entry_price",
        "target_price", "exit_ts", "exit_price", "exit_reason", "holding_hours",
        "gross_return", "cost_return", "net_return",
    ]
    if gaps.empty or okx_candles.empty:
        return pd.DataFrame(columns=columns)

    candles = _normalize_okx_candles(okx_candles)
    if candles.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict] = []
    total_cost = 2.0 * (float(fee_bps_per_side) + float(slippage_bps_per_side)) / 10_000.0
    for gap in gaps.itertuples(index=False):
        open_at = pd.Timestamp(gap.open_at)
        entry_after = open_at + pd.Timedelta(hours=float(entry_lag_hours))
        future = candles[candles["ts"] >= entry_after]
        if future.empty:
            continue
        entry = future.iloc[0]
        entry_ts = pd.Timestamp(entry["ts"])
        entry_price = float(entry["open"])
        if entry_price <= 0:
            continue

        gap_bps = float(gap.gap_bps)
        gap_pct = gap_bps / 10_000.0
        is_up_gap = str(gap.direction) == "up"
        side = "short" if is_up_gap else "long"
        target_price = entry_price * (1.0 - gap_pct if is_up_gap else 1.0 + gap_pct)
        deadline = entry_ts + pd.Timedelta(days=int(max_hold_days))
        window = candles[(candles["ts"] >= entry_ts) & (candles["ts"] <= deadline)]
        if window.empty:
            continue

        exit_ts: pd.Timestamp | None = None
        exit_price = target_price
        exit_reason = "target_fill"
        if is_up_gap:
            hits = window[window["low"].astype(float) <= target_price]
        else:
            hits = window[window["high"].astype(float) >= target_price]
        if not hits.empty:
            exit_ts = pd.Timestamp(hits.iloc[0]["ts"])
        else:
            last = window.iloc[-1]
            exit_ts = pd.Timestamp(last["ts"])
            exit_price = float(last["close"])
            exit_reason = "timeout"

        gross = (
            (entry_price - exit_price) / entry_price
            if side == "short"
            else (exit_price - entry_price) / entry_price
        )
        rows.append({
            "open_at": open_at.isoformat(),
            "direction": str(gap.direction),
            "side": side,
            "gap_bps": gap_bps,
            "entry_ts": entry_ts.isoformat(),
            "entry_price": entry_price,
            "target_price": float(target_price),
            "exit_ts": exit_ts.isoformat(),
            "exit_price": float(exit_price),
            "exit_reason": exit_reason,
            "holding_hours": (exit_ts - entry_ts).total_seconds() / 3600.0,
            "gross_return": float(gross),
            "cost_return": float(total_cost),
            "net_return": float(gross - total_cost),
        })
    return pd.DataFrame(rows, columns=columns)


def summarize_trades(trades: pd.DataFrame, *, annualization_days: float = 365.0) -> dict:
    """Summarize event-driven gap trades using trade and daily-return metrics."""
    if trades.empty:
        return {
            "trade_count": 0,
            "total_return": None,
            "annualized_return": None,
            "sharpe": None,
            "max_drawdown": None,
            "win_rate": None,
            "profit_factor": None,
        }
    returns = trades["net_return"].astype(float)
    equity = (1.0 + returns).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    start = pd.Timestamp(trades["entry_ts"].iloc[0])
    end = pd.Timestamp(trades["exit_ts"].iloc[-1])
    elapsed_days = max((end - start).total_seconds() / 86400.0, 1.0)
    ann_return = (1.0 + total_return) ** (float(annualization_days) / elapsed_days) - 1.0
    daily_returns = _daily_returns_from_trades(trades, start, end)
    sharpe = _sharpe(daily_returns, annualization_days=annualization_days)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    profit_factor = (
        float(wins.sum() / abs(losses.sum()))
        if abs(float(losses.sum())) > 1e-12 else None
    )
    drawdown = equity / equity.cummax() - 1.0
    return {
        "trade_count": int(len(trades)),
        "target_fill_trade_count": int((trades["exit_reason"] == "target_fill").sum()),
        "timeout_trade_count": int((trades["exit_reason"] == "timeout").sum()),
        "target_fill_rate": float((trades["exit_reason"] == "target_fill").mean()),
        "total_return": total_return,
        "annualized_return": float(ann_return),
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
        "win_rate": float((returns > 0).mean()),
        "profit_factor": profit_factor,
        "avg_return": float(returns.mean()),
        "median_return": float(returns.median()),
        "best_trade": float(returns.max()),
        "worst_trade": float(returns.min()),
        "avg_holding_hours": float(trades["holding_hours"].astype(float).mean()),
        "median_holding_hours": float(trades["holding_hours"].astype(float).median()),
    }


def trade_holding_distribution(
    trades: pd.DataFrame,
    *,
    buckets_hours: Iterable[float] = (1, 6, 12, 24, 48, 72, 120),
    target_only: bool = True,
) -> dict:
    """Bucket trade holding times in hours."""
    if trades.empty:
        return {"trade_count": 0, "buckets": []}
    frame = trades.copy()
    if target_only and "exit_reason" in frame.columns:
        frame = frame[frame["exit_reason"] == "target_fill"].copy()
    if frame.empty:
        return {"trade_count": 0, "buckets": []}
    out = {"trade_count": int(len(frame)), "target_only": target_only, "buckets": []}
    previous = 0.0
    holding = frame["holding_hours"].astype(float)
    for bucket in buckets_hours:
        bucket = float(bucket)
        lower_mask = holding >= previous if previous == 0.0 else holding > previous
        count = int((lower_mask & (holding <= bucket)).sum())
        out["buckets"].append({
            "label": f"{'[' if previous == 0.0 else '('}{previous:g}, {bucket:g}] hours",
            "min_hours_exclusive": None if previous == 0.0 else previous,
            "max_hours_inclusive": bucket,
            "count": count,
            "pct": _ratio(count, len(frame)),
        })
        previous = bucket
    tail_count = int((holding > previous).sum())
    out["buckets"].append({
        "label": f">{previous:g} hours",
        "min_hours_exclusive": previous,
        "max_hours_inclusive": None,
        "count": tail_count,
        "pct": _ratio(tail_count, len(frame)),
    })
    return out


def _normalize_cme_bars(cme_df: pd.DataFrame) -> pd.DataFrame:
    if cme_df.empty:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "is_roll_day"])
    frame = cme_df.copy()
    if "ts" not in frame.columns:
        if "observed_at" in frame.columns:
            frame["ts"] = pd.to_datetime(frame["observed_at"], utc=True, errors="coerce")
        else:
            frame["ts"] = pd.to_datetime(frame.index, utc=True, errors="coerce")
    if "fields" in frame.columns:
        fields_df = pd.DataFrame([
            value if isinstance(value, dict) else {}
            for value in frame["fields"]
        ])
        for col in ("open", "high", "low", "close"):
            if col not in frame.columns and col in fields_df.columns:
                frame[col] = fields_df[col]
    for col in ("open", "high", "low", "close"):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce")
    if "is_roll_day" not in frame.columns:
        if "fields" in frame.columns:
            frame["is_roll_day"] = [
                _truthy((value if isinstance(value, dict) else {}).get("is_roll_day"))
                or _truthy((value if isinstance(value, dict) else {}).get("roll_day"))
                or _truthy((value if isinstance(value, dict) else {}).get("is_roll"))
                for value in frame["fields"]
            ]
        else:
            frame["is_roll_day"] = False
    frame["is_roll_day"] = frame["is_roll_day"].apply(_truthy)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    return frame.dropna(subset=["ts", "open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)


def _normalize_okx_candles(candles: pd.DataFrame) -> pd.DataFrame:
    if candles.empty:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close"])
    frame = candles.copy()
    if "ts" not in frame.columns:
        frame["ts"] = pd.to_datetime(frame.index, utc=True, errors="coerce")
        frame = frame.reset_index(drop=True)
    else:
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close"):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce")
    return frame.dropna(subset=["ts", "open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)


def _optional_float(value) -> Optional[float]:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ratio(count: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return float(count) / float(total)


def _daily_returns_from_trades(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    index = pd.date_range(start.normalize(), end.normalize(), freq="1D", tz="UTC")
    if len(index) == 0:
        return pd.Series(dtype=float)
    daily = pd.Series(0.0, index=index)
    for trade in trades.itertuples(index=False):
        exit_day = pd.Timestamp(trade.exit_ts).tz_convert("UTC").normalize()
        if exit_day in daily.index:
            daily.loc[exit_day] += float(trade.net_return)
    return daily


def _sharpe(returns: pd.Series, *, annualization_days: float = 365.0) -> Optional[float]:
    if returns.empty:
        return None
    std = float(returns.std(ddof=1))
    if std <= 1e-12:
        return None
    return float((returns.mean() / std) * (annualization_days ** 0.5))


def _is_weekend_reopen(prev_ts: pd.Timestamp, cur_ts: pd.Timestamp) -> bool:
    gap_days = (cur_ts.date() - prev_ts.date()).days
    if prev_ts.weekday() != 4 or gap_days < 2:
        return False
    # Most official daily CME sources label Sunday evening Globex as Monday.
    # Sunday is kept for source compatibility; Tue/Wed covers US long weekends.
    return cur_ts.weekday() in {6, 0, 1, 2}


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


async def _load_from_db(dataset_id: str, start: Optional[datetime], end: Optional[datetime], settings: str) -> pd.DataFrame:
    cfg = load_config(settings_path=settings, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        raise click.ClickException("storage.timescale_dsn is not set")
    async with await ExternalDataStore.from_dsn(dsn, min_size=1, max_size=2) as store:
        return await store.get_observations(dataset_id, start=start, end=end)


def _load_okx_candles(
    *,
    csv_path: Optional[str],
    symbol: str,
    bar: str,
    data_dir: str,
    backend: str,
    settings: str,
    start: Optional[str],
    end: Optional[str],
) -> pd.DataFrame:
    if csv_path:
        return pd.read_csv(csv_path)
    cfg = load_config(settings_path=settings, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    return load_candles(
        symbol,
        bar=bar,
        data_dir=data_dir,
        start=start,
        end=end,
        backend=backend,
        dsn=dsn,
    )


def _research_status(
    source: pd.DataFrame,
    okx: pd.DataFrame,
    gaps: pd.DataFrame,
    cme_error: Optional[str],
    okx_error: Optional[str],
) -> dict:
    if cme_error:
        return {
            "status": "blocked",
            "reason": "cme_load_error",
            "detail": cme_error,
            "next_action": "Run DB migration/init and ingest CME observations before interpreting gap statistics.",
        }
    if source.empty:
        return {
            "status": "blocked",
            "reason": "missing_cme_data",
            "detail": "No CME observations were loaded for the requested dataset/range.",
            "next_action": (
                "Configure CME_BTC1_DATASET_CODE and NASDAQ_DATA_LINK_API_KEY, "
                "ingest cme_btc1_continuous, or pass --csv with CME OHLC data."
            ),
        }
    if okx_error:
        return {
            "status": "blocked",
            "reason": "okx_load_error",
            "detail": okx_error,
            "next_action": "Load OKX candles for the same research window or pass --okx-csv.",
        }
    if okx.empty:
        return {
            "status": "blocked",
            "reason": "missing_okx_data",
            "detail": "No OKX candles were loaded for the requested symbol/range.",
            "next_action": "Backfill OKX candles or pass --okx-csv.",
        }
    if gaps.empty:
        return {
            "status": "ok_no_gaps",
            "reason": "no_gaps_detected",
            "detail": "CME and OKX data loaded, but no gaps matched the current threshold/filter settings.",
            "next_action": "Review min_gap_bps, date range, roll-day filters, and source date conventions.",
        }
    return {
        "status": "ok",
        "reason": None,
        "detail": "Gap statistics and reverse-trade metrics are available for research use.",
        "next_action": None,
    }


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


@click.command()
@click.option("--dataset", default="cme_btc1_continuous", show_default=True)
@click.option("--csv", "csv_path", default=None, help="Optional CSV with ts/open/high/low/close columns")
@click.option("--okx-csv", default=None, help="Optional OKX candle CSV for trade simulation")
@click.option("--okx-symbol", default="BTC-USDT-SWAP", show_default=True)
@click.option("--okx-bar", default="1H", show_default=True)
@click.option("--data-dir", default="data/ticks", show_default=True)
@click.option("--okx-backend", default="parquet", show_default=True, type=click.Choice(["parquet", "postgres", "market"]))
@click.option("--start", default=None)
@click.option("--end", default=None)
@click.option("--min-gap-bps", default=10.0, show_default=True, type=float)
@click.option("--max-fill-days", default=5, show_default=True, type=int)
@click.option("--fee-bps-per-side", default=5.0, show_default=True, type=float)
@click.option("--slippage-bps-per-side", default=1.0, show_default=True, type=float)
@click.option("--entry-lag-hours", default=0.0, show_default=True, type=float)
@click.option("--include-roll-days", is_flag=True, help="Include rows flagged as contract roll days")
@click.option("--settings", default="config/settings.yaml", show_default=True)
@click.option("--output", default=None, help="Write JSON summary to this path")
def cli(
    dataset: str,
    csv_path: Optional[str],
    okx_csv: Optional[str],
    okx_symbol: str,
    okx_bar: str,
    data_dir: str,
    okx_backend: str,
    start: Optional[str],
    end: Optional[str],
    min_gap_bps: float,
    max_fill_days: int,
    fee_bps_per_side: float,
    slippage_bps_per_side: float,
    entry_lag_hours: float,
    include_roll_days: bool,
    settings: str,
    output: Optional[str],
) -> None:
    start_dt = _parse_dt(start)
    end_dt = _parse_dt(end)
    if csv_path:
        source = pd.read_csv(csv_path)
        cme_error = None
    else:
        try:
            source = asyncio.run(_load_from_db(dataset, start_dt, end_dt, settings))
            cme_error = None
        except Exception as exc:
            source = pd.DataFrame()
            cme_error = str(exc)
    gaps = detect_weekend_gaps(
        source,
        min_gap_bps=min_gap_bps,
        max_fill_days=max_fill_days,
        exclude_roll_days=not include_roll_days,
    )
    try:
        okx = _load_okx_candles(
            csv_path=okx_csv,
            symbol=okx_symbol,
            bar=okx_bar,
            data_dir=data_dir,
            backend=okx_backend,
            settings=settings,
            start=start,
            end=end,
        )
    except Exception as exc:
        okx = pd.DataFrame()
        okx_error = str(exc)
    else:
        okx_error = None
    trades = simulate_reverse_gap_trades(
        gaps,
        okx,
        max_hold_days=max_fill_days,
        fee_bps_per_side=fee_bps_per_side,
        slippage_bps_per_side=slippage_bps_per_side,
        entry_lag_hours=entry_lag_hours,
    )
    payload = {
        "dataset_id": dataset,
        "min_gap_bps": min_gap_bps,
        "max_fill_days": max_fill_days,
        "exclude_roll_days": not include_roll_days,
        "okx_symbol": okx_symbol,
        "okx_bar": okx_bar,
        "fee_bps_per_side": fee_bps_per_side,
        "slippage_bps_per_side": slippage_bps_per_side,
        "entry_lag_hours": entry_lag_hours,
        "summary": summarize_gaps(gaps, exclude_roll_days=not include_roll_days),
        "time_to_fill_distribution": time_to_fill_distribution(gaps),
        "trade_summary": summarize_trades(trades),
        "trade_holding_distribution": trade_holding_distribution(trades),
        "research_status": _research_status(source, okx, gaps, cme_error, okx_error),
        "data_status": {
            "cme_rows": int(len(source)),
            "cme_error": cme_error,
            "gap_count": int(len(gaps)),
            "okx_rows": int(len(okx)),
            "okx_error": okx_error,
        },
        "gaps": gaps.to_dict(orient="records"),
        "trades": trades.to_dict(orient="records"),
    }
    text = json.dumps(_json_safe(payload), indent=2, allow_nan=False)
    if output:
        Path(output).write_text(text, encoding="utf-8")
        click.echo(f"Wrote {output}")
    else:
        click.echo(text)


if __name__ == "__main__":
    cli()
