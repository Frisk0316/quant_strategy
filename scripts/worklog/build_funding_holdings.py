"""Replay E-063 frozen parameters and write its display-only holdings log."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from backtesting.funding_xs_dispersion_backtest import (  # noqa: E402
    FundingXSDispersionParams,
    load_funding_xs_dispersion_inputs,
    run_funding_xs_dispersion_backtest,
)
from scripts._db_writer import resolve_dsn  # noqa: E402
from scripts.run_strategy_finding_20260726 import _alias_adjusted_membership  # noqa: E402


E063_DIR = ROOT / "results" / "strategy_finding_20260726" / "f_funding_xs_dispersion_retry1"
SUMMARY_PATH = E063_DIR / "summary.json"
OUT_PATH = E063_DIR / "holdings.json"
UNIVERSE_PATH = ROOT / "data" / "universe" / "universe_membership.parquet"


def build_payload(
    rebalances: list[dict[str, Any]],
    *,
    notional_base_usd: float = 10_000,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if notional_base_usd <= 0:
        raise ValueError("notional_base_usd must be positive")

    def display_name(symbol: str) -> str:
        return symbol.removesuffix("-USDT-SWAP")

    return {
        "schema_version": 1,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "params_frozen_from": "E-063",
        "notional_base_usd": notional_base_usd,
        "notional_note": "Display-only assumed notional; amounts are weights multiplied by notional_base_usd.",
        "rebalances": [
            {
                "date": row["date"],
                "long": {
                    display_name(symbol): weight * notional_base_usd
                    for symbol, weight in row["long"].items()
                },
                "short": {
                    display_name(symbol): weight * notional_base_usd
                    for symbol, weight in row["short"].items()
                },
                "period_return": row["period_return"],
            }
            for row in rebalances
        ],
    }


def build_holdings(
    *,
    dsn: str,
) -> dict[str, Any]:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    raw_params = summary.get("full_sample_best_params")
    if not isinstance(raw_params, dict) or summary.get("hypothesis_id") != "H-009":
        raise ValueError("summary must contain E-063 H-009 frozen parameters")
    params = FundingXSDispersionParams(**raw_params)
    if params.universe != summary.get("input_symbols"):
        raise ValueError("frozen parameter universe does not match E-063 input_symbols")

    source = summary.get("data_source") or {}
    start = str(source["start"]).split("T", 1)[0]
    end = str(source["end_exclusive"]).split("T", 1)[0]
    exchange = str(source["primary_exchange"])
    membership, _ = _alias_adjusted_membership(UNIVERSE_PATH, start=start, end=end)
    membership = membership[membership["symbol"].isin(params.universe)].copy()
    close, high, low, vol, funding = load_funding_xs_dispersion_inputs(
        params.universe,
        bar=params.bar,
        start=start,
        end=end,
        backend="postgres",
        dsn=dsn,
        exchange=exchange,
    )
    result = run_funding_xs_dispersion_backtest(
        close,
        high,
        low,
        vol,
        funding,
        membership,
        params,
        market_close=close.get("BTC-USDT-SWAP"),
        holdings_log=True,
    )
    return build_payload(result.metrics["holdings_log"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn")
    args = parser.parse_args(argv)
    dsn = resolve_dsn(args.dsn) or dotenv_values(ROOT / ".env").get("DATABASE_URL")
    if not dsn:
        parser.error("--dsn, DATABASE_URL, or config storage.timescale_dsn is required")
    payload = build_holdings(dsn=dsn)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({len(payload['rebalances'])} rebalances)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
