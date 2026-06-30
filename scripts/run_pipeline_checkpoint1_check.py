"""Validate a pipeline checkpoint 1 summary artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from backtesting.pipeline_checkpoint1 import evaluate_summary, result_to_dict


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True, type=Path, help="path to a Stage 3 summary.json")
    parser.add_argument("--registry", default=Path("docs/EXPERIMENT_REGISTRY.md"), type=Path)
    parser.add_argument("--output", type=Path, help="defaults to checkpoint1_auto.json beside --summary")
    args = parser.parse_args(argv)

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    registry_text = args.registry.read_text(encoding="utf-8")
    output = result_to_dict(evaluate_summary(summary, registry_text, summary_path=args.summary))
    output_path = args.output or args.summary.with_name("checkpoint1_auto.json")
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    status = output["checkpoint1_auto_status"]
    print(status)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
