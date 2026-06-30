"""Checkpoint 1 automation helpers for the research pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
VALID_STATUSES = {"PASS", "FAIL", "NEEDS_HUMAN"}
HUMAN_REVIEW_ITEMS = (
    "leak_lag_spotcheck",
    "diff_block_reason_honest",
    "verdict",
    "retry_vs_new_family",
)


@dataclass(frozen=True)
class Checkpoint1Check:
    name: str
    status: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Checkpoint1Result:
    batch_id: str
    candidate_id: str
    family_id: str
    checks: tuple[Checkpoint1Check, ...]
    human_review_items: tuple[str, ...] = HUMAN_REVIEW_ITEMS
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class _RegistryRow:
    family_id: str
    trials: int
    artifact: str
    outcome: str
    cumulative_override: int | None = None
    cumulative_n_trials: int = 0


@dataclass(frozen=True)
class FamilyRegistryEntry:
    family_id: str
    cumulative_n_trials: int
    status: str
    artifact: str
    k_used: int = 0
    k_limit: int = 0


def _normalize_path(value: str | Path) -> str:
    return str(value).strip().strip("`").replace("\\", "/").lower().lstrip("./")


def _bool_gate(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict) and isinstance(value.get("passed"), bool):
        return value["passed"]
    return None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_trials(value: str) -> int | None:
    match = re.match(r"\s*(\d+)\b", value)
    return int(match.group(1)) if match else None


def _parse_cumulative_trials_override(cells: list[str]) -> int | None:
    text = " ".join(cells).lower()
    patterns = (
        r"family[-_\s]*cumulative[^|]*?`?n[_\s-]?trials`?\s*=\s*(\d+)",
        r"family[-_\s]*cumulative rule[^|.]*?at least\s+(\d+)\s+trials",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _parse_registry_rows(registry_text: str) -> list[_RegistryRow]:
    rows: list[_RegistryRow] = []
    for line in registry_text.splitlines():
        if not line.startswith("| E-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 9:
            continue
        trials = _parse_trials(cells[5])
        if trials is None:
            continue
        artifact = cells[6]
        outcome = cells[7]
        lower_row = f"{cells[5]} {artifact} {outcome}".lower()
        if "planned" in lower_row or "pending" in lower_row:
            continue
        rows.append(
            _RegistryRow(
                family_id=cells[3],
                trials=trials,
                artifact=artifact,
                outcome=outcome,
                cumulative_override=_parse_cumulative_trials_override(cells),
            )
        )
    return rows


def _with_family_cumulative_trials(rows: list[_RegistryRow]) -> list[_RegistryRow]:
    totals: dict[str, int] = {}
    cumulative_rows: list[_RegistryRow] = []
    for row in rows:
        current = totals.get(row.family_id, 0)
        cumulative = row.cumulative_override if row.cumulative_override is not None else max(current, row.trials)
        totals[row.family_id] = cumulative
        cumulative_rows.append(
            _RegistryRow(
                family_id=row.family_id,
                trials=row.trials,
                artifact=row.artifact,
                outcome=row.outcome,
                cumulative_override=row.cumulative_override,
                cumulative_n_trials=cumulative,
            )
        )
    return cumulative_rows


def _parse_family_k_budget(registry_text: str) -> dict[str, tuple[int, int]]:
    budgets: dict[str, tuple[int, int]] = {}
    for line in registry_text.splitlines():
        if not line.startswith("| F-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        k_used = _int_or_none(cells[1])
        k_limit = _int_or_none(cells[2])
        if k_used is None or k_limit is None:
            continue
        budgets[cells[0]] = (k_used, k_limit)
    return budgets


def family_registry_from_text(registry_text: str) -> dict[str, FamilyRegistryEntry]:
    families: dict[str, FamilyRegistryEntry] = {}
    k_budgets = _parse_family_k_budget(registry_text)
    for row in _with_family_cumulative_trials(_parse_registry_rows(registry_text)):
        k_used, k_limit = k_budgets.get(row.family_id, (0, 0))
        families[row.family_id] = FamilyRegistryEntry(
            family_id=row.family_id,
            cumulative_n_trials=row.cumulative_n_trials,
            status=row.outcome,
            artifact=row.artifact,
            k_used=k_used,
            k_limit=k_limit,
        )
    for family_id, (k_used, k_limit) in k_budgets.items():
        families.setdefault(
            family_id,
            FamilyRegistryEntry(
                family_id=family_id,
                cumulative_n_trials=0,
                status="",
                artifact="",
                k_used=k_used,
                k_limit=k_limit,
            ),
        )
    return families


def _expected_trials(rows: list[_RegistryRow], family_id: str, summary_path: str | Path | None) -> int | None:
    family_rows = [row for row in _with_family_cumulative_trials(rows) if row.family_id == family_id]
    if not family_rows:
        return None
    if summary_path is not None:
        needle = _normalize_path(summary_path)
        exact = [row for row in family_rows if needle in _normalize_path(row.artifact)]
        if exact:
            return exact[-1].cumulative_n_trials
    return family_rows[-1].cumulative_n_trials


def _check_n_trials(summary: dict[str, Any], registry_text: str, summary_path: str | Path | None) -> Checkpoint1Check:
    family_id = str(summary.get("family_id") or "")
    rows = _parse_registry_rows(registry_text)
    expected = _expected_trials(rows, family_id, summary_path)
    reported = _int_or_none(summary.get("family_cumulative_n_trials"))
    cpcv = summary.get("cpcv") if isinstance(summary.get("cpcv"), dict) else {}
    cpcv_trials = _int_or_none(cpcv.get("n_trials"))
    details = {
        "expected_family_trials": expected,
        "summary_family_cumulative_n_trials": reported,
        "cpcv_n_trials": cpcv_trials,
        "summary_path": _normalize_path(summary_path) if summary_path is not None else None,
    }
    if expected is None:
        return Checkpoint1Check("n_trials_reconcile", "FAIL", f"no registry row found for family {family_id!r}", details)
    if reported != expected or cpcv_trials != reported:
        return Checkpoint1Check("n_trials_reconcile", "FAIL", "summary/CPCV n_trials do not reconcile to registry", details)
    return Checkpoint1Check("n_trials_reconcile", "PASS", "summary and CPCV n_trials reconcile to registry", details)


def _check_leak(summary: dict[str, Any]) -> Checkpoint1Check:
    if summary.get("leak_test_passed") is True:
        return Checkpoint1Check("leak_test_present_and_green", "PASS", "leak_test_passed is true")
    return Checkpoint1Check("leak_test_present_and_green", "FAIL", "leak_test_passed is not true")


def _check_dsr_order(summary: dict[str, Any]) -> Checkpoint1Check:
    dsr = _float_or_none(summary.get("dsr"))
    psr = _float_or_none(summary.get("psr"))
    if dsr is None or psr is None:
        return Checkpoint1Check("dsr_le_psr", "NEEDS_HUMAN", "dsr_not_recomputable", {"dsr": dsr, "psr": psr})
    if dsr <= psr + 1e-12:
        return Checkpoint1Check("dsr_le_psr", "PASS", "DSR is not greater than PSR(0)", {"dsr": dsr, "psr": psr})
    return Checkpoint1Check("dsr_le_psr", "FAIL", "DSR exceeds PSR(0)", {"dsr": dsr, "psr": psr})


def _check_idealized(summary: dict[str, Any]) -> Checkpoint1Check:
    value = summary.get("idealized_fill")
    if value is False:
        return Checkpoint1Check("idealized_fill_excluded", "PASS", "idealized_fill is false")
    if value is True:
        return Checkpoint1Check("idealized_fill_excluded", "FAIL", "idealized_fill is true")
    return Checkpoint1Check("idealized_fill_excluded", "NEEDS_HUMAN", "idealized_fill is missing or not boolean")


def _check_portable(summary: dict[str, Any]) -> Checkpoint1Check:
    portable = _bool_gate(summary.get("portable_validation_gate"))
    promotion = _bool_gate(summary.get("promotion_gate_passed"))
    if portable is True:
        return Checkpoint1Check("portable_gate_or_honest_block", "PASS", "portable validation gate passed")
    if portable is False and promotion is False:
        return Checkpoint1Check(
            "portable_gate_or_honest_block",
            "PASS",
            "portable validation is blocked; human review must verify the block reason",
        )
    if portable is False and promotion is True:
        return Checkpoint1Check("portable_gate_or_honest_block", "FAIL", "promotion passed while portable validation failed")
    return Checkpoint1Check("portable_gate_or_honest_block", "NEEDS_HUMAN", "portable validation status is missing")


def _check_ct_val(summary: dict[str, Any]) -> Checkpoint1Check:
    if summary.get("ct_val_all_authoritative") is not True:
        return Checkpoint1Check("ct_val_authoritative_and_venue_match", "FAIL", "ct_val_all_authoritative is not true")
    sources = summary.get("ct_val_sources")
    if not isinstance(sources, dict) or not sources:
        return Checkpoint1Check("ct_val_authoritative_and_venue_match", "NEEDS_HUMAN", "ct_val_sources missing")
    data_source = summary.get("data_source") if isinstance(summary.get("data_source"), dict) else {}
    venue = data_source.get("primary_exchange") or summary.get("exchange")
    mismatches = [
        symbol
        for symbol, source in sources.items()
        if isinstance(source, dict) and venue and source.get("exchange") != venue
    ]
    if mismatches:
        return Checkpoint1Check(
            "ct_val_authoritative_and_venue_match",
            "FAIL",
            "ct_val source venue does not match run venue",
            {"run_venue": venue, "mismatches": mismatches},
        )
    return Checkpoint1Check("ct_val_authoritative_and_venue_match", "PASS", "ct_val sources are authoritative and venue-matched")


def _check_threshold(summary: dict[str, Any]) -> Checkpoint1Check:
    dsr = _float_or_none(summary.get("dsr"))
    psr = _float_or_none(summary.get("psr"))
    if dsr is None or psr is None:
        return Checkpoint1Check("dsr_psr_threshold", "NEEDS_HUMAN", "dsr_or_psr_missing", {"dsr": dsr, "psr": psr})
    if dsr >= 0.95 and psr >= 0.95:
        return Checkpoint1Check("dsr_psr_threshold", "PASS", "DSR and PSR meet the 0.95 threshold", {"dsr": dsr, "psr": psr})
    return Checkpoint1Check("dsr_psr_threshold", "FAIL", "DSR or PSR is below 0.95", {"dsr": dsr, "psr": psr})


def evaluate_summary(summary: dict[str, Any], registry_text: str, summary_path: str | Path | None = None) -> Checkpoint1Result:
    checks = (
        _check_n_trials(summary, registry_text, summary_path),
        _check_leak(summary),
        _check_dsr_order(summary),
        _check_idealized(summary),
        _check_portable(summary),
        _check_ct_val(summary),
        _check_threshold(summary),
    )
    return Checkpoint1Result(
        batch_id=str(summary.get("batch_id") or ""),
        candidate_id=str(summary.get("candidate_id") or ""),
        family_id=str(summary.get("family_id") or ""),
        checks=checks,
    )


def evaluate_checkpoint1_result(result: Checkpoint1Result) -> str:
    statuses = {check.status for check in result.checks}
    if "FAIL" in statuses:
        return "FAIL"
    if "NEEDS_HUMAN" in statuses:
        return "NEEDS_HUMAN"
    return "PASS"


def result_to_dict(result: Checkpoint1Result) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "batch_id": result.batch_id,
        "candidate_id": result.candidate_id,
        "family_id": result.family_id,
        "checks": [
            {
                "name": check.name,
                "status": check.status,
                "reason": check.reason,
                **({"details": check.details} if check.details else {}),
            }
            for check in result.checks
        ],
        "checkpoint1_auto_status": evaluate_checkpoint1_result(result),
        "human_review_items": list(result.human_review_items),
    }
