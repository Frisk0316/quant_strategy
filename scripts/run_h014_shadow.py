"""Run one credential-free H-014 shadow cycle, or build its bias report."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from okx_quant.execution.deribit_shadow import (  # noqa: E402
    build_bias_report,
    load_config,
    run_cycle,
)
from okx_quant.execution.deribit_shadow.runner import resolve_dsn  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/h014_shadow.yaml")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.report:
        report = build_bias_report(config["journal_path"])
        output = Path(config["journal_path"]).with_name("bias_report.json")
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0
    summary = asyncio.run(run_cycle(config, resolve_dsn()))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
