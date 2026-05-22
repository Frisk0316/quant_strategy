"""
Backtest artifacts exporter.

Writes a self-contained results/<run_id>/ directory containing JSON summaries
and CSV tables for every aspect of a replay backtest run.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from loguru import logger


# ---------------------------------------------------------------------------
# Fixed column schemas — ensures every CSV has the correct header even when
# the corresponding DataFrame is empty.
# ---------------------------------------------------------------------------

ORDER_COLUMNS = [
    "ts", "datetime", "strategy", "inst_id", "side", "ord_type",
    "px", "sz", "notional_usd", "td_mode", "cl_ord_id", "state", "reason", "metadata",
]

FILL_COLUMNS = [
    "ts", "datetime", "strategy", "inst_id", "side", "fill_px", "fill_sz",
    "fee", "fee_ccy", "state", "cl_ord_id", "ord_id", "notional_usd", "fee_rate",
    "ct_val", "remaining_sz", "execution_model", "metadata",
]

TRADE_COLUMNS = [
    "ts", "datetime", "strategy", "inst_id", "side", "fill_px", "fill_sz",
    "notional_usd", "fee", "fee_ccy",
    "size_before", "size_after", "avg_entry_before", "avg_entry_after",
    "position_notional_before", "position_notional_after",
    "realized_pnl", "net_realized_pnl", "unrealized_pnl_after",
    "cash_before", "cash_after", "equity_after",
    "is_opening", "is_reducing", "is_closing", "is_reversing",
    "metadata",
]

POSITION_COLUMNS = [
    "ts", "datetime", "strategy", "inst_id", "size", "avg_entry",
    "mark_price", "notional", "unrealized_pnl", "realized_pnl",
    "net_realized_pnl", "cash", "equity", "leverage",
]

EQUITY_COLUMNS = [
    "ts", "datetime", "equity", "cash", "realized_pnl",
    "unrealized_pnl", "funding_pnl", "fee_paid", "drawdown", "return",
]

RETURN_COLUMNS = ["ts", "datetime", "return", "log_return"]

DRAWDOWN_COLUMNS = [
    "ts", "datetime", "equity", "running_max_equity", "drawdown", "drawdown_pct",
]

FUNDING_COLUMNS = [
    "ts", "datetime", "inst_id", "strategy", "funding_rate", "funding_rate_pct",
    "funding_interval_hours", "mark_price", "position_size", "position_notional",
    "funding_fee", "cash_before", "cash_after", "equity_after", "source",
]

SIGNAL_COLUMNS = [
    "ts", "datetime", "strategy", "inst_id", "side", "strength",
    "fair_value", "target_bid", "target_ask", "metadata",
]

RISK_EVENT_COLUMNS = [
    "ts", "datetime", "strategy", "inst_id", "side", "px", "sz",
    "notional_usd", "reason", "current_position", "position_limit",
    "current_equity", "metadata",
]

REJECTED_ORDER_COLUMNS = [
    "ts", "datetime", "strategy", "inst_id", "side", "px", "sz",
    "cl_ord_id", "reason", "best_bid", "best_ask", "metadata",
]

CANCEL_LOG_COLUMNS = [
    "ts", "datetime", "inst_id", "cl_ord_id", "state", "effective_ts", "reason",
]

EXECUTION_MARKER_COLUMNS = [
    "ts", "datetime", "inst_id", "strategy", "side", "price", "qty", "fee",
    "notional_usd", "net_realized_pnl", "day_pnl", "position_after", "marker_position", "marker_shape", "marker_text",
]

PRICE_SERIES_COLUMNS = ["ts", "datetime", "inst_id", "open", "high", "low", "close", "vol"]

INDICATOR_SERIES_COLUMNS = [
    "ts", "datetime", "inst_id", "strategy", "close",
    "fast_value", "slow_value",
    "macd", "macd_signal", "macd_histogram",
    "warmup_source",
]

_TECHNICAL_STRATEGIES = {"ma_crossover", "ema_crossover", "macd_crossover"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _ts_to_datetime(ts_series: pd.Series) -> pd.Series:
    """Convert a ts column (ms or seconds integer, or datetime-like) to ISO-8601 UTC strings."""
    try:
        numeric = pd.to_numeric(ts_series, errors="coerce").dropna()
        if not numeric.empty:
            med = float(numeric.median())
            # Timestamps < 1e11 are almost certainly seconds (year ~1970–5138 in seconds
            # vs year 1970–1973 in ms). Multiply to ms so pd.to_datetime unit="ms" works.
            if 0 < med < 1e11:
                ts_series = pd.to_numeric(ts_series, errors="coerce") * 1000
        converted = pd.to_datetime(ts_series, unit="ms", utc=True, errors="coerce")
        if converted.isna().all():
            converted = pd.to_datetime(ts_series, utc=True, errors="coerce")
    except Exception:
        converted = pd.to_datetime(ts_series, utc=True, errors="coerce")
    return converted.dt.strftime("%Y-%m-%dT%H:%M:%SZ").fillna("")


def _dump_metadata(val: Any) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "{}"
    if isinstance(val, dict):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str):
        return val if val.startswith("{") else json.dumps({"raw": val}, ensure_ascii=False)
    return json.dumps({"raw": str(val)}, ensure_ascii=False)


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Add any missing columns as None and reorder to match schema."""
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def _safe_float(val: Any, default: float = float("nan")) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# run_id generation
# ---------------------------------------------------------------------------

def build_run_id(
    strategy_names: list[str],
    start: Optional[str],
    end: Optional[str],
    bar: str,
    run_id: Optional[str] = None,
) -> str:
    if run_id:
        return re.sub(r'[<>:"/\\|?*]', "_", run_id)
    strat = "_".join(sorted(strategy_names)) if strategy_names else "unknown"
    start_s = (start or "nostart").replace("-", "")[:8]
    end_s = (end or "noend").replace("-", "")[:8]
    bar_s = bar.replace(":", "")
    now_s = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"replay_{strat}_{start_s}_{end_s}_{bar_s}_{now_s}"


# ---------------------------------------------------------------------------
# Individual writers
# ---------------------------------------------------------------------------

def _sanitize_floats(obj):
    """Recursively replace inf/nan with None so the output is valid JSON."""
    if isinstance(obj, float):
        import math
        return None if (math.isinf(obj) or math.isnan(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_floats(v) for v in obj]
    return obj


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(_sanitize_floats(data), indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _write_csv(path: Path, df: pd.DataFrame, columns: list[str]) -> None:
    df = df.copy()
    if "datetime" not in df.columns and "ts" in df.columns:
        df["datetime"] = _ts_to_datetime(df["ts"])
    if "metadata" in columns and "metadata" in df.columns:
        df["metadata"] = df["metadata"].apply(_dump_metadata)
    df = ensure_columns(df, columns)
    df.to_csv(path, index=False)


def _artifact_mode(dsn: Optional[str] = None) -> str:
    """Return files/db/both. Prefers explicit dsn over DATABASE_URL env var."""
    has_dsn = bool(dsn or os.environ.get("DATABASE_URL"))
    raw = os.environ.get("BACKTEST_ARTIFACT_MODE", "").strip().lower()
    if raw in {"files", "db", "both"}:
        if raw == "db" and not has_dsn:
            logger.warning("BACKTEST_ARTIFACT_MODE=db requested but no DATABASE_URL available; writing files instead")
            return "files"
        return raw
    return "db" if has_dsn else "files"


def _json_safe(value: Any) -> Any:
    import math
    if value is None:
        return None
    if isinstance(value, float) and (np.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        f = float(value)
        return None if (np.isnan(f) or math.isinf(f)) else f
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (datetime, pd.Timestamp)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if pd.isna(value) if not isinstance(value, (list, dict, tuple, set)) else False:
        return None
    return value


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return _json_safe(json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso")))


def _upsert_run_to_db(run_id: str, meta: dict, artifact_dir: Path, dsn: Optional[str] = None) -> None:
    """Best-effort: insert run summary into backtest_runs table. Non-fatal."""
    try:
        import asyncio

        import asyncpg

        dsn = dsn or os.environ.get("DATABASE_URL")
        if not dsn:
            return

        metrics = meta.get("metrics", {})
        metadata = {
            "parameters": meta.get("parameters", {}),
        }

        def _parse_date(value: Any) -> Any:
            if not value:
                return None
            try:
                return datetime.fromisoformat(str(value)[:10]).date()
            except Exception:
                return None

        async def _insert() -> None:
            conn = await asyncpg.connect(dsn)
            try:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS backtest_runs (
                        run_id          TEXT PRIMARY KEY,
                        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        strategies      TEXT[] NOT NULL DEFAULT '{}',
                        symbols         TEXT[] NOT NULL DEFAULT '{}',
                        bar             TEXT NOT NULL DEFAULT '',
                        start_date      DATE,
                        end_date        DATE,
                        artifact_dir    TEXT NOT NULL,
                        total_return    FLOAT8,
                        sharpe          FLOAT8,
                        max_drawdown    FLOAT8,
                        order_count     INT,
                        real_fill_count INT,
                        fill_rate       FLOAT8,
                        bankrupt        BOOLEAN DEFAULT FALSE,
                        metadata        JSONB DEFAULT '{}'
                    )
                    """
                )
                await conn.execute(
                    "ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'"
                )
                await conn.execute(
                    """
                    INSERT INTO backtest_runs
                      (run_id, created_at, strategies, symbols, bar, start_date, end_date,
                       artifact_dir, total_return, sharpe, max_drawdown, order_count,
                       real_fill_count, fill_rate, bankrupt, metadata)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb)
                    ON CONFLICT (run_id) DO UPDATE SET
                        created_at = EXCLUDED.created_at,
                        strategies = EXCLUDED.strategies,
                        symbols = EXCLUDED.symbols,
                        bar = EXCLUDED.bar,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        artifact_dir = EXCLUDED.artifact_dir,
                        total_return = EXCLUDED.total_return,
                        sharpe = EXCLUDED.sharpe,
                        max_drawdown = EXCLUDED.max_drawdown,
                        order_count = EXCLUDED.order_count,
                        real_fill_count = EXCLUDED.real_fill_count,
                        fill_rate = EXCLUDED.fill_rate,
                        bankrupt = EXCLUDED.bankrupt,
                        metadata = EXCLUDED.metadata
                    """,
                    run_id,
                    datetime.now(tz=timezone.utc),
                    meta.get("strategies", []),
                    meta.get("symbols", []),
                    meta.get("bar", ""),
                    _parse_date(meta.get("start")),
                    _parse_date(meta.get("end")),
                    str(artifact_dir),
                    metrics.get("total_return"),
                    metrics.get("sharpe"),
                    metrics.get("max_drawdown"),
                    metrics.get("order_count", metrics.get("submitted_order_count")),
                    metrics.get("real_fill_count", metrics.get("fill_count", metrics.get("orders_filled_count"))),
                    metrics.get("fill_rate"),
                    bool(metrics.get("bankrupt", False)),
                    json.dumps(metadata, allow_nan=False),
                )
            finally:
                await conn.close()

        asyncio.run(_insert())
    except Exception as exc:
        logger.warning("Could not upsert run {} to DB: {}", run_id, exc)


def _upsert_artifacts_to_db(run_id: str, artifacts: dict[str, Any], dsn: Optional[str] = None, mode: str = "files") -> None:
    """Best-effort: store full artifacts in backtest_artifacts JSONB rows."""
    try:
        import asyncio

        import asyncpg

        dsn = dsn or os.environ.get("DATABASE_URL")
        if not dsn or mode not in {"db", "both"}:
            return

        async def _insert() -> None:
            conn = await asyncpg.connect(dsn)
            try:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS backtest_artifacts (
                        run_id        TEXT NOT NULL REFERENCES backtest_runs(run_id) ON DELETE CASCADE,
                        artifact_type TEXT NOT NULL,
                        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        row_count     INT NOT NULL DEFAULT 0,
                        payload       JSONB NOT NULL,
                        PRIMARY KEY (run_id, artifact_type)
                    )
                    """
                )
                rows = []
                for artifact_type, payload in artifacts.items():
                    safe_payload = _json_safe(payload)
                    row_count = len(safe_payload) if isinstance(safe_payload, list) else 1
                    rows.append((
                        run_id,
                        artifact_type,
                        row_count,
                        json.dumps(safe_payload, ensure_ascii=False, default=str),
                    ))
                await conn.executemany(
                    """
                    INSERT INTO backtest_artifacts (run_id, artifact_type, row_count, payload)
                    VALUES ($1, $2, $3, $4::jsonb)
                    ON CONFLICT (run_id, artifact_type) DO UPDATE SET
                        row_count=EXCLUDED.row_count,
                        payload=EXCLUDED.payload,
                        created_at=NOW()
                    """,
                    rows,
                )
            finally:
                await conn.close()

        asyncio.run(_insert())
    except Exception as exc:
        logger.warning("Could not upsert artifacts for run {} to DB: {}", run_id, exc)


def _normalize_orders(order_log: pd.DataFrame) -> pd.DataFrame:
    if order_log.empty:
        return order_log
    df = order_log.copy()
    if "datetime" not in df.columns:
        df["datetime"] = _ts_to_datetime(df["ts"])
    if "metadata" not in df.columns:
        df["metadata"] = "{}"
    else:
        df["metadata"] = df["metadata"].apply(_dump_metadata)
    for col in ["state", "reason", "ord_type", "td_mode"]:
        if col not in df.columns:
            df[col] = None
    return df


def _normalize_fills(fill_log: pd.DataFrame) -> pd.DataFrame:
    if fill_log.empty:
        return fill_log
    df = fill_log.copy()
    if "datetime" not in df.columns:
        df["datetime"] = _ts_to_datetime(df["ts"])
    # Extract structured fields from metadata
    if "metadata" in df.columns:
        meta_series = df["metadata"].apply(
            lambda m: m if isinstance(m, dict) else {}
        )
        for field in ["fee_rate", "ct_val", "remaining_sz", "execution_model", "notional_usd"]:
            if field not in df.columns:
                df[field] = meta_series.apply(lambda m: m.get(field))
        if "notional_usd" in df.columns:
            fallback_mask = df["notional_usd"].isna() | (df["notional_usd"] == 0)
            if fallback_mask.any():
                ct_val = df.get("ct_val", pd.Series(1.0, index=df.index)).fillna(1.0)
                df.loc[fallback_mask, "notional_usd"] = (
                    df.loc[fallback_mask, "fill_px"].astype(float)
                    * df.loc[fallback_mask, "fill_sz"].astype(float)
                    * ct_val.loc[fallback_mask].astype(float)
                )
        df["metadata"] = df["metadata"].apply(_dump_metadata)
    for col in ["fee_ccy", "ord_id"]:
        if col not in df.columns:
            df[col] = None
    return df


def _build_equity_df(
    equity_curve: pd.Series,
    fill_log: pd.DataFrame,
    funding_log: pd.DataFrame,
) -> pd.DataFrame:
    if equity_curve.empty:
        return pd.DataFrame(columns=EQUITY_COLUMNS)

    eq = equity_curve.copy()
    if not isinstance(eq.index, pd.DatetimeIndex):
        idx = pd.to_datetime(eq.index, unit="ms", utc=True, errors="coerce")
        if idx.isna().all():
            idx = pd.to_datetime(eq.index, utc=True, errors="coerce")
    else:
        idx = eq.index

    df = pd.DataFrame({
        "ts": eq.index,
        "equity": eq.values.astype(float),
    })
    df["datetime"] = _ts_to_datetime(df["ts"])
    df["return"] = df["equity"].pct_change().fillna(0.0)
    running_max = df["equity"].cummax()
    df["drawdown"] = (df["equity"] - running_max) / running_max.replace(0, float("nan"))
    df["drawdown"] = df["drawdown"].fillna(0.0)

    # Aggregate fee_paid from fills
    total_fee = 0.0
    if not fill_log.empty and "fee" in fill_log.columns:
        total_fee = float(fill_log["fee"].sum())

    # Aggregate funding_pnl from funding log
    total_funding = 0.0
    if not funding_log.empty and "cashflow" in funding_log.columns:
        total_funding = float(funding_log["cashflow"].sum())

    df["cash"] = float("nan")
    df["realized_pnl"] = float("nan")
    df["unrealized_pnl"] = float("nan")
    df["funding_pnl"] = total_funding
    df["fee_paid"] = total_fee
    return df


def _build_returns_df(equity_curve: pd.Series) -> pd.DataFrame:
    if equity_curve.empty:
        return pd.DataFrame(columns=RETURN_COLUMNS)
    eq = equity_curve.values.astype(float)
    rets = pd.Series(eq).pct_change().fillna(0.0).values
    with np.errstate(divide="ignore", invalid="ignore"):
        log_rets = np.where(
            (eq[:-1] > 0) & (eq[1:] > 0),
            np.log(eq[1:] / eq[:-1]),
            float("nan"),
        )
    log_rets = np.concatenate([[float("nan")], log_rets])
    df = pd.DataFrame({
        "ts": equity_curve.index,
        "return": rets,
        "log_return": log_rets,
    })
    df["datetime"] = _ts_to_datetime(df["ts"])
    return df


def _build_drawdown_df(equity_curve: pd.Series) -> pd.DataFrame:
    if equity_curve.empty:
        return pd.DataFrame(columns=DRAWDOWN_COLUMNS)
    eq = equity_curve.values.astype(float)
    running_max = pd.Series(eq).cummax().values
    dd = eq - running_max
    dd_pct = np.where(running_max != 0, dd / running_max, 0.0)
    df = pd.DataFrame({
        "ts": equity_curve.index,
        "equity": eq,
        "running_max_equity": running_max,
        "drawdown": dd,
        "drawdown_pct": dd_pct,
    })
    df["datetime"] = _ts_to_datetime(df["ts"])
    return df


def _build_funding_df(funding_log: pd.DataFrame) -> pd.DataFrame:
    if funding_log.empty:
        return funding_log
    df = funding_log.copy()
    if "datetime" not in df.columns:
        df["datetime"] = _ts_to_datetime(df["ts"])
    col_map = {
        "rate": "funding_rate",
        "cashflow": "funding_fee",
        "notional_usd": "position_notional",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns and v not in df.columns})
    if "funding_rate" in df.columns:
        df["funding_rate_pct"] = df["funding_rate"] * 100
    for col in ["strategy", "funding_interval_hours", "source", "cash_before", "cash_after", "equity_after"]:
        if col not in df.columns:
            df[col] = None
    return df


def _build_execution_markers(fill_log: pd.DataFrame, trade_log: pd.DataFrame) -> pd.DataFrame:
    real_fills = fill_log[
        (fill_log["fill_sz"].astype(float) > 0)
        & (fill_log["state"].isin({"filled", "partially_filled"}))
    ].copy() if not fill_log.empty and "state" in fill_log.columns else pd.DataFrame()

    if real_fills.empty:
        return pd.DataFrame(columns=EXECUTION_MARKER_COLUMNS)

    real_fills["datetime"] = _ts_to_datetime(real_fills["ts"])

    # Join net_realized_pnl from trade_log where available
    net_pnl_map: dict = {}
    day_pnl_map: dict = {}
    if not trade_log.empty and "net_realized_pnl" in trade_log.columns:
        trade_with_dt = trade_log.copy()
        if "datetime" not in trade_with_dt.columns and "ts" in trade_with_dt.columns:
            trade_with_dt["datetime"] = _ts_to_datetime(trade_with_dt["ts"])
        trade_with_dt["_day"] = pd.to_datetime(
            trade_with_dt.get("datetime", pd.Series(dtype=object)),
            utc=True,
            errors="coerce",
        ).dt.strftime("%Y-%m-%d")
        for _, row in trade_with_dt.iterrows():
            key = (row.get("inst_id", ""), row.get("ts", 0))
            net_pnl_map[key] = row.get("net_realized_pnl", 0.0)
        day_group = (
            trade_with_dt.dropna(subset=["_day"])
            .groupby(["inst_id", "_day"])["net_realized_pnl"]
            .sum()
        )
        day_pnl_map = {
            (inst_id, day): pnl
            for (inst_id, day), pnl in day_group.items()
        }

    rows = []
    for _, f in real_fills.iterrows():
        side = str(f.get("side", "buy"))
        price = _safe_float(f.get("fill_px"), 0.0)
        qty = _safe_float(f.get("fill_sz"), 0.0)
        fee = _safe_float(f.get("fee"), 0.0)
        notional_usd = _safe_float(f.get("notional_usd"), abs(price * qty))
        pnl = _safe_float(
            net_pnl_map.get((f.get("inst_id", ""), f.get("ts", 0)), float("nan")),
            float("nan"),
        )
        day = pd.to_datetime(f.get("datetime", ""), utc=True, errors="coerce")
        day_key = day.strftime("%Y-%m-%d") if pd.notna(day) else ""
        day_pnl = _safe_float(
            day_pnl_map.get((f.get("inst_id", ""), day_key), float("nan")),
            float("nan"),
        )
        pnl_str = f"{pnl:.2f}" if not np.isnan(pnl) else "n/a"
        day_pnl_str = f"{day_pnl:.2f}" if not np.isnan(day_pnl) else "n/a"
        marker_position = "belowBar" if side == "buy" else "aboveBar"
        marker_shape = "arrowUp" if side == "buy" else "arrowDown"
        marker_text = (
            f"{side.upper()} {qty:.6g} @ {price:,.2f} | "
            f"Notional: {notional_usd:,.2f} USDT | "
            f"Trade PnL: {pnl_str} | Day PnL: {day_pnl_str}"
        )

        # position_after from trade_log
        pos_after = float("nan")
        if not trade_log.empty and "size_after" in trade_log.columns:
            match = trade_log[
                (trade_log.get("inst_id", pd.Series()) == f.get("inst_id", ""))
                & (trade_log.get("ts", pd.Series()) == f.get("ts", 0))
            ]
            if not match.empty:
                pos_after = _safe_float(match.iloc[0].get("size_after"), float("nan"))

        rows.append({
            "ts": f.get("ts"),
            "datetime": f.get("datetime", ""),
            "inst_id": f.get("inst_id", ""),
            "strategy": f.get("strategy", ""),
            "side": side,
            "price": price,
            "qty": qty,
            "fee": fee,
            "notional_usd": notional_usd,
            "net_realized_pnl": pnl,
            "day_pnl": day_pnl,
            "position_after": pos_after,
            "marker_position": marker_position,
            "marker_shape": marker_shape,
            "marker_text": marker_text,
        })
    return pd.DataFrame(rows)


def _build_price_series_df(price_log: pd.DataFrame) -> pd.DataFrame:
    if price_log.empty:
        return pd.DataFrame(columns=PRICE_SERIES_COLUMNS)
    df = price_log.copy()
    if "datetime" not in df.columns and "ts" in df.columns:
        df["datetime"] = _ts_to_datetime(df["ts"])
    return df


def _resolve_indicator_params(cfg: Any, strategy_name: str) -> Optional[dict]:
    """Pull the active parameters for a technical-indicator strategy from cfg.

    Returns None when the cfg does not carry the strategy config object — callers
    treat that as "skip indicator emission" rather than fail.
    """
    strategies = getattr(cfg, "strategies", None)
    if strategies is None:
        return None
    sub = getattr(strategies, strategy_name, None)
    if sub is None:
        return None
    try:
        dumped = sub.model_dump() if hasattr(sub, "model_dump") else dict(sub)
    except Exception:
        return None
    return dumped if isinstance(dumped, dict) else None


def _build_run_parameters(cfg: Any, args: Any, strategy_names: list[str]) -> dict[str, Any]:
    """Capture the active research parameters that produced this result."""
    def _maybe_json_obj(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else value
        except Exception:
            return value

    strategies_obj = getattr(cfg, "strategies", None)
    strategy_params: dict[str, Any] = {}
    if strategies_obj is not None:
        for name in strategy_names:
            sub = getattr(strategies_obj, name, None)
            if sub is None:
                continue
            try:
                dumped = sub.model_dump() if hasattr(sub, "model_dump") else dict(sub)
            except Exception:
                dumped = {}
            if isinstance(dumped, dict):
                strategy_params[name] = _scrub_secrets(dumped)

    risk = getattr(cfg, "risk", None)
    risk_params = {
        key: getattr(risk, key)
        for key in ("max_order_notional_usd", "max_pos_pct_equity", "max_leverage")
        if risk is not None and hasattr(risk, key)
    }
    backtest = getattr(cfg, "backtest", None)
    backtest_params = {
        key: getattr(backtest, key)
        for key in ("order_latency_ms", "cancel_latency_ms", "queue_fill_fraction", "liquidate_on_end")
        if backtest is not None and hasattr(backtest, key)
    }
    cli_strategy_params = _maybe_json_obj(getattr(args, "strategy_params", None)) if args else None
    cli_risk_overrides = _maybe_json_obj(getattr(args, "risk_overrides", None)) if args else None
    return _scrub_secrets({
        "strategies": strategy_params,
        "risk": risk_params,
        "backtest": backtest_params,
        "overrides": {
            "strategy_params": cli_strategy_params or {},
            "risk_overrides": cli_risk_overrides or {},
        },
    })


def _indicator_lookback_bars(strategy_name: str, params: dict) -> int:
    if not bool(params.get("indicator_db_warmup", False)):
        return 0
    if strategy_name == "ma_crossover":
        return max(int(params.get("slow_window", 50) or 50) - 1, 0)
    if strategy_name == "ema_crossover":
        return max(int(params.get("slow_span", 50) or 50) * 3, 0)
    if strategy_name == "macd_crossover":
        slow_s = int(params.get("slow_span", 26) or 26)
        signal_s = int(params.get("signal_span", 9) or 9)
        return max(slow_s, signal_s) * 3
    return 0


def _fetch_warmup_candles(
    dsn: Optional[str],
    inst_ids: list[str],
    bar: str,
    start_ts: Any,
    lookback_bars: int,
) -> dict[str, pd.DataFrame]:
    if not dsn or not inst_ids or lookback_bars <= 0 or not bar:
        return {}
    try:
        import asyncio

        import asyncpg

        if isinstance(start_ts, (int, float, np.integer, np.floating)) or (
            isinstance(start_ts, str) and start_ts.isdigit()
        ):
            numeric_ts = float(start_ts)
            unit = "ms" if numeric_ts > 1e11 else "s"
            start_dt = pd.to_datetime(numeric_ts, unit=unit, utc=True, errors="coerce")
        else:
            start_dt = pd.to_datetime(start_ts, utc=True, errors="coerce")
        if pd.isna(start_dt):
            return {}
        start_value = start_dt.to_pydatetime()

        async def _fetch() -> dict[str, pd.DataFrame]:
            conn = await asyncpg.connect(dsn)
            try:
                result: dict[str, pd.DataFrame] = {}
                for inst_id in inst_ids:
                    rows = await conn.fetch(
                        """
                        SELECT ts, close FROM canonical_candles
                        WHERE inst_id=$1 AND bar=$2 AND ts < $3
                        ORDER BY ts DESC LIMIT $4
                        """,
                        inst_id,
                        bar,
                        start_value,
                        lookback_bars,
                    )
                    if not rows:
                        continue
                    df = pd.DataFrame([dict(r) for r in rows]).sort_values("ts")
                    df["inst_id"] = inst_id
                    df["datetime"] = _ts_to_datetime(df["ts"])
                    result[inst_id] = df
                return result
            finally:
                await conn.close()

        return asyncio.run(_fetch())
    except Exception as exc:
        logger.warning("Could not fetch indicator warmup candles from DB: {}", exc)
        return {}


def _compute_indicator_frame(
    price_df: pd.DataFrame,
    strategy_name: str,
    params: dict,
    warmup_per_inst: Optional[dict[str, pd.DataFrame]] = None,
) -> pd.DataFrame:
    """Recompute fast/slow (and MACD) per inst_id from price_series close prices.

    Mirrors the math in src/okx_quant/strategies/technical_indicators.py so the
    artifact lines up with the live strategy without re-importing it.
    """
    if price_df.empty or "close" not in price_df.columns:
        return pd.DataFrame(columns=INDICATOR_SERIES_COLUMNS)

    out_frames: list[pd.DataFrame] = []
    grouped = price_df.sort_values("ts").groupby("inst_id", sort=False)
    for inst_id, group in grouped:
        sub = group.copy()
        warm = (warmup_per_inst or {}).get(str(inst_id))
        warm_closes = (
            warm.sort_values("ts")["close"].astype(float)
            if warm is not None and not warm.empty and "close" in warm.columns
            else pd.Series(dtype=float)
        )
        closes = pd.concat(
            [warm_closes.reset_index(drop=True), sub["close"].astype(float).reset_index(drop=True)],
            ignore_index=True,
        )
        warm_len = len(warm_closes)
        fast = pd.Series(float("nan"), index=closes.index)
        slow = pd.Series(float("nan"), index=closes.index)
        macd = pd.Series(float("nan"), index=closes.index)
        macd_signal = pd.Series(float("nan"), index=closes.index)
        macd_hist = pd.Series(float("nan"), index=closes.index)

        if strategy_name == "ma_crossover":
            fast_w = int(params.get("fast_window", 20) or 20)
            slow_w = int(params.get("slow_window", 50) or 50)
            fast = closes.rolling(fast_w, min_periods=fast_w).mean()
            slow = closes.rolling(slow_w, min_periods=slow_w).mean()
        elif strategy_name == "ema_crossover":
            fast_s = int(params.get("fast_span", 20) or 20)
            slow_s = int(params.get("slow_span", 50) or 50)
            fast = closes.ewm(span=fast_s, adjust=False).mean()
            slow = closes.ewm(span=slow_s, adjust=False).mean()
        elif strategy_name == "macd_crossover":
            fast_s = int(params.get("fast_span", 12) or 12)
            slow_s = int(params.get("slow_span", 26) or 26)
            signal_s = int(params.get("signal_span", 9) or 9)
            fast = closes.ewm(span=fast_s, adjust=False).mean()
            slow = closes.ewm(span=slow_s, adjust=False).mean()
            macd_line = fast - slow
            signal_line = macd_line.ewm(span=signal_s, adjust=False).mean()
            macd = macd_line
            macd_signal = signal_line
            macd_hist = macd_line - signal_line
        else:
            continue

        out = pd.DataFrame({
            "ts": sub["ts"].tolist(),
            "inst_id": inst_id,
            "strategy": strategy_name,
            "close": sub["close"].astype(float).values,
            "fast_value": fast.iloc[warm_len:].values,
            "slow_value": slow.iloc[warm_len:].values,
            "macd": macd.iloc[warm_len:].values,
            "macd_signal": macd_signal.iloc[warm_len:].values,
            "macd_histogram": macd_hist.iloc[warm_len:].values,
            "warmup_source": "db" if warm_len > 0 else "cold",
        })
        if "datetime" in sub.columns:
            out["datetime"] = sub["datetime"].values
        out_frames.append(out)

    if not out_frames:
        return pd.DataFrame(columns=INDICATOR_SERIES_COLUMNS)
    df = pd.concat(out_frames, ignore_index=True)
    if "datetime" not in df.columns:
        df["datetime"] = _ts_to_datetime(df["ts"])
    return df


def _build_indicator_series_df(
    price_df: pd.DataFrame,
    cfg: Any,
    strategy_names: list[str],
    dsn: Optional[str] = None,
    bar: str = "",
) -> pd.DataFrame:
    """Recompute indicator time series for any technical strategy in the run.

    Empty DataFrame when no technical strategy is active or when price_series is
    missing close prices — non-fatal, just skips emitting the CSV.
    """
    active = [s for s in (strategy_names or []) if s in _TECHNICAL_STRATEGIES]
    if not active or price_df.empty or "close" not in price_df.columns:
        return pd.DataFrame(columns=INDICATOR_SERIES_COLUMNS)
    frames: list[pd.DataFrame] = []
    inst_ids = [str(s) for s in price_df.get("inst_id", pd.Series(dtype=object)).dropna().unique()]
    start_ts = price_df["ts"].min() if "ts" in price_df.columns and not price_df.empty else None
    for strat in active:
        params = _resolve_indicator_params(cfg, strat) or {}
        lookback = _indicator_lookback_bars(strat, params)
        warmup = _fetch_warmup_candles(dsn, inst_ids, bar, start_ts, lookback) if lookback > 0 else {}
        sub = _compute_indicator_frame(price_df, strat, params, warmup_per_inst=warmup)
        if not sub.empty:
            frames.append(sub)
    if not frames:
        return pd.DataFrame(columns=INDICATOR_SERIES_COLUMNS)
    df = pd.concat(frames, ignore_index=True)
    trimmed: list[pd.DataFrame] = []
    for _, group in df.sort_values("ts").groupby(["strategy", "inst_id"], sort=False):
        finite_mask = group["fast_value"].apply(_is_finite_number) | group["slow_value"].apply(_is_finite_number)
        if finite_mask.any():
            first_idx = finite_mask[finite_mask].index[0]
            trimmed.append(group.loc[first_idx:])
    if not trimmed:
        return pd.DataFrame(columns=INDICATOR_SERIES_COLUMNS)
    return pd.concat(trimmed, ignore_index=True)


def _indicator_warmup_sources(indicator_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    if indicator_df.empty or not {"strategy", "inst_id", "warmup_source"} <= set(indicator_df.columns):
        return {}
    out: dict[str, dict[str, str]] = {}
    for (strategy, inst_id), group in indicator_df.groupby(["strategy", "inst_id"], sort=True):
        sources = [str(v) for v in group["warmup_source"].dropna().unique()]
        source = "db" if "db" in sources else "cold"
        out.setdefault(str(strategy), {})[str(inst_id)] = source
    return out


def _build_data_coverage(
    market_frames_meta: list[dict],
    funding_frames_meta: list[dict],
) -> dict:
    return {
        "candles": market_frames_meta,
        "funding": funding_frames_meta,
    }


def _build_positions_from_trades(trade_log: pd.DataFrame) -> pd.DataFrame:
    """Build position snapshots from trade log (one row per real fill)."""
    if trade_log.empty:
        return pd.DataFrame(columns=POSITION_COLUMNS)
    df = trade_log.copy()
    if "datetime" not in df.columns:
        df["datetime"] = _ts_to_datetime(df["ts"])
    df["size"] = df.get("size_after", None)
    df["avg_entry"] = df.get("avg_entry_after", None)
    df["mark_price"] = df.get("fill_px", None)
    df["notional"] = df.get("position_notional_after", None)
    df["unrealized_pnl"] = df.get("unrealized_pnl_after", None)
    df["realized_pnl"] = df.get("realized_pnl", None)
    df["net_realized_pnl"] = df.get("net_realized_pnl", None)
    df["cash"] = df.get("cash_after", None)
    df["equity"] = df.get("equity_after", None)
    df["leverage"] = float("nan")
    return df


# ---------------------------------------------------------------------------
# Sensitive key filter for config export
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = {
    "api_key", "secret", "passphrase", "password", "token",
    "telegram_token", "bot_token", "webhook_secret",
}


def _scrub_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: "***REDACTED***" if k.lower() in _SENSITIVE_KEYS else _scrub_secrets(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub_secrets(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def save_backtest_artifacts(
    result: Any,
    cfg: Any,
    args: Any,
    output_dir: str = "results",
    run_id: Optional[str] = None,
    strategy_names: Optional[list[str]] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    bar: str = "1H",
    market_frames_meta: Optional[list[dict]] = None,
    funding_frames_meta: Optional[list[dict]] = None,
    validation_results: Optional[dict[str, Any]] = None,
) -> Path:
    """
    Write all backtest artifacts for a single run.

    Returns the path to the run directory.
    """
    # Build run directory
    strats = strategy_names or getattr(args, "strategy", []) or []
    start_s = start or getattr(args, "start", None)
    end_s = end or getattr(args, "end", None)
    bar_s = bar or getattr(args, "bar", "1H")
    run_id_final = build_run_id(strats, start_s, end_s, bar_s, run_id)
    run_parameters = _build_run_parameters(cfg, args, strats)

    # Resolve DSN: prefer cfg.storage.timescale_dsn (populated by load_config from
    # DATABASE_URL env var when YAML omits it), fall back to env var directly.
    dsn: Optional[str] = getattr(getattr(cfg, "storage", None), "timescale_dsn", None) or os.environ.get("DATABASE_URL")
    artifact_mode = _artifact_mode(dsn=dsn)
    write_files = artifact_mode in {"files", "both"}
    run_dir = Path(output_dir) / run_id_final
    if write_files:
        run_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------
    # Pull data from result
    # -------------------------------------------------------------------
    order_log: pd.DataFrame = getattr(result, "order_log", pd.DataFrame())
    fill_log: pd.DataFrame = getattr(result, "fill_log", pd.DataFrame())
    trade_log: pd.DataFrame = getattr(result, "trade_log", pd.DataFrame())
    funding_log: pd.DataFrame = getattr(result, "funding_log", pd.DataFrame())
    price_log: pd.DataFrame = getattr(result, "price_log", pd.DataFrame())
    equity_curve: pd.Series = getattr(result, "equity_curve", pd.Series(dtype=float))
    metrics: dict = dict(getattr(result, "metrics", {}))
    signal_log: list[dict] = getattr(result, "signal_log", [])
    risk_event_log: list[dict] = getattr(result, "risk_event_log", [])
    rejected_log: list[dict] = getattr(result, "rejected_log", [])
    cancel_log_data: list[dict] = getattr(result, "cancel_log", [])
    result_validation: dict[str, Any] = dict(getattr(result, "validation", {}) or {})
    if validation_results and "cpcv" in validation_results:
        cpcv_payload = validation_results.get("cpcv") or {}
        if _is_finite_number(cpcv_payload.get("dsr")):
            metrics["dsr"] = cpcv_payload.get("dsr")
        if _is_finite_number(cpcv_payload.get("psr")):
            metrics["psr"] = cpcv_payload.get("psr")

    # -------------------------------------------------------------------
    # config.json
    # -------------------------------------------------------------------
    try:
        cfg_dict = cfg.model_dump() if hasattr(cfg, "model_dump") else {}
    except Exception:
        cfg_dict = {}
    config_data = _scrub_secrets({
        "system": cfg_dict.get("system", {}),
        "strategies": cfg_dict.get("strategies", {}),
        "risk": cfg_dict.get("risk", {}),
        "backtest": cfg_dict.get("backtest", {}),
        "storage": cfg_dict.get("storage", {}),
        "cli_args": {
            k: v for k, v in vars(args).items()
            if k.lower() not in _SENSITIVE_KEYS
        } if args else {},
    })
    if write_files:
        _write_json(run_dir / "config.json", config_data)

    # -------------------------------------------------------------------
    # metrics.json — use already-computed metrics from result
    # -------------------------------------------------------------------
    if write_files:
        _write_json(run_dir / "metrics.json", metrics)

    # -------------------------------------------------------------------
    # orders.csv
    # -------------------------------------------------------------------
    orders_df = _normalize_orders(order_log) if not order_log.empty else pd.DataFrame()
    if write_files:
        _write_csv(run_dir / "orders.csv", orders_df, ORDER_COLUMNS)

    # -------------------------------------------------------------------
    # fills.csv
    # -------------------------------------------------------------------
    fills_df = _normalize_fills(fill_log) if not fill_log.empty else pd.DataFrame()
    if write_files:
        _write_csv(run_dir / "fills.csv", fills_df, FILL_COLUMNS)

    # -------------------------------------------------------------------
    # trades.csv
    # -------------------------------------------------------------------
    trades_df = trade_log.copy() if not trade_log.empty else pd.DataFrame()
    if not trades_df.empty:
        # Only real trades (not funding cashflow entries)
        trades_df = trades_df[trades_df.get("fill_sz", pd.Series(0, index=trades_df.index)).astype(float) > 0].copy()
        if "datetime" not in trades_df.columns:
            trades_df["datetime"] = _ts_to_datetime(trades_df["ts"])
        if "notional_usd" not in trades_df.columns:
            if "metadata" in trades_df.columns:
                trades_df["notional_usd"] = trades_df["metadata"].apply(
                    lambda m: _safe_float(m.get("notional_usd"), float("nan")) if isinstance(m, dict) else float("nan")
                )
            else:
                trades_df["notional_usd"] = float("nan")
        fallback_mask = trades_df["notional_usd"].isna() | (trades_df["notional_usd"] == 0)
        if fallback_mask.any():
            ct_val = pd.Series(1.0, index=trades_df.index)
            if "ct_val_after" in trades_df.columns:
                ct_val = trades_df["ct_val_after"].fillna(1.0)
            trades_df.loc[fallback_mask, "notional_usd"] = (
                trades_df.loc[fallback_mask, "fill_px"].astype(float)
                * trades_df.loc[fallback_mask, "fill_sz"].astype(float)
                * ct_val.loc[fallback_mask].astype(float)
            ).abs()
        if "metadata" in trades_df.columns:
            trades_df["metadata"] = trades_df["metadata"].apply(_dump_metadata)
    if write_files:
        _write_csv(run_dir / "trades.csv", trades_df, TRADE_COLUMNS)

    # -------------------------------------------------------------------
    # positions.csv
    # -------------------------------------------------------------------
    positions_df = _build_positions_from_trades(trade_log)
    if write_files:
        _write_csv(run_dir / "positions.csv", positions_df, POSITION_COLUMNS)

    # -------------------------------------------------------------------
    # equity_curve.csv
    # -------------------------------------------------------------------
    equity_df = _build_equity_df(equity_curve, fill_log, funding_log)
    if write_files:
        _write_csv(run_dir / "equity_curve.csv", equity_df, EQUITY_COLUMNS)

    # -------------------------------------------------------------------
    # returns.csv
    # -------------------------------------------------------------------
    returns_df = _build_returns_df(equity_curve)
    if write_files:
        _write_csv(run_dir / "returns.csv", returns_df, RETURN_COLUMNS)

    # -------------------------------------------------------------------
    # drawdown.csv
    # -------------------------------------------------------------------
    drawdown_df = _build_drawdown_df(equity_curve)
    if write_files:
        _write_csv(run_dir / "drawdown.csv", drawdown_df, DRAWDOWN_COLUMNS)

    # -------------------------------------------------------------------
    # funding.csv
    # -------------------------------------------------------------------
    funding_df = _build_funding_df(funding_log) if not funding_log.empty else pd.DataFrame()
    if write_files:
        _write_csv(run_dir / "funding.csv", funding_df, FUNDING_COLUMNS)

    # -------------------------------------------------------------------
    # signals.csv
    # -------------------------------------------------------------------
    signals_df = pd.DataFrame(signal_log) if signal_log else pd.DataFrame()
    if not signals_df.empty and "datetime" not in signals_df.columns:
        signals_df["datetime"] = _ts_to_datetime(signals_df["ts"])
    if not signals_df.empty and "metadata" in signals_df.columns:
        signals_df["metadata"] = signals_df["metadata"].apply(_dump_metadata)
    if write_files:
        _write_csv(run_dir / "signals.csv", signals_df, SIGNAL_COLUMNS)

    # -------------------------------------------------------------------
    # risk_events.csv
    # -------------------------------------------------------------------
    risk_df = pd.DataFrame(risk_event_log) if risk_event_log else pd.DataFrame()
    if not risk_df.empty and "datetime" not in risk_df.columns:
        risk_df["datetime"] = _ts_to_datetime(risk_df["ts"])
    if not risk_df.empty and "metadata" in risk_df.columns:
        risk_df["metadata"] = risk_df["metadata"].apply(_dump_metadata)
    if write_files:
        _write_csv(run_dir / "risk_events.csv", risk_df, RISK_EVENT_COLUMNS)

    # -------------------------------------------------------------------
    # rejected_orders.csv
    # -------------------------------------------------------------------
    rejected_df = pd.DataFrame(rejected_log) if rejected_log else pd.DataFrame()
    if not rejected_df.empty:
        if "datetime" not in rejected_df.columns:
            rejected_df["datetime"] = _ts_to_datetime(rejected_df["ts"])
        if "metadata" in rejected_df.columns:
            rejected_df["metadata"] = rejected_df["metadata"].apply(_dump_metadata)
    if write_files:
        _write_csv(run_dir / "rejected_orders.csv", rejected_df, REJECTED_ORDER_COLUMNS)

    # -------------------------------------------------------------------
    # cancel_log.csv
    # -------------------------------------------------------------------
    cancel_df = pd.DataFrame(cancel_log_data) if cancel_log_data else pd.DataFrame()
    if not cancel_df.empty and "datetime" not in cancel_df.columns:
        cancel_df["datetime"] = _ts_to_datetime(cancel_df["ts"])
    if write_files:
        _write_csv(run_dir / "cancel_log.csv", cancel_df, CANCEL_LOG_COLUMNS)

    # -------------------------------------------------------------------
    # execution_markers.csv
    # -------------------------------------------------------------------
    markers_df = _build_execution_markers(fills_df, trades_df)
    if write_files:
        _write_csv(run_dir / "execution_markers.csv", markers_df, EXECUTION_MARKER_COLUMNS)

    # -------------------------------------------------------------------
    # price_series.csv
    # -------------------------------------------------------------------
    price_df = _build_price_series_df(price_log)
    if write_files:
        _write_csv(run_dir / "price_series.csv", price_df, PRICE_SERIES_COLUMNS)

    # -------------------------------------------------------------------
    # indicator_series.csv — only emitted for technical-indicator strategies
    # -------------------------------------------------------------------
    indicator_df = _build_indicator_series_df(price_df, cfg, strats, dsn=dsn, bar=bar_s)
    indicator_warmup_sources = _indicator_warmup_sources(indicator_df)
    if write_files:
        _write_csv(run_dir / "indicator_series.csv", indicator_df, INDICATOR_SERIES_COLUMNS)

    # -------------------------------------------------------------------
    # data_coverage.json
    # -------------------------------------------------------------------
    coverage = _build_data_coverage(
        market_frames_meta or [],
        funding_frames_meta or [],
    )
    replay_coverage = result_validation.get("gate3_data_coverage")
    if isinstance(replay_coverage, dict):
        coverage["replay_gate"] = replay_coverage
        if "features" in replay_coverage:
            coverage["features"] = replay_coverage.get("features") or []
    if write_files:
        _write_json(run_dir / "data_coverage.json", coverage)

    # -------------------------------------------------------------------
    # result.json — top-level index
    # -------------------------------------------------------------------
    symbols = list({
        row.get("inst_id", "") for _, row in (
            fills_df.iterrows() if not fills_df.empty else iter([])
        )
    } | {
        row.get("inst_id", "") for _, row in (
            orders_df.iterrows() if not orders_df.empty else iter([])
        )
    } | {
        row.get("inst_id", "") for _, row in (
            price_df.iterrows() if not price_df.empty else iter([])
        )
    })
    symbols = [s for s in symbols if s]

    artifact_refs = {
        "config": "config.json",
        "metrics": "metrics.json",
        "orders": "orders.csv",
        "fills": "fills.csv",
        "trades": "trades.csv",
        "positions": "positions.csv",
        "equity": "equity_curve.csv",
        "returns": "returns.csv",
        "drawdown": "drawdown.csv",
        "funding": "funding.csv",
        "signals": "signals.csv",
        "risk_events": "risk_events.csv",
        "rejected_orders": "rejected_orders.csv",
        "cancel_log": "cancel_log.csv",
        "execution_markers": "execution_markers.csv",
        "price_series": "price_series.csv",
        "indicator_series": "indicator_series.csv",
        "data_coverage": "data_coverage.json",
    }
    if artifact_mode == "db":
        artifact_refs = {
            key: f"db://backtest_artifacts/{run_id_final}/{key}"
            for key in artifact_refs
        }

    result_json = {
        "run_id": run_id_final,
        "created_at": _now_utc(),
        "mode": "replay_backtest",
        "strategies": strats,
        "symbols": symbols,
        "bar": bar_s,
        "start": start_s,
        "end": end_s,
        "backend": getattr(getattr(cfg, "storage", None), "candle_backend", "parquet"),
        "data_source": {
            "ohlcv_layer": "canonical_candles",
            "funding_layer": "funding_rates",
            "primary_exchange": "binance",
        },
        "metrics": metrics,
        "parameters": run_parameters,
        "artifacts": artifact_refs,
    }
    validation_payload = dict(result_validation)
    if validation_results:
        if "walk_forward" in validation_results:
            result_json["walk_forward"] = validation_results["walk_forward"]
        if "cpcv" in validation_results:
            result_json["cpcv"] = validation_results["cpcv"]
        validation_payload.update({
            key: value
            for key, value in validation_results.items()
            if key not in {"walk_forward", "cpcv"}
        })
    if indicator_warmup_sources:
        validation_payload.setdefault("indicator_warmup_sources", indicator_warmup_sources)
    if validation_payload:
        result_json["validation"] = validation_payload
    if write_files:
        _write_json(run_dir / "result.json", result_json)
    _upsert_run_to_db(run_id_final, result_json, run_dir, dsn=dsn)
    _upsert_artifacts_to_db(run_id_final, {
        "result": result_json,
        "config": config_data,
        "metrics": metrics,
        "orders": _df_records(ensure_columns(orders_df.copy(), ORDER_COLUMNS)),
        "fills": _df_records(ensure_columns(fills_df.copy(), FILL_COLUMNS)),
        "trades": _df_records(ensure_columns(trades_df.copy(), TRADE_COLUMNS)),
        "positions": _df_records(ensure_columns(positions_df.copy(), POSITION_COLUMNS)),
        "equity": _df_records(ensure_columns(equity_df.copy(), EQUITY_COLUMNS)),
        "returns": _df_records(ensure_columns(returns_df.copy(), RETURN_COLUMNS)),
        "drawdown": _df_records(ensure_columns(drawdown_df.copy(), DRAWDOWN_COLUMNS)),
        "funding": _df_records(ensure_columns(funding_df.copy(), FUNDING_COLUMNS)),
        "signals": _df_records(ensure_columns(signals_df.copy(), SIGNAL_COLUMNS)),
        "risk_events": _df_records(ensure_columns(risk_df.copy(), RISK_EVENT_COLUMNS)),
        "rejected_orders": _df_records(ensure_columns(rejected_df.copy(), REJECTED_ORDER_COLUMNS)),
        "cancel_log": _df_records(ensure_columns(cancel_df.copy(), CANCEL_LOG_COLUMNS)),
        "execution_markers": _df_records(ensure_columns(markers_df.copy(), EXECUTION_MARKER_COLUMNS)),
        "price_series": _df_records(ensure_columns(price_df.copy(), PRICE_SERIES_COLUMNS)),
        "indicator_series": _df_records(ensure_columns(indicator_df.copy(), INDICATOR_SERIES_COLUMNS)),
        "data_coverage": coverage,
    }, dsn=dsn, mode=artifact_mode)

    return run_dir
