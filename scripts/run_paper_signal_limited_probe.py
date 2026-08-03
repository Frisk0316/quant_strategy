"""Run the frozen 2026-08-02 paper/data limited research probe."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtesting.paper_signal_probe import DEFAULT_OUTPUT_ROOT, run_limited_probe
from scripts._db_writer import resolve_dsn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="TimescaleDB DSN; defaults to DATABASE_URL/config")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    dsn = resolve_dsn(args.dsn)
    if not dsn:
        parser.error("database DSN is required")
    report = asyncio.run(run_limited_probe(dsn=dsn, output_root=args.output_root.resolve()))
    print(json.dumps(report["terminal_counts"], sort_keys=True))
    print(args.output_root.resolve() / "limited_probe_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
