"""Build the public research-status JSON from local files only."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKSTREAM_FIELDS = ("name", "status", "milestones", "current", "state", "next")
SHADOW_FIELDS = (
    "journal_weeks",
    "distinct_journal_weeks",
    "minimum_weeks",
    "eight_week_journal_met",
)


def _missing(path: Path) -> dict[str, Any]:
    return {"available": False, "reason": f"{path.name} not found"}


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data


def _workstreams(root: Path) -> list[dict[str, Any]] | dict[str, Any]:
    path = root / "config" / "workstreams.yaml"
    if not path.is_file():
        return _missing(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("workstreams") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ValueError("workstreams.yaml must contain a workstreams list")

    public = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each workstream must be an object")
        row = {field: entry.get(field) for field in WORKSTREAM_FIELDS}
        row["links"] = [
            PurePosixPath(str(link).replace("\\", "/")).name
            for link in (entry.get("links") or [])
        ]
        public.append(row)
    return public


def _shadow(root: Path) -> dict[str, Any]:
    directory = root / "results" / "shadow_h014"
    bias_path = directory / "bias_report.json"
    journal_path = directory / "journal.jsonl"
    for path in (bias_path, journal_path):
        if not path.is_file():
            return _missing(path)

    bias = _read_json(bias_path)
    criteria = bias.get("exit_criteria", bias)
    if not isinstance(criteria, dict):
        raise ValueError("bias_report.json exit_criteria must be an object")
    public = {"available": True}
    public.update({field: criteria[field] for field in SHADOW_FIELDS if field in criteria})
    if "generated_at" in bias:
        public["generated_at"] = bias["generated_at"]

    counts: Counter[str] = Counter()
    total = 0
    last_event_date = None
    for line in journal_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("journal.jsonl lines must contain JSON objects")
        total += 1
        if event.get("status") is not None:
            counts[str(event["status"])] += 1
        last_event_date = event.get("event_date")
    public["event_counts"] = {
        "total": total,
        "by_status": dict(sorted(counts.items())),
        "last_event_date": last_event_date,
    }
    return public


def _research_funnel(root: Path) -> list[dict[str, Any]] | dict[str, Any]:
    path = root / "frontend" / "research_funnel.json"
    if not path.is_file():
        return _missing(path)
    families = _read_json(path).get("families")
    if not isinstance(families, list):
        raise ValueError("research_funnel.json must contain a families list")

    public = []
    for family in families:
        if not isinstance(family, dict):
            raise ValueError("each research family must be an object")
        experiments = family.get("experiments") or []
        if not isinstance(experiments, list):
            raise ValueError("research family experiments must be a list")
        outcome = experiments[-1].get("outcome") if experiments else None
        public.append(
            {
                "family": family.get("family_id"),
                "status": family.get("status"),
                "hypothesis_id": family.get("hypothesis_id"),
                "experiment_count": len(experiments),
                "outcome": outcome,
            }
        )
    return public


def build_public_status(root: Path = ROOT) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workstreams": _workstreams(root),
        "shadow_h014": _shadow(root),
        "research_funnel": _research_funnel(root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "public_status" / "status.json")
    args = parser.parse_args(argv)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(build_public_status(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
