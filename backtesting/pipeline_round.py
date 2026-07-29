"""ADR-0016 result-blind round manifest and reconciliation helpers."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

COUNTED_STATUSES = {"ready", "execution_ready"}
TRACKS = {"new_research", "existing_iteration"}
STAGE2_TERMINAL = {"pass", "fail", "error"}
STAGE3_TERMINAL = {"pass", "fail", "error"}


def _canonical(payload: Mapping[str, Any]) -> bytes:
    clean = {key: value for key, value in payload.items() if key != "manifest_hash"}
    return json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(manifest)).hexdigest()


def join_candidate_inputs(
    literature: Iterable[Mapping[str, Any]],
    iterations: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Join result-blind drafts, dropping pending and duplicate family/provenance rows."""
    joined: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for track, rows in (("new_research", literature), ("existing_iteration", iterations)):
        for source in rows:
            candidate = dict(source)
            if candidate.get("draft_status") == "pending_llm":
                continue
            candidate["track"] = track
            key = (str(candidate.get("family_id", "")).strip(), str(candidate.get("provenance_id", "")).strip())
            if not all(key) or key in seen:
                continue
            seen.add(key)
            joined.append(candidate)
    return joined


def validate_round_manifest(
    manifest: Mapping[str, Any],
    *,
    registered_runners: Iterable[str],
) -> list[str]:
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        return ["candidates_not_list"]
    reasons: list[str] = []
    count = len(candidates)
    if not 10 <= count <= 15:
        reasons.append("candidate_count_outside_10_15")
    ids = [str(row.get("candidate_id", "")).strip() for row in candidates if isinstance(row, Mapping)]
    families = [str(row.get("family_id", "")).strip() for row in candidates if isinstance(row, Mapping)]
    if len(ids) != count or any(not value for value in ids) or len(set(ids)) != count:
        reasons.append("duplicate_or_missing_candidate_id")
    if len(families) != count or any(not value for value in families) or len(set(families)) != count:
        reasons.append("duplicate_or_missing_family")

    runners = set(registered_runners)
    new_count = iteration_count = 0
    for row in candidates:
        if not isinstance(row, Mapping):
            reasons.append("candidate_not_object")
            continue
        track = row.get("track")
        new_count += track == "new_research"
        iteration_count += track == "existing_iteration"
        if track not in TRACKS:
            reasons.append(f"{row.get('candidate_id')}:invalid_track")
        if row.get("draft_status") == "pending_llm":
            reasons.append(f"{row.get('candidate_id')}:pending_llm")
        if row.get("execution_status") not in COUNTED_STATUSES:
            reasons.append(f"{row.get('candidate_id')}:not_execution_ready")
        if row.get("runner") not in runners:
            reasons.append(f"{row.get('candidate_id')}:runner_not_registered")
        if track == "new_research" and not row.get("verified_paper"):
            reasons.append(f"{row.get('candidate_id')}:paper_not_verified")
        if track == "existing_iteration" and not row.get("iteration_rationale"):
            reasons.append(f"{row.get('candidate_id')}:missing_iteration_rationale")
    if new_count < 8:
        reasons.append("new_research_count_below_8")
    if iteration_count < 2:
        reasons.append("existing_iteration_count_below_2")
    return reasons


def seal_round_manifest(
    manifest: Mapping[str, Any],
    *,
    registered_runners: Iterable[str],
) -> dict[str, Any]:
    sealed = prepare_round_manifest(manifest, registered_runners=registered_runners)
    if sealed["validation_errors"]:
        raise ValueError("round manifest refused: " + ", ".join(sealed["validation_errors"]))
    sealed["sealed"] = True
    sealed["manifest_hash"] = manifest_hash(sealed)
    return sealed


def prepare_round_manifest(
    manifest: Mapping[str, Any],
    *,
    registered_runners: Iterable[str],
) -> dict[str, Any]:
    """Label incomplete input without sealing it or exposing any result."""
    sealed = dict(manifest)
    reasons = validate_round_manifest(sealed, registered_runners=registered_runners)
    sealed["round_type"] = "complete_round" if not reasons else "limited_probe"
    sealed["validation_errors"] = reasons
    return sealed


def verify_resume(manifest: Mapping[str, Any], expected_hash: str) -> None:
    if manifest.get("manifest_hash") != expected_hash or manifest_hash(manifest) != expected_hash:
        raise ValueError("manifest_hash_mismatch")


def reconcile_round(
    manifest: Mapping[str, Any],
    stage2: Mapping[str, Mapping[str, Any]],
    stage3: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    expected_hash = str(manifest.get("manifest_hash", ""))
    verify_resume(manifest, expected_hash)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for candidate in manifest["candidates"]:
        candidate_id = candidate["candidate_id"]
        s2 = stage2.get(candidate_id)
        if not s2 or s2.get("manifest_hash") != expected_hash or s2.get("status") not in STAGE2_TERMINAL:
            errors.append(f"{candidate_id}:missing_or_invalid_stage2_terminal")
            continue
        s3 = stage3.get(candidate_id)
        if s2["status"] == "pass":
            if not s3 or s3.get("manifest_hash") != expected_hash or s3.get("status") not in STAGE3_TERMINAL:
                errors.append(f"{candidate_id}:missing_or_invalid_stage3_terminal")
                continue
        elif s3 is not None:
            errors.append(f"{candidate_id}:unexpected_stage3_for_stage2_{s2['status']}")
            continue
        rows.append({"candidate_id": candidate_id, "stage2": s2["status"], "stage3": s3["status"] if s3 else "not_run"})
    if errors:
        raise ValueError("round reconciliation failed: " + ", ".join(errors))
    return {
        "manifest_hash": expected_hash,
        "round_type": manifest["round_type"],
        "candidate_count": len(rows),
        "candidates": rows,
    }
