"""CLI for deterministic research idea batch generation."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtesting.pipeline_idea_generator import DEFAULT_CAP, DEFAULT_FEEDBACK_TAGS_PATH, generate_batch
from scripts.run_pipeline_funnel_report import idea_batch_funnel_metrics, write_funnel_metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy", required=True)
    parser.add_argument("--ledger", default="docs/EXPERIMENT_REGISTRY.md")
    parser.add_argument("--hypothesis-ledger", default="docs/HYPOTHESIS_LEDGER.md")
    parser.add_argument("--feedback-tags", default=str(DEFAULT_FEEDBACK_TAGS_PATH))
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--output-root", default="results")
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP)
    args = parser.parse_args(argv)
    payload = generate_batch(
        args.taxonomy,
        args.ledger,
        args.batch_id,
        hypothesis_ledger_path=args.hypothesis_ledger,
        feedback_tags_path=args.feedback_tags,
        output_root=args.output_root,
        cap=args.cap,
    )
    write_funnel_metrics(Path(args.output_root) / payload["batch_id"], idea_batch_funnel_metrics(payload))
    print(f"wrote {args.output_root}/{payload['batch_id']}/idea_batch.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
