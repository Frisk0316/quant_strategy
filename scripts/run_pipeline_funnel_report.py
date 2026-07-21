"""Summarize research-pipeline funnel metrics across idea batches."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.pipeline_checkpoint1 import family_registry_from_text
from backtesting.pipeline_idea_generator import _rows as hypothesis_rows


COLUMNS = (
    "batch_id",
    "driver",
    "fetched",
    "scored",
    "above_threshold",
    "selected",
    "stage2_pass",
    "stage2_fail",
    "stage3_done",
)

_STAGE3_METRIC_RE = re.compile(
    r"\b(?P<name>WF|CPCV|DSR|PSR)"
    r"(?:\s+(?:combined\s+)?OOS)?(?:\s+Sharpe)?"
    r"(?:\s*=\s*PSR)?\s*(?:=|:)?\s*~?"
    r"(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
    re.IGNORECASE,
)


def _skip_counts(skipped: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("reason") or "unknown") for row in skipped if isinstance(row, Mapping)))


def idea_batch_funnel_metrics(
    payload: Mapping[str, Any],
    *,
    fetched: int | None = None,
    scored: int | None = None,
    above_threshold: int | None = None,
    driver: str = "idea_batch",
) -> dict[str, Any]:
    skipped = payload.get("skipped") if isinstance(payload.get("skipped"), list) else []
    selected = int(payload.get("n_selected") or len(payload.get("candidates") or []))
    eligible = int(payload.get("n_eligible_before_cap") or selected)
    return {
        "schema_version": 1,
        "batch_id": payload.get("batch_id"),
        "driver": driver,
        "fetched": fetched if fetched is not None else selected + len(skipped),
        "scored": scored if scored is not None else None,
        "above_threshold": above_threshold if above_threshold is not None else eligible,
        "selected": selected,
        "skipped": _skip_counts(skipped),
    }


def write_funnel_metrics(batch_dir: str | Path, metrics: Mapping[str, Any]) -> Path:
    path = Path(batch_dir) / "funnel_metrics.json"
    path.write_text(json.dumps(dict(metrics), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_batch_metrics(batch_dir: Path) -> dict[str, Any]:
    path = batch_dir / "funnel_metrics.json"
    if not path.exists():
        return {"batch_id": batch_dir.name, "driver": "n/a", "missing_metrics": True}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    payload.setdefault("batch_id", batch_dir.name)
    payload["missing_metrics"] = False
    return payload


def collect_metrics(results_root: str | Path) -> list[dict[str, Any]]:
    root = Path(results_root)
    return [load_batch_metrics(path) for path in sorted(root.glob("idea_batch_*")) if path.is_dir()]


def _named_check_status(payload: Mapping[str, Any], name: str) -> bool | None:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return None
    for check in checks:
        if isinstance(check, Mapping) and check.get("name") == name:
            return str(check.get("status") or "").upper() == "PASS"
    return None


def _data_feasible(payload: Mapping[str, Any]) -> bool:
    canonical = _named_check_status(payload, "data_availability")
    if canonical is not None:
        return canonical
    probe = payload.get("probe")
    if isinstance(probe, Mapping) and "status" in probe:
        return str(probe.get("status") or "").upper() == "PASS"
    verdict = payload.get("verdict")
    return (
        str(payload.get("probe_status") or "").upper() == "COMPLETE"
        and isinstance(verdict, Mapping)
        and str(verdict.get("status") or "").upper() == "PASS"
    )


def _stage2_candidates(
    results_root: str | Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], int, list[dict[str, str]]]:
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    paths = sorted(Path(results_root).rglob("stage2_feasibility.json"))
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise ValueError(f"{path} must contain a JSON object")
        except (OSError, ValueError) as exc:
            errors.append(
                {
                    "path": str(path).replace("\\", "/"),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        hypothesis_id = str(payload.get("hypothesis_id") or "").strip()
        family_id = str(payload.get("family_id") or "").strip()
        if not hypothesis_id or not family_id:
            continue
        row = candidates.setdefault(
            (hypothesis_id, family_id),
            {
                "hypothesis_id": hypothesis_id,
                "family_id": family_id,
                "data_feasible": False,
                "power_feasible": False,
            },
        )
        row["data_feasible"] = row["data_feasible"] or _data_feasible(payload)
        row["power_feasible"] = row["power_feasible"] or bool(
            _named_check_status(payload, "statistical_power")
        )
    return candidates, len(paths), errors


def _registry_experiment_rows(registry_text: str) -> list[dict[str, Any]]:
    rows = []
    for line in registry_text.splitlines():
        if not line.startswith("| E-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 9:
            continue
        match = re.match(r"(\d+)\b", cells[5])
        rows.append(
            {
                "id": cells[0],
                "date": cells[1],
                "hypothesis_id": cells[2],
                "family_id": cells[3],
                "setup": cells[4],
                "trials": int(match.group(1)) if match else 0,
                "artifact": cells[6],
                "outcome": cells[7],
                "notes": " | ".join(cells[8:]),
            }
        )
    return rows


def _is_stage3_run(row: Mapping[str, Any]) -> bool:
    artifact_and_outcome = f"{row['artifact']} {row['outcome']}".lower()
    return (
        int(row["trials"]) > 0
        and "summary.json" in str(row["artifact"]).lower()
        and not re.search(
            r"\b(?:planned|pending|invalid|superseded|data[-_]blocked|stage2[-_]fail(?:ed)?|fail[-_]closed)\b",
            artifact_and_outcome,
        )
    )


def _gate_passed(row: Mapping[str, Any]) -> bool:
    text = f"{row['outcome']} {row['notes']}".lower()
    compact = text.replace("`", "").replace(" ", "")
    return "statistical-pass" in text or "statistical_gate_passed:true" in compact


def _stage3_metrics(row: Mapping[str, Any] | None) -> dict[str, float | None]:
    metrics = {name: None for name in ("wf", "cpcv", "dsr", "psr")}
    if row is None:
        return metrics
    for match in _STAGE3_METRIC_RE.finditer(str(row["notes"])):
        name = match.group("name").lower()
        value = float(match.group("value"))
        if metrics[name] is None:
            metrics[name] = value
        if name == "dsr" and "PSR" in match.group(0).upper() and metrics["psr"] is None:
            metrics["psr"] = value
    return metrics


def collect_pipeline_funnel(
    results_root: str | Path,
    registry_path: str | Path,
    ledger_path: str | Path = ROOT / "docs" / "HYPOTHESIS_LEDGER.md",
) -> dict[str, Any]:
    candidates, artifact_count, artifact_errors = _stage2_candidates(results_root)
    registry_text = Path(registry_path).read_text(encoding="utf-8")
    ledger = {
        (row.get("ID"), row.get("Family ID")): row
        for row in hypothesis_rows(Path(ledger_path).read_text(encoding="utf-8"))
    }
    for hypothesis_id, family_id in ledger:
        if hypothesis_id and family_id:
            candidates.setdefault(
                (hypothesis_id, family_id),
                {
                    "hypothesis_id": hypothesis_id,
                    "family_id": family_id,
                    "data_feasible": False,
                    "power_feasible": False,
                },
            )

    stage3: dict[tuple[str, str], list[dict[str, Any]]] = {}
    stage3_by_family: dict[str, list[dict[str, Any]]] = {}
    experiments_by_family: dict[str, list[dict[str, str]]] = {}
    for row in _registry_experiment_rows(registry_text):
        key = (row["hypothesis_id"], row["family_id"])
        experiments_by_family.setdefault(row["family_id"], []).append(
            {field: row[field] for field in ("id", "date", "setup", "outcome", "notes")}
        )
        if _is_stage3_run(row):
            stage3.setdefault(key, []).append(row)
            stage3_by_family.setdefault(row["family_id"], []).append(row)

    family_registry = family_registry_from_text(registry_text)
    candidates_by_family: dict[str, list[tuple[tuple[str, str], dict[str, Any]]]] = {}
    for key, candidate in candidates.items():
        candidates_by_family.setdefault(candidate["family_id"], []).append((key, candidate))
    for family_id in family_registry:
        candidates_by_family.setdefault(family_id, [])

    families: list[dict[str, Any]] = []
    for family_id in sorted(candidates_by_family):
        entries = candidates_by_family[family_id]
        family_runs = stage3_by_family.get(family_id, [])
        if family_runs:
            selected_key = (family_runs[-1]["hypothesis_id"], family_id)
        elif entries:
            selected_key = max(
                (key for key, _candidate in entries),
                key=lambda key: int(key[0].removeprefix("H-")) if key[0].removeprefix("H-").isdigit() else -1,
            )
        else:
            selected_key = (None, family_id)
        hypothesis = ledger.get(selected_key, {})
        registry = family_registry.get(family_id)
        families.append(
            {
                "family_id": family_id,
                "hypothesis_id": hypothesis.get("ID", selected_key[0]),
                "status": hypothesis.get("Status"),
                "source": hypothesis.get("Source"),
                "hypothesis_text": hypothesis.get("Hypothesis (falsifiable)"),
                "experiments": sorted(
                    experiments_by_family.get(family_id, []),
                    key=lambda experiment: (experiment["date"], experiment["id"]),
                ),
                **_stage3_metrics(family_runs[-1] if family_runs else None),
                "n_trials": registry.cumulative_n_trials if registry else None,
                "k_used": registry.k_used if registry else None,
                "k_limit": registry.k_limit if registry else None,
                "candidates": len(entries),
                "data_feasible": sum(int(candidate["data_feasible"]) for _key, candidate in entries),
                "power_feasible": sum(int(candidate["power_feasible"]) for _key, candidate in entries),
                "stage3_run": sum(int(bool(stage3.get(key))) for key, _candidate in entries)
                or int(bool(family_runs)),
                "gate_pass": sum(
                    int(bool(stage3.get(key)) and _gate_passed(stage3[key][-1]))
                    for key, _candidate in entries
                )
                or int(bool(family_runs) and _gate_passed(family_runs[-1])),
            }
        )
    total_keys = ("candidates", "data_feasible", "power_feasible", "stage3_run", "gate_pass")
    totals = {key: sum(int(row[key]) for row in families) for key in total_keys}
    totals["k_spent"] = sum(int(row["k_used"] or 0) for row in families)
    return {
        "schema_version": 3,
        "stage2_artifacts_scanned": artifact_count,
        "stage2_artifact_errors": artifact_errors,
        "totals": totals,
        "families": families,
    }


def _cell(row: Mapping[str, Any], column: str) -> str:
    value = row.get(column)
    if value is None:
        return "n/a"
    return str(value)


def render_markdown(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "| " + " | ".join(COLUMNS) + " |",
        "| " + " | ".join("---" for _ in COLUMNS) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(row, column) for column in COLUMNS) + " |")
    return "\n".join(lines) + "\n"


def render_pipeline_markdown(report: Mapping[str, Any]) -> str:
    columns = (
        "family_id",
        "candidates",
        "data_feasible",
        "power_feasible",
        "stage3_run",
        "gate_pass",
        "K_spent",
    )
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in report.get("families", []):
        lines.append(
            "| "
            + " | ".join(
                (
                    str(row["family_id"]),
                    str(row["candidates"]),
                    str(row["data_feasible"]),
                    str(row["power_feasible"]),
                    str(row["stage3_run"]),
                    str(row["gate_pass"]),
                    f"{row['k_used']}/{row['k_limit']}",
                )
            )
            + " |"
        )
    totals = report["totals"]
    lines.append(
        "| TOTAL | "
        + " | ".join(
            str(totals[key])
            for key in ("candidates", "data_feasible", "power_feasible", "stage3_run", "gate_pass", "k_spent")
        )
        + " |"
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--output", type=Path, help="Optional markdown output path")
    parser.add_argument("--json-output", type=Path, help="Optional JSON output path")
    parser.add_argument("--registry", type=Path, default=ROOT / "docs" / "EXPERIMENT_REGISTRY.md")
    parser.add_argument("--ledger", type=Path, default=ROOT / "docs" / "HYPOTHESIS_LEDGER.md")
    args = parser.parse_args(argv)

    if any(Path(args.results_root).rglob("stage2_feasibility.json")):
        report = collect_pipeline_funnel(args.results_root, args.registry, args.ledger)
        json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        table = render_pipeline_markdown(report)
        print(json_text, end="")
        if args.json_output:
            args.json_output.write_text(json_text, encoding="utf-8")
    else:
        table = render_markdown(collect_metrics(args.results_root))
    print(table, end="")
    if args.output:
        args.output.write_text(table, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
