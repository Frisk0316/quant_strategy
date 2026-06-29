"""Stage 2 feasibility gate helpers for the research pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_CHECKS = ("data_availability", "distinctness", "cost_after_edge")
VALID_STATUSES = {"PASS", "FAIL"}
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FeasibilityCheck:
    name: str
    status: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeasibilityResult:
    batch_id: str
    candidate_id: str
    candidate_dir: str
    hypothesis_id: str
    family_id: str
    checks: tuple[FeasibilityCheck, ...]
    schema_version: int = SCHEMA_VERSION


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Stage 2 field {key!r} must be a non-empty string")
    return value


def _check_from_dict(payload: dict[str, Any]) -> FeasibilityCheck:
    if not isinstance(payload, dict):
        raise ValueError("Stage 2 check must be an object")
    name = _required_text(payload, "name")
    status = _required_text(payload, "status")
    reason = _required_text(payload, "reason")
    if status not in VALID_STATUSES:
        raise ValueError(f"unknown Stage 2 status {status!r}")
    details = payload.get("details", {})
    if not isinstance(details, dict):
        raise ValueError("Stage 2 check details must be an object")
    return FeasibilityCheck(name=name, status=status, reason=reason, details=dict(details))


def result_from_dict(payload: dict[str, Any]) -> FeasibilityResult:
    if not isinstance(payload, dict):
        raise ValueError("Stage 2 payload must be an object")
    checks_payload = payload.get("checks")
    if not isinstance(checks_payload, list):
        raise ValueError("Stage 2 field 'checks' must be a list")
    checks = tuple(_check_from_dict(row) for row in checks_payload)
    seen: set[str] = set()
    for check in checks:
        if check.name in seen:
            raise ValueError(f"duplicate Stage 2 check {check.name!r}")
        seen.add(check.name)
    schema_version = payload.get("schema_version", SCHEMA_VERSION)
    if type(schema_version) is not int or schema_version != SCHEMA_VERSION:
        raise ValueError(f"unsupported Stage 2 schema_version {schema_version!r}")
    return FeasibilityResult(
        schema_version=schema_version,
        batch_id=_required_text(payload, "batch_id"),
        candidate_id=_required_text(payload, "candidate_id"),
        candidate_dir=_required_text(payload, "candidate_dir"),
        hypothesis_id=_required_text(payload, "hypothesis_id"),
        family_id=_required_text(payload, "family_id"),
        checks=checks,
    )


def evaluate_stage2_result(result: FeasibilityResult) -> str:
    by_name = {check.name: check for check in result.checks}
    for required in REQUIRED_CHECKS:
        check = by_name.get(required)
        if check is None or check.status != "PASS":
            return "FAIL"
    return "PASS"


def result_to_dict(result: FeasibilityResult) -> dict[str, Any]:
    return {
        "schema_version": result.schema_version,
        "batch_id": result.batch_id,
        "candidate_id": result.candidate_id,
        "candidate_dir": result.candidate_dir,
        "hypothesis_id": result.hypothesis_id,
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
        "stage2_status": evaluate_stage2_result(result),
    }
