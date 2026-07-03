"""Summarize research-pipeline funnel metrics across idea batches."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", default="results")
    parser.add_argument("--output", type=Path, help="Optional markdown output path")
    args = parser.parse_args(argv)

    table = render_markdown(collect_metrics(args.results_root))
    print(table, end="")
    if args.output:
        args.output.write_text(table, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
