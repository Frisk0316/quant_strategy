"""Backtest smoke placeholder with honest coverage reporting.

The repository does not currently include a tiny frozen fixture that can run a
full replay backtest without local data or TimescaleDB. This script verifies the
expected entrypoints exist and reports the remaining gap without pretending to
run a complete smoke.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINTS = (
    "scripts/run_replay_backtest.py",
    "backtesting/replay.py",
    "backtesting/artifacts.py",
)


def main() -> int:
    missing = [path for path in ENTRYPOINTS if not (REPO_ROOT / path).exists()]
    for path in ENTRYPOINTS:
        status = "PASS" if path not in missing else "ERROR"
        print(f"{status} backtest entrypoint: {path}")
    if missing:
        print("backtest-smoke failed: required entrypoint(s) missing")
        return 1
    print("SKIP full replay smoke: no tiny no-DB fixture is defined yet")
    print("Known gap: add a frozen fixture before treating this as execution coverage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
