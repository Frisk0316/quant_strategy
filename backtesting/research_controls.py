"""Research-only controls shared by replay and parameter-sweep entrypoints."""
from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

RISK_OVERRIDE_KEYS = {
    "max_order_notional_usd",
    "max_pos_pct_equity",
    "max_leverage",
}

FILL_ALL_MAX_ORDER_NOTIONAL_USD = 1_000_000_000_000.0
FILL_ALL_MAX_POS_PCT_EQUITY = 1_000_000.0
FILL_ALL_STALE_QUOTE_PCT = 1_000_000.0


class ResearchControlError(ValueError):
    """Raised when a research-only override is invalid."""


def sanitize_risk_overrides(raw: Any) -> dict[str, float]:
    """Validate and normalize risk overrides accepted by research backtests only."""
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ResearchControlError("risk_overrides must be an object")
    unknown = sorted(set(raw) - RISK_OVERRIDE_KEYS)
    if unknown:
        raise ResearchControlError(f"unsupported risk override(s): {', '.join(unknown)}")
    overrides: dict[str, float] = {}
    for key, value in raw.items():
        if value in (None, ""):
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ResearchControlError(f"risk override {key} must be numeric") from exc
        if not pd.notna(parsed) or parsed <= 0:
            raise ResearchControlError(f"risk override {key} must be > 0")
        overrides[key] = parsed
    return overrides


def apply_research_risk_overrides(cfg: Any, raw: Any) -> tuple[Any, dict[str, float]]:
    """Return a copied config with research-only risk overrides applied."""
    overrides = sanitize_risk_overrides(raw)
    if not overrides:
        return cfg, {}
    next_cfg = cfg.model_copy(deep=True) if hasattr(cfg, "model_copy") else cfg
    risk = getattr(next_cfg, "risk", None)
    if risk is None or not hasattr(risk, "model_copy"):
        raise ResearchControlError("config does not support risk overrides")
    next_cfg.risk = risk.model_copy(update=overrides)
    return next_cfg, overrides


def apply_fill_all_signal_controls(cfg: Any, enabled: bool) -> tuple[Any, dict[str, Any]]:
    """Return a copied config with idealized signal-fill controls applied.

    This is intentionally a research/backtest-only convenience: it raises the
    caps that commonly block signal-to-order conversion and switches the replay
    execution lifecycle to an immediate full-fill model. Live/demo/shadow config
    files remain unchanged unless the caller explicitly writes them.
    """
    if not enabled:
        return cfg, {}

    next_cfg = cfg.model_copy(deep=True) if hasattr(cfg, "model_copy") else cfg
    risk = getattr(next_cfg, "risk", None)
    backtest = getattr(next_cfg, "backtest", None)
    if risk is None or not hasattr(risk, "model_copy"):
        raise ResearchControlError("config does not support fill-all signal risk controls")
    if backtest is None or not hasattr(backtest, "model_copy"):
        raise ResearchControlError("config does not support fill-all signal backtest controls")

    risk_updates = {
        "max_order_notional_usd": max(
            float(getattr(risk, "max_order_notional_usd", 0.0) or 0.0),
            FILL_ALL_MAX_ORDER_NOTIONAL_USD,
        ),
        "max_pos_pct_equity": max(
            float(getattr(risk, "max_pos_pct_equity", 0.0) or 0.0),
            FILL_ALL_MAX_POS_PCT_EQUITY,
        ),
        "stale_quote_pct": max(
            float(getattr(risk, "stale_quote_pct", 0.0) or 0.0),
            FILL_ALL_STALE_QUOTE_PCT,
        ),
    }
    backtest_updates = {
        "fill_all_signals": True,
        "order_latency_ms": 0,
        "cancel_latency_ms": 0,
        "queue_fill_fraction": 1.0,
    }
    next_cfg.risk = risk.model_copy(update=risk_updates)
    next_cfg.backtest = backtest.model_copy(update=backtest_updates)
    return next_cfg, {
        "enabled": True,
        "risk": risk_updates,
        "backtest": backtest_updates,
    }


def summarize_risk_events(events: Any) -> dict[str, Any]:
    """Summarize replay risk events by reason and instrument."""
    if events is None:
        rows: list[dict[str, Any]] = []
    elif isinstance(events, pd.DataFrame):
        rows = events.to_dict("records")
    else:
        rows = [dict(row) for row in events]
    if not rows:
        return {
            "total": 0,
            "by_reason": {},
            "by_symbol": {},
            "by_reason_symbol": {},
        }

    by_reason = Counter(str(row.get("reason") or "unknown") for row in rows)
    by_symbol = Counter(str(row.get("inst_id") or "unknown") for row in rows)
    by_reason_symbol = Counter(
        f"{row.get('reason') or 'unknown'}|{row.get('inst_id') or 'unknown'}"
        for row in rows
    )
    timestamps = [row.get("datetime") for row in rows if row.get("datetime")]
    return {
        "total": len(rows),
        "by_reason": dict(sorted(by_reason.items())),
        "by_symbol": dict(sorted(by_symbol.items())),
        "by_reason_symbol": dict(sorted(by_reason_symbol.items())),
        "first_datetime": min(timestamps) if timestamps else None,
        "last_datetime": max(timestamps) if timestamps else None,
    }
