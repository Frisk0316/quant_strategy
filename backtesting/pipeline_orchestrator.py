"""Minimal driver for advisory research-pipeline sidecars."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from backtesting.pipeline_checkpoint1 import evaluate_checkpoint1_result, evaluate_summary
from backtesting.pipeline_checkpoint1 import result_to_dict as checkpoint1_to_dict
from backtesting.pipeline_feasibility import evaluate_stage2_result
from backtesting.pipeline_feasibility import result_to_dict as stage2_to_dict
from backtesting.pipeline_stage2_registry import (
    STAGE2_PROBES,
    Stage2Probe,
    require_statistical_power_inputs,
)
from backtesting.pipeline_stage3_registry import STAGE3_RUNNERS, Stage3Runner

SCHEMA_VERSION = 1
EXPERIMENT_REGISTRY_PATH = Path("docs/EXPERIMENT_REGISTRY.md")

ACTIVE_STATUSES = {"idea_registered", "stage2_pass", "stage3_done"}
NOOP_STATUSES = {
    "awaiting_stage2_implementation",
    "stage2_fail",
    "stage2_pass_on_reprobe",
    "awaiting_stage3_implementation",
    "checkpoint1_pass",
    "checkpoint1_fail",
    "checkpoint1_needs_human",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slash(path: Path) -> str:
    return str(path).replace("\\", "/")


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return _slash(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(dict(payload)), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def derive_candidate_dir(provisional_candidate_id: str) -> str:
    slug = provisional_candidate_id
    for prefix in ("B-", "A-"):
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
            break
    return slug.replace("-", "_")


def _source(value: Any) -> str:
    if value in {"taxonomy", "B_taxonomy"}:
        return "taxonomy"
    if value in {"literature", "A_literature"}:
        return "literature"
    return "mixed"


def _set_status(candidate: MutableMapping[str, Any], status: str, *, at: str | None = None) -> bool:
    if candidate.get("status") == status:
        return False
    candidate["status"] = status
    candidate.setdefault("status_history", []).append({"status": status, "at": at or _now()})
    return True


def _latest_status(candidate: Mapping[str, Any]) -> str:
    history = candidate.get("status_history")
    if isinstance(history, list) and history and isinstance(history[-1], Mapping):
        return str(history[-1].get("status") or "")
    return str(candidate.get("status") or "")


def _append_status(candidate: MutableMapping[str, Any], status: str) -> None:
    candidate["status"] = status
    candidate.setdefault("status_history", []).append({"status": status, "at": _now()})


def _candidate_statistical_power(context: Mapping[str, Any], candidate_id: str) -> dict[str, Any]:
    by_candidate = context.get("statistical_power_inputs")
    payload = by_candidate.get(candidate_id) if isinstance(by_candidate, Mapping) else None
    return require_statistical_power_inputs(
        payload,
        label=f"statistical power inputs for candidate {candidate_id!r}",
    )


def _stage2_metrics(payload: Mapping[str, Any]) -> dict[str, Any]:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return {}
    return {
        str(check.get("name")): {
            "status": check.get("status"),
            "reason": check.get("reason"),
            "details": check.get("details", {}),
        }
        for check in checks
        if isinstance(check, Mapping)
    }


def pre_register_batch(
    idea_batch: Mapping[str, Any],
    *,
    hypothesis_ids: Mapping[str, str],
    batch_id: str,
    max_runtime_seconds: int,
    created_at: str | None = None,
) -> dict[str, Any]:
    candidates_payload = idea_batch.get("candidates")
    if not isinstance(candidates_payload, list):
        raise ValueError("idea_batch['candidates'] must be a list")
    if len(candidates_payload) > 15:
        raise ValueError("idea_batch candidate cap is 15")

    timestamp = created_at or _now()
    candidates: list[dict[str, Any]] = []
    for candidate in candidates_payload:
        if not isinstance(candidate, Mapping):
            raise ValueError("idea_batch candidates must be objects")
        candidate_id = _required_text(
            candidate.get("candidate_id") or candidate.get("provisional_candidate_id"),
            "candidate_id",
        )
        hypothesis_id = hypothesis_ids.get(candidate_id)
        if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
            raise ValueError(f"missing hypothesis_id for candidate {candidate_id!r}")
        family_id = str(candidate.get("family_id") or candidate.get("family_id_or_NEW") or "NEW").strip() or "NEW"
        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_dir": derive_candidate_dir(candidate_id),
                "family_id": family_id,
                "hypothesis_id": hypothesis_id.strip(),
                "status": "idea_registered",
                "status_history": [{"status": "idea_registered", "at": timestamp}],
                "stage2_feasibility_path": None,
                "summary_path": None,
                "checkpoint1_auto_path": None,
                "feedback_spawned": bool(candidate.get("feedback_spawned", False)),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "created_at": timestamp,
        "source": _source(idea_batch.get("source")),
        "max_runtime_seconds": int(max_runtime_seconds),
        "candidates": candidates,
    }


async def advance_candidate(
    candidate: MutableMapping[str, Any],
    *,
    conn: Any,
    context: Mapping[str, Any],
    stage2_probes: Mapping[str, Stage2Probe],
    stage3_runners: Mapping[str, Stage3Runner],
    registry_text: str,
) -> None:
    status = str(candidate.get("status") or "")
    if status in NOOP_STATUSES:
        return

    output_root = Path(context["output_root"])
    batch_id = str(context["batch_id"])
    candidate_dir = str(candidate["candidate_dir"])
    candidate_root = output_root / batch_id / candidate_dir
    ctx = {
        **dict(context),
        "candidate_id": candidate["candidate_id"],
        "candidate_dir": candidate_dir,
        "family_id": candidate["family_id"],
        "hypothesis_id": candidate["hypothesis_id"],
    }

    if status == "idea_registered":
        probe = stage2_probes.get(str(candidate["family_id"]))
        if probe is None:
            _set_status(candidate, "awaiting_stage2_implementation")
            return
        ctx["statistical_power"] = _candidate_statistical_power(ctx, str(candidate["candidate_id"]))
        result = await probe(conn, ctx)
        stage2_path = candidate_root / "stage2_feasibility.json"
        _write_json(stage2_path, stage2_to_dict(result))
        candidate["stage2_feasibility_path"] = _slash(stage2_path)
        _set_status(candidate, "stage2_fail" if evaluate_stage2_result(result) == "FAIL" else "stage2_pass")
        return

    if status == "stage2_pass":
        runner = stage3_runners.get(str(candidate["family_id"]))
        if runner is None:
            _set_status(candidate, "awaiting_stage3_implementation")
            return
        summary = runner(ctx)
        summary_path = candidate_root / "summary.json"
        _write_json(summary_path, summary)
        candidate["summary_path"] = _slash(summary_path)
        _set_status(candidate, "stage3_done")
        return

    if status == "stage3_done":
        summary_path_value = candidate.get("summary_path")
        if not summary_path_value:
            raise ValueError(f"candidate {candidate['candidate_id']!r} has no summary_path")
        summary_path = Path(str(summary_path_value))
        summary = _read_json(summary_path)
        checkpoint = evaluate_summary(summary, registry_text, summary_path=summary_path)
        payload = checkpoint1_to_dict(checkpoint)
        checkpoint_path = candidate_root / "checkpoint1_auto.json"
        _write_json(checkpoint_path, payload)
        candidate["checkpoint1_auto_path"] = _slash(checkpoint_path)
        candidate["checkpoint1_auto_status"] = payload["checkpoint1_auto_status"]
        candidate["human_review_items"] = payload["human_review_items"]
        status_suffix = evaluate_checkpoint1_result(checkpoint).lower()
        _set_status(candidate, f"checkpoint1_{status_suffix}")


async def reprobe_stage2_failures(
    state: MutableMapping[str, Any],
    *,
    conn: Any,
    context: Mapping[str, Any],
    stage2_probes: Mapping[str, Stage2Probe],
) -> dict[str, Any]:
    advisory: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": state["batch_id"],
        "candidates": [],
    }
    output_root = Path(context["output_root"])
    for candidate in state.get("candidates", []):
        if not isinstance(candidate, MutableMapping) or _latest_status(candidate) != "stage2_fail":
            continue
        candidate_id = _required_text(candidate.get("candidate_id"), "candidate_id")
        family_id = _required_text(candidate.get("family_id"), "family_id")
        hypothesis_id_value = candidate.get("hypothesis_id")
        if not isinstance(hypothesis_id_value, str) or not hypothesis_id_value.strip():
            raise ValueError(f"missing hypothesis_id for candidate {candidate_id!r}")
        hypothesis_id = hypothesis_id_value.strip()
        candidate_dir = _required_text(candidate.get("candidate_dir"), f"{candidate_id} candidate_dir")
        stage2_path = Path(_required_text(candidate.get("stage2_feasibility_path"), f"{candidate_id} stage2_feasibility_path"))
        previous = _read_json(stage2_path)
        probe = stage2_probes.get(family_id)
        if probe is None:
            raise ValueError(f"missing Stage2 probe for family {family_id!r}")
        statistical_power = _candidate_statistical_power(context, candidate_id)
        current = _jsonable(
            stage2_to_dict(
                await probe(
                    conn,
                    {
                        **dict(context),
                        "candidate_id": candidate_id,
                        "candidate_dir": candidate_dir,
                        "family_id": family_id,
                        "hypothesis_id": hypothesis_id,
                        "statistical_power": statistical_power,
                    },
                )
            )
        )
        changed = current != previous
        current_status = str(current.get("stage2_status") or "")
        if changed:
            _append_status(candidate, "stage2_pass_on_reprobe" if current_status == "PASS" else "stage2_fail")
        advisory["candidates"].append(
            {
                "candidate_id": candidate_id,
                "family_id": family_id,
                "hypothesis_id": hypothesis_id,
                "stage2_feasibility_path": _slash(stage2_path),
                "previous_status": previous.get("stage2_status"),
                "current_status": current.get("stage2_status"),
                "previous_metrics": _stage2_metrics(previous),
                "current_metrics": _stage2_metrics(current),
                "changed": changed,
            }
        )
    _write_json(output_root / str(state["batch_id"]) / "reprobe_advisory.json", advisory)
    return advisory


def render_shortlist(state: Mapping[str, Any]) -> str:
    lines = [
        f"# Batch `{state['batch_id']}` Orchestrator Shortlist",
        "",
        "- Generated by: `scripts/run_pipeline_orchestrator.py`",
        f"- Candidates: {len(state.get('candidates', []))}",
        "",
        "| Candidate | Family | Hypothesis | Final status | Checkpoint1 auto status | Human review items |",
        "|---|---|---|---|---|---|",
    ]
    for candidate in state.get("candidates", []):
        status = candidate.get("status", "")
        checkpoint = candidate.get("checkpoint1_auto_status") if str(status).startswith("checkpoint1_") else "n/a"
        review_items = candidate.get("human_review_items")
        if status == "awaiting_stage2_implementation":
            review = "Ask Codex to implement Stage2 probe"
        elif status == "awaiting_stage3_implementation":
            review = "Ask Codex to implement Stage3 runner"
        elif isinstance(review_items, list) and review_items:
            review = ", ".join(str(item) for item in review_items)
        else:
            review = "n/a"
        lines.append(
            "| {candidate_id} | {family_id} | {hypothesis_id} | {status} | {checkpoint} | {review} |".format(
                candidate_id=candidate.get("candidate_id", ""),
                family_id=candidate.get("family_id", ""),
                hypothesis_id=candidate.get("hypothesis_id", ""),
                status=status,
                checkpoint=checkpoint,
                review=review,
            )
        )
    return "\n".join(lines) + "\n"


def _orchestrator_funnel_metrics(state: Mapping[str, Any]) -> dict[str, Any]:
    candidates = [row for row in state.get("candidates", []) if isinstance(row, Mapping)]

    def has_status(candidate: Mapping[str, Any], status: str) -> bool:
        history = candidate.get("status_history")
        if isinstance(history, list):
            return any(isinstance(row, Mapping) and row.get("status") == status for row in history)
        return candidate.get("status") == status

    latest = [_latest_status(candidate) for candidate in candidates]
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": state.get("batch_id"),
        "driver": "orchestrator",
        "selected": len(candidates),
        "stage2_pass": sum(
            1
            for candidate in candidates
            if has_status(candidate, "stage2_pass") or has_status(candidate, "stage2_pass_on_reprobe")
        ),
        "stage2_fail": sum(1 for status in latest if status == "stage2_fail"),
        "stage3_done": sum(1 for candidate in candidates if has_status(candidate, "stage3_done")),
        "stage3_awaiting_implementation": sum(1 for status in latest if status == "awaiting_stage3_implementation"),
        "checkpoint1_pass": sum(1 for status in latest if status == "checkpoint1_pass"),
        "checkpoint1_fail": sum(1 for status in latest if status == "checkpoint1_fail"),
        "checkpoint1_needs_human": sum(1 for status in latest if status == "checkpoint1_needs_human"),
        "feedback_spawned": sum(1 for candidate in candidates if candidate.get("feedback_spawned") is True),
    }


def _write_funnel_metrics(batch_dir: Path, state: Mapping[str, Any]) -> None:
    _write_json(batch_dir / "funnel_metrics.json", _orchestrator_funnel_metrics(state))


async def _connect(dsn: str) -> Any:
    import asyncpg

    return await asyncpg.connect(dsn)


async def run_orchestrator(
    *,
    idea_batch_path: Path | None,
    hypothesis_ids_path: Path | None,
    batch_id: str,
    max_runtime_seconds: int,
    output_root: Path,
    dsn: str,
    universe_path: Path,
    start: str,
    end_exclusive: str,
    power_inputs: Mapping[str, Any] | None = None,
    reprobe: bool = False,
) -> Path:
    batch_dir = output_root / batch_id
    state_path = batch_dir / "orchestrator_state.json"
    if state_path.exists():
        state = _read_json(state_path)
    else:
        if idea_batch_path is None or hypothesis_ids_path is None:
            raise ValueError("--idea-batch-path and --hypothesis-ids are required unless --reprobe uses existing state")
        state = pre_register_batch(
            _read_json(idea_batch_path),
            hypothesis_ids=_read_json(hypothesis_ids_path),
            batch_id=batch_id,
            max_runtime_seconds=max_runtime_seconds,
        )
        _write_json(state_path, state)

    conn = await _connect(dsn)
    started = time.monotonic()
    try:
        context = {
            "batch_id": batch_id,
            "output_root": output_root,
            "dsn": dsn,
            "universe_path": universe_path,
            "start": _utc(start),
            "end": _utc(end_exclusive),
            "statistical_power_inputs": power_inputs or {},
        }
        if reprobe:
            advisory = await reprobe_stage2_failures(state, conn=conn, context=context, stage2_probes=STAGE2_PROBES)
            if any(row.get("changed") for row in advisory["candidates"]):
                _write_json(state_path, state)
            _write_funnel_metrics(batch_dir, state)
            return state_path

        registry_text = EXPERIMENT_REGISTRY_PATH.read_text(encoding="utf-8")
        # ponytail: at most three mechanical stages; no scheduler until batches need one.
        for _ in range(3):
            changed = False
            for candidate in state["candidates"]:
                before = json.dumps(candidate, sort_keys=True)
                if time.monotonic() - started >= max_runtime_seconds:
                    break
                await advance_candidate(
                    candidate,
                    conn=conn,
                    context=context,
                    stage2_probes=STAGE2_PROBES,
                    stage3_runners=STAGE3_RUNNERS,
                    registry_text=registry_text,
                )
                changed = changed or before != json.dumps(candidate, sort_keys=True)
                _write_json(state_path, state)
            if not changed:
                break
    finally:
        close = getattr(conn, "close", None)
        if close is not None:
            await close()

    (batch_dir / "shortlist.md").write_text(render_shortlist(state), encoding="utf-8")
    _write_funnel_metrics(batch_dir, state)
    _write_json(state_path, state)
    return state_path
