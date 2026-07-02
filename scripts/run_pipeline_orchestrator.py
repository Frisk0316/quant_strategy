"""Run the advisory research-pipeline orchestrator."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.pipeline_orchestrator import run_orchestrator


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--idea-batch-path", type=Path)
    parser.add_argument("--hypothesis-ids", type=Path)
    parser.add_argument("--max-runtime-seconds", required=True, type=int)
    parser.add_argument("--output-root", default=Path("results"), type=Path)
    parser.add_argument("--dsn", default="postgresql://quant:changeme@localhost:5432/quant")
    parser.add_argument("--universe-path", default=Path("data/universe/universe_membership.parquet"), type=Path)
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end-exclusive", default="2026-06-17")
    parser.add_argument("--reprobe", action="store_true")
    args = parser.parse_args(argv)
    if not args.reprobe and (args.idea_batch_path is None or args.hypothesis_ids is None):
        parser.error("--idea-batch-path and --hypothesis-ids are required unless --reprobe is set")

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
            reprobe=args.reprobe,
        )
    )
    print(state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
