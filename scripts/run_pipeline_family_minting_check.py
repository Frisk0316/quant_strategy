"""Write a family-minting distinctness sidecar for a candidate signal."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from backtesting.pipeline_family_minting import decide_family_minting


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path, help="JSON with signal and claimed family fields")
    parser.add_argument("--refs", required=True, type=Path, help="JSON mapping family_id to reference signal")
    parser.add_argument("--ledger", default=Path("docs/EXPERIMENT_REGISTRY.md"), type=Path)
    parser.add_argument("--output", type=Path, help="defaults to family_minting.json beside --candidate")
    args = parser.parse_args(argv)

    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    refs = json.loads(args.refs.read_text(encoding="utf-8"))
    signal = candidate.get("signal") if isinstance(candidate, dict) else candidate
    output = decide_family_minting(
        signal,
        refs,
        str(candidate.get("claimed_family_id_or_NEW", "NEW")) if isinstance(candidate, dict) else "NEW",
        str(candidate.get("claimed_mechanism", "")) if isinstance(candidate, dict) else "",
        args.ledger,
        batch_id=str(candidate.get("batch_id", "")) if isinstance(candidate, dict) else "",
        candidate_id=str(candidate.get("candidate_id", "")) if isinstance(candidate, dict) else "",
    )
    output_path = args.output or args.candidate.with_name("family_minting.json")
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output["decision"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
