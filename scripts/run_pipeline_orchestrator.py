"""Run the advisory pipeline or a sealed ADR-0016 round."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.pipeline_orchestrator import run_orchestrator, run_round


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--idea-batch-path", type=Path)
    parser.add_argument("--hypothesis-ids", type=Path)
    parser.add_argument("--max-runtime-seconds", type=int)
    parser.add_argument("--output-root", default=Path("results"), type=Path)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--universe-path", default=Path("data/universe/universe_membership.parquet"), type=Path)
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end-exclusive", default="2026-06-17")
    parser.add_argument("--power-inputs", type=Path)
    parser.add_argument("--reprobe", action="store_true")
    parser.add_argument("--round-literature-path", type=Path)
    parser.add_argument("--round-iterations-path", type=Path)
    parser.add_argument("--artifact-root", default=Path("."), type=Path)
    args = parser.parse_args(argv)
    round_mode = args.round_literature_path is not None or args.round_iterations_path is not None
    if round_mode and (args.round_literature_path is None or args.round_iterations_path is None):
        parser.error("--round-literature-path and --round-iterations-path are required together")
    if not round_mode and args.max_runtime_seconds is None:
        parser.error("--max-runtime-seconds is required")
    if not round_mode and not args.reprobe and (args.idea_batch_path is None or args.hypothesis_ids is None):
        parser.error("--idea-batch-path and --hypothesis-ids are required unless --reprobe is set")
    power_inputs = {}
    if args.power_inputs is not None:
        try:
            power_inputs = json.loads(args.power_inputs.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"cannot read --power-inputs: {exc}")
        if not isinstance(power_inputs, dict):
            parser.error("--power-inputs must contain a JSON object keyed by candidate_id")

    if round_mode:
        report_path = asyncio.run(
            run_round(
                literature_path=args.round_literature_path,
                iterations_path=args.round_iterations_path,
                round_id=args.batch_id,
                output_root=args.output_root,
                dsn=args.dsn,
                artifact_root=args.artifact_root,
            )
        )
        print(report_path)
        return 0

    state_path = asyncio.run(
        run_orchestrator(
            idea_batch_path=args.idea_batch_path,
            hypothesis_ids_path=args.hypothesis_ids,
            batch_id=args.batch_id,
            max_runtime_seconds=args.max_runtime_seconds,
            output_root=args.output_root,
            dsn=args.dsn,
            universe_path=args.universe_path,
            start=args.start,
            end_exclusive=args.end_exclusive,
            power_inputs=power_inputs,
            reprobe=args.reprobe,
        )
    )
    print(state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
