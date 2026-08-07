"""ADR-0016 result-blind round manifest and reconciliation helpers."""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import math
from collections.abc import Awaitable, Callable, Iterable, Mapping
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

COUNTED_STATUSES = {"ready", "execution_ready"}
TRACKS = {"new_research", "existing_iteration"}
STAGE2_TERMINAL = {"pass", "fail", "error"}
STAGE3_TERMINAL = {"pass", "fail", "error"}

DatasetQuery = Callable[
    [str, Mapping[str, Any]],
    Mapping[str, Any] | None | Awaitable[Mapping[str, Any] | None],
]


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


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number > 0.0 else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contained_artifact(path_value: Any, artifact_root: Path) -> Path | None:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    root = artifact_root.resolve()
    path = Path(path_value)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def _prepare_i68_fields(
    manifest: Mapping[str, Any],
    *,
    artifact_root: Path,
) -> tuple[dict[str, Any], dict[int, list[str]]]:
    prepared = copy.deepcopy(dict(manifest))
    candidates = prepared.get("candidates")
    errors: dict[int, list[str]] = {}
    if not isinstance(candidates, list):
        return prepared, errors

    for index, row in enumerate(candidates):
        if not isinstance(row, dict):
            continue
        row.pop("counted", None)
        row.pop("execution_readiness_errors", None)
        row.pop("breadth_coercion", None)

        gross = _positive_number(row.get("expected_gross_capture_bps"))
        cost = _positive_number(row.get("modeled_cost_bps"))
        row["gross_over_cost"] = gross / cost if gross is not None and cost is not None else None

        declared_value = row.get("breadth")
        declared = _positive_number(declared_value)
        provenance = row.get("breadth_provenance")
        if not isinstance(provenance, Mapping):
            provenance = row.get("breadth_artifact")
        reason = "missing_breadth_derivation"
        verified = False
        if isinstance(provenance, Mapping):
            artifact = _contained_artifact(provenance.get("path"), artifact_root)
            expected = provenance.get("sha256")
            if artifact is None:
                reason = "invalid_breadth_artifact_path"
            elif not isinstance(expected, str) or len(expected) != 64:
                reason = "invalid_breadth_artifact_sha256"
            elif not artifact.is_file():
                reason = "missing_breadth_artifact"
            elif _sha256(artifact) != expected.lower():
                reason = "breadth_artifact_sha256_mismatch"
            else:
                verified = True
        if declared is None:
            reason = "invalid_breadth"
            verified = False
        if verified:
            row["breadth"] = declared
            row["breadth_provenance"] = dict(provenance)
            row["breadth_provenance"]["sha256_verified"] = True
        else:
            row["breadth"] = 1.0
            row["breadth_coercion"] = {
                "declared": declared_value,
                "used": 1.0,
                "reason": reason,
            }
            errors.setdefault(index, []).append(reason)
    return prepared, errors


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _dataset_name(claim: Mapping[str, Any], index: int) -> str:
    return str(claim.get("dataset_id") or claim.get("name") or f"dataset[{index}]").strip()


async def query_dataset_claim(conn: Any, claim: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the live row count for one allow-listed DB dataset and half-open window."""
    locator = str(claim.get("locator") or "").strip()
    dataset_id = str(claim.get("dataset_id") or "").strip()
    start = _timestamp(claim.get("start"))
    end = _timestamp(claim.get("end"))
    if not dataset_id or start is None or end is None:
        raise ValueError("dataset_id, start, and end are required")

    if locator == "external_observations":
        row = await conn.fetchrow(
            """
            SELECT COUNT(*)::bigint AS row_count
            FROM external_observations
            WHERE dataset_id = $1 AND observed_at >= $2 AND observed_at < $3
            """,
            dataset_id,
            start,
            end,
        )
    elif locator == "canonical_candles":
        bar = claim.get("bar")
        if bar:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*)::bigint AS row_count
                FROM canonical_candles
                WHERE inst_id = $1 AND bar = $2 AND ts >= $3 AND ts < $4
                """,
                dataset_id,
                str(bar),
                start,
                end,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*)::bigint AS row_count
                FROM canonical_candles
                WHERE inst_id = $1 AND ts >= $2 AND ts < $3
                """,
                dataset_id,
                start,
                end,
            )
    elif locator == "funding_rates":
        source = claim.get("source")
        if source:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*)::bigint AS row_count
                FROM funding_rates
                WHERE inst_id = $1 AND source = $2 AND ts >= $3 AND ts < $4
                """,
                dataset_id,
                str(source),
                start,
                end,
            )
        else:
            row = await conn.fetchrow(
                """
                SELECT COUNT(*)::bigint AS row_count
                FROM funding_rates
                WHERE inst_id = $1 AND ts >= $2 AND ts < $3
                """,
                dataset_id,
                start,
                end,
            )
    else:
        raise ValueError(f"unsupported dataset locator: {locator!r}")
    return {
        "row_count": int(row["row_count"]) if row else 0,
        "start": start,
        "end": end,
    }


async def _query_dataset_dsn(dsn: str, claim: Mapping[str, Any]) -> Mapping[str, Any]:
    import asyncpg

    conn = await asyncpg.connect(dsn, server_settings={"default_transaction_read_only": "on"})
    try:
        return await query_dataset_claim(conn, claim)
    finally:
        await conn.close()


async def _run_dataset_query(query: DatasetQuery, dsn: str, claim: Mapping[str, Any]) -> Mapping[str, Any] | None:
    result = query(dsn, claim)
    if inspect.isawaitable(result):
        result = await result
    return result


async def _validate_prepared_manifest(
    manifest: Mapping[str, Any],
    *,
    registered_runners: Iterable[str],
    dsn: str | None,
    dataset_query: DatasetQuery,
    initial_errors: Mapping[int, list[str]],
) -> tuple[list[str], set[int], dict[int, list[str]]]:
    candidates = manifest.get("candidates")
    if not isinstance(candidates, list):
        return ["candidates_not_list"], set(), {}

    reasons: list[str] = []
    invalid: set[int] = set(initial_errors)
    per_candidate = {index: list(values) for index, values in initial_errors.items()}
    count = len(candidates)
    if not 10 <= count <= 15:
        reasons.append("candidate_count_outside_10_15")

    ids = [str(row.get("candidate_id", "")).strip() for row in candidates if isinstance(row, Mapping)]
    families = [str(row.get("family_id", "")).strip() for row in candidates if isinstance(row, Mapping)]
    if len(ids) != count or any(not value for value in ids) or len(set(ids)) != count:
        reasons.append("duplicate_or_missing_candidate_id")
        invalid.update(range(count))
    if len(families) != count or any(not value for value in families) or len(set(families)) != count:
        reasons.append("duplicate_or_missing_family")
        invalid.update(range(count))

    runners = set(registered_runners)
    if not dsn:
        reasons.append("dsn_required")
        invalid.update(range(count))

    def reject(index: int, candidate_id: str, reason: str) -> None:
        reasons.append(f"{candidate_id}:{reason}")
        invalid.add(index)
        per_candidate.setdefault(index, []).append(reason)

    for index, row in enumerate(candidates):
        if not isinstance(row, Mapping):
            reasons.append("candidate_not_object")
            invalid.add(index)
            continue
        candidate_id = str(row.get("candidate_id") or f"candidate[{index}]")
        track = row.get("track")
        if track not in TRACKS:
            reject(index, candidate_id, "invalid_track")
        if row.get("draft_status") == "pending_llm":
            reject(index, candidate_id, "pending_llm")
        if row.get("execution_status") not in COUNTED_STATUSES:
            reject(index, candidate_id, "not_execution_ready")
        if row.get("runner") not in runners:
            reject(index, candidate_id, "runner_not_registered")
        if track == "new_research" and not row.get("verified_paper"):
            reject(index, candidate_id, "paper_not_verified")
        if track == "existing_iteration" and not row.get("iteration_rationale"):
            reject(index, candidate_id, "missing_iteration_rationale")

        gross = _positive_number(row.get("expected_gross_capture_bps"))
        cost = _positive_number(row.get("modeled_cost_bps"))
        provenance = row.get("gross_estimate_provenance")
        if gross is None:
            reject(index, candidate_id, "missing_or_invalid_expected_gross_capture_bps")
        if cost is None:
            reject(index, candidate_id, "missing_or_invalid_modeled_cost_bps")
        if not isinstance(provenance, str) or not provenance.strip() or "\n" in provenance or "\r" in provenance:
            reject(index, candidate_id, "missing_or_invalid_gross_estimate_provenance")
        for reason in initial_errors.get(index, []):
            reasons.append(f"{candidate_id}:{reason}")

        datasets = row.get("datasets")
        if not isinstance(datasets, list) or not datasets:
            reject(index, candidate_id, "missing_dataset_claims")
            continue
        for dataset_index, claim in enumerate(datasets):
            if not isinstance(claim, Mapping):
                reject(index, candidate_id, f"dataset[{dataset_index}]:invalid_claim")
                continue
            name = _dataset_name(claim, dataset_index)
            claimed_count = claim.get("row_count")
            claimed_start = _timestamp(claim.get("start"))
            claimed_end = _timestamp(claim.get("end"))
            if (
                isinstance(claimed_count, bool)
                or not isinstance(claimed_count, int)
                or claimed_count <= 0
                or claimed_start is None
                or claimed_end is None
                or claimed_start >= claimed_end
            ):
                reject(index, candidate_id, f"{name}:missing_or_invalid_dataset_numbers")
                continue
            if not dsn:
                continue
            try:
                observed = await _run_dataset_query(dataset_query, dsn, claim)
            except Exception as exc:
                reject(index, candidate_id, f"{name}:dataset_query_failed_{type(exc).__name__}")
                continue
            if not isinstance(observed, Mapping):
                reject(index, candidate_id, f"{name}:dataset_missing")
                continue
            observed_count = observed.get("row_count")
            observed_start = _timestamp(observed.get("start"))
            observed_end = _timestamp(observed.get("end"))
            if not isinstance(observed_count, int) or isinstance(observed_count, bool) or observed_count <= 0:
                reject(index, candidate_id, f"{name}:dataset_missing")
                continue
            if observed_count != claimed_count:
                reject(index, candidate_id, f"{name}:dataset_row_count_mismatch")
            if observed_start != claimed_start or observed_end != claimed_end:
                reject(index, candidate_id, f"{name}:dataset_range_mismatch")

    counted = [index for index in range(count) if index not in invalid]
    if not 10 <= len(counted) <= 15:
        reasons.append("execution_ready_candidate_count_outside_10_15")
    new_count = sum(candidates[index].get("track") == "new_research" for index in counted)
    iteration_count = sum(candidates[index].get("track") == "existing_iteration" for index in counted)
    if new_count < 8:
        reasons.append("new_research_count_below_8")
    if iteration_count < 2:
        reasons.append("existing_iteration_count_below_2")
    return reasons, invalid, per_candidate


async def validate_round_manifest(
    manifest: Mapping[str, Any],
    *,
    registered_runners: Iterable[str],
    dsn: str | None = None,
    dataset_query: DatasetQuery | None = None,
    artifact_root: Path = Path("."),
) -> list[str]:
    prepared, initial_errors = _prepare_i68_fields(manifest, artifact_root=artifact_root)
    reasons, _, _ = await _validate_prepared_manifest(
        prepared,
        registered_runners=registered_runners,
        dsn=dsn,
        dataset_query=dataset_query or _query_dataset_dsn,
        initial_errors=initial_errors,
    )
    return reasons


async def seal_round_manifest(
    manifest: Mapping[str, Any],
    *,
    registered_runners: Iterable[str],
    dsn: str | None = None,
    dataset_query: DatasetQuery | None = None,
    artifact_root: Path = Path("."),
) -> dict[str, Any]:
    sealed = await prepare_round_manifest(
        manifest,
        registered_runners=registered_runners,
        dsn=dsn,
        dataset_query=dataset_query,
        artifact_root=artifact_root,
    )
    if sealed["validation_errors"]:
        raise ValueError("round manifest refused: " + ", ".join(sealed["validation_errors"]))
    sealed["sealed"] = True
    sealed["manifest_hash"] = manifest_hash(sealed)
    return sealed


async def prepare_round_manifest(
    manifest: Mapping[str, Any],
    *,
    registered_runners: Iterable[str],
    dsn: str | None = None,
    dataset_query: DatasetQuery | None = None,
    artifact_root: Path = Path("."),
) -> dict[str, Any]:
    """Label incomplete input without sealing it or exposing any result."""
    prepared, initial_errors = _prepare_i68_fields(manifest, artifact_root=artifact_root)
    reasons, invalid, per_candidate = await _validate_prepared_manifest(
        prepared,
        registered_runners=registered_runners,
        dsn=dsn,
        dataset_query=dataset_query or _query_dataset_dsn,
        initial_errors=initial_errors,
    )
    candidates = prepared.get("candidates")
    if isinstance(candidates, list):
        for index, row in enumerate(candidates):
            if isinstance(row, dict):
                row["counted"] = index not in invalid
                row["execution_readiness_errors"] = per_candidate.get(index, [])
        prepared["counted_candidate_count"] = len(candidates) - len(invalid)
    prepared["round_type"] = "complete_round" if not reasons else "limited_probe"
    prepared["validation_errors"] = reasons
    return prepared


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
