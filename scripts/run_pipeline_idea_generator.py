"""CLI for deterministic research idea batch generation."""
from __future__ import annotations

import argparse

from backtesting.pipeline_idea_generator import DEFAULT_CAP, generate_batch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy", required=True)
    parser.add_argument("--ledger", default="docs/EXPERIMENT_REGISTRY.md")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--output-root", default="results")
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP)
    args = parser.parse_args(argv)
    payload = generate_batch(
        args.taxonomy,
        args.ledger,
        args.batch_id,
        output_root=args.output_root,
        cap=args.cap,
    )
    print(f"wrote {args.output_root}/{payload['batch_id']}/idea_batch.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
