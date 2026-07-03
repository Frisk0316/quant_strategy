"""Family-minting distinctness checks for the research pipeline."""
from __future__ import annotations

from math import isfinite, sqrt
from pathlib import Path
from typing import Any, Mapping, Sequence

from backtesting.pipeline_checkpoint1 import family_registry_from_text

SCHEMA_VERSION = 1
HARD_ASSIGN_CORR = 0.90
BORDERLINE_CORR = 0.70
DECISIONS = {"ASSIGN", "MINT", "NEEDS_HUMAN", "SKIP_RECOMMENDED"}


def _points(signal: Any) -> dict[Any, float]:
    if isinstance(signal, Mapping):
        items = signal.items()
    elif isinstance(signal, Sequence) and not isinstance(signal, (str, bytes, bytearray)):
        items = enumerate(signal)
    else:
        return {}

    points: dict[Any, float] = {}
    for key, value in items:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if isfinite(number):
            points[key] = number
    return points


def _abs_corr(left: Any, right: Any) -> float:
    left_points = _points(left)
    right_points = _points(right)
    keys = sorted(set(left_points) & set(right_points))
    if len(keys) < 2:
        return 0.0
    xs = [left_points[key] for key in keys]
    ys = [right_points[key] for key in keys]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    dx = [value - mean_x for value in xs]
    dy = [value - mean_y for value in ys]
    denom = sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    if denom == 0.0:
        return 0.0
    return abs(sum(a * b for a, b in zip(dx, dy)) / denom)


def _review_items(decision: str, status: str | None) -> list[str]:
    items: list[str] = []
    if decision == "MINT":
        items.append("mechanism_novelty")
    if decision == "NEEDS_HUMAN":
        items.append("borderline_distinctness")
    if status and ("refuted" in status.lower() or "shelved" in status.lower()):
        items.append("refuted_family_twist_justification")
    return items or ["mechanism_novelty"]


def decide_family_minting(
    candidate_signal: Any,
    reference_signals: Mapping[str, Any],
    claimed_family_id_or_NEW: str,
    claimed_mechanism: str,
    ledger_path: str | Path,
    *,
    batch_id: str = "",
    candidate_id: str = "",
) -> dict[str, Any]:
    registry = family_registry_from_text(Path(ledger_path).read_text(encoding="utf-8"))
    correlations = {
        family_id: _abs_corr(candidate_signal, signal)
        for family_id, signal in reference_signals.items()
    }
    nearest_family_id = max(correlations, key=correlations.get) if correlations else ""
    max_abs_corr = correlations.get(nearest_family_id, 0.0)
    claimed = str(claimed_family_id_or_NEW or "").strip()
    claimed_existing = claimed.upper() != "NEW"
    assigned_family_id = claimed if claimed_existing else nearest_family_id
    nearest = registry.get(assigned_family_id or nearest_family_id)
    nearest_status = nearest.status if nearest else ""
    nearest_trials = nearest.cumulative_n_trials if nearest else 0

    if claimed_existing:
        decision = "ASSIGN"
        reason = "claimed existing family; inherit ledger budget"
    elif max_abs_corr >= HARD_ASSIGN_CORR:
        if "refuted" in nearest_status.lower() or "shelved" in nearest_status.lower():
            decision = "SKIP_RECOMMENDED"
            reason = "highly correlated with a refuted/shelved family"
        else:
            decision = "ASSIGN"
            reason = "highly correlated with an existing family"
    elif max_abs_corr >= BORDERLINE_CORR:
        decision = "NEEDS_HUMAN"
        reason = "borderline distinctness needs checkpoint review"
    else:
        decision = "MINT"
        reason = "low correlation with supplied reference families; provisional new-family candidate"

    inherited_n_trials = nearest_trials if decision in {"ASSIGN", "SKIP_RECOMMENDED"} else 0
    k_used = nearest.k_used if nearest else 0
    k_limit = nearest.k_limit if nearest else 0
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "candidate_id": candidate_id,
        "claimed_family_id_or_NEW": claimed,
        "claimed_mechanism": claimed_mechanism,
        "max_abs_corr": max_abs_corr,
        "nearest_family_id": assigned_family_id if claimed_existing else nearest_family_id,
        "nearest_family_status": nearest_status,
        "nearest_family_cumulative_n_trials": nearest_trials,
        "decision": decision,
        "inherited_n_trials": inherited_n_trials,
        "k_used": k_used,
        "k_limit": k_limit,
        "at_k_limit": bool(k_limit and k_used >= k_limit),
        "provisional_new_family": decision == "MINT",
        "human_review_items": _review_items(decision, nearest_status),
        "reason": reason,
    }
