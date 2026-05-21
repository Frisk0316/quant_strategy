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
