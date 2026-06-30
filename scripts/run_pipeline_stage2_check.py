"""Validate a Stage 2 feasibility artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from backtesting.pipeline_feasibility import result_from_dict, result_to_dict


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-status", action="store_true", help="rewrite the artifact with computed stage2_status")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)

    payload = json.loads(args.path.read_text(encoding="utf-8"))
    result = result_from_dict(payload)
    output = result_to_dict(result)
    status = output["stage2_status"]

    if args.write_status:
        args.path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(status)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
