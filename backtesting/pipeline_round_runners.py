"""Reviewed ADR-0016 round runners backed by existing Stage-2 probes."""
from __future__ import annotations

import hashlib
import inspect
import json
import math
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from backtesting.pipeline_feasibility import result_to_dict
from backtesting.pipeline_stage2_registry import STAGE2_PROBES

REQUIRED_CHECKS = {"data_availability", "distinctness", "cost_after_edge", "statistical_power"}
BREADTH_FORMULAS = {
    "mean_nonzero_positions",
    "mean_d(count_i(abs(actual_position[d,i]) > 0)), aligned to daily return observations",
}

# Reviewed runner name -> existing Stage-2 family. Admission review adds exact entries; never discover them.
REVIEWED_ROUND_RUNNERS: dict[str, str] = {}
# Candidate-specific Stage-3 entries require a separate explicit user authorization.
AUTHORIZED_STAGE3_ROUND_RUNNERS: dict[str, Any] = {}


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp_required")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _artifact_path(value: Any, root: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("breadth_artifact_path_invalid")
    resolved_root = root.resolve()
    path = Path(value)
    resolved = path.resolve() if path.is_absolute() else (resolved_root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("breadth_artifact_path_invalid") from exc
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _field(payload: Any, pointer: Any) -> Any:
    if not isinstance(pointer, str) or not pointer.strip():
        raise ValueError("breadth_artifact_field_invalid")
    parts = pointer.lstrip("/").split("/") if pointer.startswith("/") else pointer.split(".")
    value = payload
    for raw_part in parts:
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise ValueError("breadth_artifact_field_invalid")
    return value


def _position_value(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError("breadth_position_invalid")
    return float(value)


def _position_counts(series: Any, start: datetime, end: datetime) -> list[int]:
    if isinstance(series, Mapping):
        rows = [{"ts": timestamp, "positions": positions} for timestamp, positions in series.items()]
    elif isinstance(series, list):
        rows = series
    else:
        raise ValueError("breadth_position_series_invalid")

    grouped: dict[datetime, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("breadth_position_series_invalid")
        observed_at = _timestamp(row.get("ts") or row.get("timestamp") or row.get("date") or row.get("day"))
        if not start <= observed_at < end:
            continue
        positions = row.get("positions") or row.get("weights") or row.get("actual_positions")
        if isinstance(positions, Mapping):
            grouped.setdefault(observed_at, {}).update(
                {str(symbol): _position_value(value) for symbol, value in positions.items()}
            )
            continue
        symbol = row.get("symbol")
        value = row.get("position", row.get("weight"))
        if not isinstance(symbol, str) or not symbol.strip() or value is None:
            raise ValueError("breadth_position_series_invalid")
        grouped.setdefault(observed_at, {})[symbol] = _position_value(value)
    return [sum(value != 0.0 for value in positions.values()) for _, positions in sorted(grouped.items())]


def _verify_breadth(candidate: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    candidate_id = str(candidate.get("candidate_id") or "candidate")
    declared = candidate.get("breadth")
    if (
        isinstance(declared, bool)
        or not isinstance(declared, (int, float))
        or not math.isfinite(float(declared))
        or float(declared) <= 0.0
    ):
        raise ValueError(f"breadth_declared_invalid:{candidate_id}")
    provenance = candidate.get("breadth_provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError(f"breadth_provenance_invalid:{candidate_id}")
    formula = provenance.get("formula")
    if formula not in BREADTH_FORMULAS:
        raise ValueError(f"breadth_formula_unsupported:{candidate_id}")
    window = provenance.get("window")
    if isinstance(window, Mapping):
        start_value, end_value = window.get("start"), window.get("end") or window.get("end_exclusive")
    elif isinstance(window, (list, tuple)) and len(window) == 2:
        start_value, end_value = window
    else:
        raise ValueError(f"breadth_window_invalid:{candidate_id}")
    start, end = _timestamp(start_value), _timestamp(end_value)
    if start >= end:
        raise ValueError(f"breadth_window_invalid:{candidate_id}")

    path = _artifact_path(provenance.get("path"), Path(context.get("artifact_root", ".")))
    expected_hash = provenance.get("sha256")
    if not path.is_file() or not isinstance(expected_hash, str) or _sha256(path) != expected_hash.lower():
        raise ValueError(f"breadth_artifact_sha256_mismatch:{candidate_id}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        counts = _position_counts(_field(payload, provenance.get("field")), start, end)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise ValueError(f"breadth_artifact_invalid:{candidate_id}") from exc
    n_obs = provenance.get("n_obs")
    if type(n_obs) is not int or n_obs <= 0 or n_obs != len(counts):
        raise ValueError(f"breadth_n_obs_mismatch:{candidate_id}")
    measured = sum(counts) / len(counts)
    recomputed = measured if measured > 0.0 else 1.0
    if abs(recomputed - float(declared)) > 1e-9:
        raise ValueError(f"breadth_recompute_mismatch:{candidate_id}")


def _stage2_context(candidate: Mapping[str, Any]) -> dict[str, Any]:
    window = candidate.get("window")
    if isinstance(window, (list, tuple)) and len(window) == 2:
        window = {"start": window[0], "end": window[1]}
    if not isinstance(window, Mapping):
        window = candidate.get("data")
    if not isinstance(window, Mapping):
        window = {}
    universe = candidate.get("universe")
    if isinstance(universe, Mapping):
        universe_path = universe.get("path")
    elif isinstance(universe, str):
        universe_path = universe
    else:
        universe_path = candidate.get("universe_path")
    power = candidate.get("statistical_power")
    if not isinstance(power, Mapping):
        power = candidate.get("power_inputs") or candidate.get("power")
    if not isinstance(power, Mapping):
        power = {
            key: candidate.get(key)
            for key in ("breadth", "n_obs", "n_trials", "plausible_net_sharpe")
        }
    start = window.get("start") or candidate.get("start")
    end = window.get("end") or window.get("end_exclusive") or candidate.get("end") or candidate.get("end_exclusive")
    ctx = dict(candidate)
    ctx.update(
        {
            "start": _timestamp(start),
            "end": _timestamp(end),
            "universe_path": Path(universe_path) if universe_path is not None else None,
            "statistical_power": dict(power),
        }
    )
    return ctx


def _connect(dsn: str) -> Any:
    import asyncpg

    return asyncpg.connect(dsn, server_settings={"default_transaction_read_only": "on"})


def stage2_round_runner(family_id: str):
    if family_id not in STAGE2_PROBES:
        raise ValueError(f"stage2_probe_not_registered:{family_id}")
    probe = STAGE2_PROBES[family_id]

    async def runner(candidate: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
        candidate_id = str(candidate.get("candidate_id") or "candidate")
        if candidate.get("family_id") != family_id:
            raise ValueError(f"round_runner_family_mismatch:{candidate_id}")
        _verify_breadth(candidate, context)
        connection = None
        error: Exception | None = None
        result = None
        try:
            dsn = context.get("dsn")
            if not isinstance(dsn, str) or not dsn:
                raise ValueError("dsn_required")
            connection = _connect(dsn)
            if inspect.isawaitable(connection):
                connection = await connection
            result = await probe(connection, _stage2_context(candidate))
        except Exception as exc:
            error = exc
        finally:
            close = getattr(connection, "close", None)
            if close is not None:
                try:
                    closed = close()
                    if inspect.isawaitable(closed):
                        await closed
                except Exception as exc:
                    error = error or exc
        if error is not None:
            return {"stage2": {"status": "error", "checks": [], "error": type(error).__name__}}
        checks = result_to_dict(result)["checks"]
        by_name = {check["name"]: check["status"] for check in checks}
        status = "pass" if all(by_name.get(name) == "PASS" for name in REQUIRED_CHECKS) else "fail"
        return {"stage2": {"status": status, "checks": checks}}

    return runner


def build_round_runners(reviewed: Mapping[str, str]) -> dict[str, Any]:
    runners: dict[str, Any] = {}
    for runner_name, family_id in reviewed.items():
        if (
            not isinstance(runner_name, str)
            or not runner_name.strip()
            or not isinstance(family_id, str)
            or not family_id.strip()
            or any(character in runner_name + family_id for character in "*?[]")
        ):
            raise ValueError("wildcard_round_runner_forbidden")
        runners[runner_name] = stage2_round_runner(family_id)
    return runners


ROUND_RUNNERS = build_round_runners(REVIEWED_ROUND_RUNNERS)
