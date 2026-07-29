"""Cancel H-014 option orders for both currencies and force reduce-only state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RISK_CONFIG = ROOT / "config" / "risk.yaml"
DEFAULT_ENV_FILE = ROOT / ".env"
DEFAULT_STATE_PATH = ROOT / "results" / "live_h014" / "reduce_only.flag"
for search_path in (ROOT, ROOT / "src"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from okx_quant.execution.deribit_live.adapter import load_live_config, set_reduce_only_state
from okx_quant.execution.deribit_live.private_client import DeribitPrivateClient


class _DryRunClient:
    def cancel_all_by_currency(self, currency: str) -> dict[str, Any]:
        return {"dry_run": True, "currency": currency, "kind": "option"}

    def close(self) -> None:
        return None


def run_panic(
    client: Any,
    *,
    state_path: str | Path = DEFAULT_STATE_PATH,
    dry_run: bool = False,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    if not dry_run:
        try:
            set_reduce_only_state(state_path, "manual panic command")
        except Exception as exc:
            errors["reduce_only_state"] = str(exc)
    for currency in ("BTC", "ETH"):
        try:
            results[currency] = client.cancel_all_by_currency(currency)
        except Exception as exc:
            errors[currency] = str(exc)
    if errors:
        raise RuntimeError(f"H-014 panic cancellation failed: {errors}")
    return {"dry_run": dry_run, "reduce_only": not dry_run, "cancelled": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="use a no-network client")
    parser.add_argument("--risk-config", default=str(DEFAULT_RISK_CONFIG))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    args = parser.parse_args()

    config = load_live_config(args.risk_config)
    if args.dry_run:
        client: Any = _DryRunClient()
    else:
        try:
            client = DeribitPrivateClient.from_env(env=config.env, env_file=args.env_file)
        except Exception:
            # Fail closed even when credentials are unavailable.
            set_reduce_only_state(DEFAULT_STATE_PATH, "manual panic command")
            raise
    try:
        print(json.dumps(run_panic(client, dry_run=args.dry_run), indent=2, sort_keys=True))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
