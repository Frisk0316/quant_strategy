"""Benchmark API latency for backtest artifact read endpoints."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000", help="Running API base URL")
    parser.add_argument("--run-id", required=True, help="Backtest run ID to benchmark")
    parser.add_argument("--symbol", default=None, help="Optional symbol for symbol-scoped chart endpoints")
    parser.add_argument("--repeats", type=int, default=5, help="Measured repetitions per endpoint")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup repetitions per endpoint")
    parser.add_argument("--validation-id", default=None, help="Optional differential validation ID")
    parser.add_argument("--validation-artifact", action="append", default=[], help="Validation artifact name to include")
    parser.add_argument("--output", default=None, help="JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    endpoints = _endpoints(args)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base_url": args.api_base_url.rstrip("/"),
        "run_id": args.run_id,
        "symbol": args.symbol,
        "repeats": args.repeats,
        "warmup": args.warmup,
        "endpoints": [],
    }
    for item in endpoints:
        for _ in range(max(0, args.warmup)):
            _request_json(args.api_base_url, item["path"])
        timings = []
        status = "ok"
        error = None
        bytes_read = 0
        for _ in range(max(1, args.repeats)):
            started = time.perf_counter()
            try:
                payload = _request_json(args.api_base_url, item["path"])
                bytes_read = len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))
            except Exception as exc:
                status = "error"
                error = str(exc)
                break
            timings.append((time.perf_counter() - started) * 1000.0)
        report["endpoints"].append(_summarize(item, timings, status, error, bytes_read))

    output = Path(args.output) if args.output else _default_output_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(output), "endpoint_count": len(report["endpoints"])}, indent=2))
    return 0


def _endpoints(args: argparse.Namespace) -> list[dict[str, str]]:
    run_id = args.run_id
    symbol_query = {"symbol": args.symbol} if args.symbol else {}
    endpoints = [
        {"name": "runs", "path": "/api/backtest/runs"},
        {"name": "summary", "path": f"/api/backtest/{run_id}/summary"},
        {"name": "price_series", "path": _path(f"/api/backtest/{run_id}/price-series", {**symbol_query, "n": 1200})},
        {"name": "indicators", "path": _path(f"/api/backtest/{run_id}/indicators", {**symbol_query, "n": 1200})},
        {"name": "fills", "path": _path(f"/api/backtest/{run_id}/fills", {"limit": 1000})},
        {"name": "trades", "path": _path(f"/api/backtest/{run_id}/trades", {"limit": 1000})},
        {"name": "validation_list", "path": f"/api/backtest/{run_id}/differential-validation"},
    ]
    if args.validation_id:
        endpoints.append(
            {
                "name": "validation_detail",
                "path": f"/api/backtest/{run_id}/differential-validation/{args.validation_id}",
            }
        )
        for artifact in args.validation_artifact:
            endpoints.append(
                {
                    "name": f"validation_artifact:{artifact}",
                    "path": f"/api/backtest/{run_id}/differential-validation/{args.validation_id}/artifact/{artifact}",
                }
            )
    return endpoints


def _path(path: str, query: dict[str, object]) -> str:
    params = {key: value for key, value in query.items() if value is not None and value != ""}
    return path + ("?" + urlencode(params) if params else "")


def _request_json(base_url: str, path: str):
    request = Request(base_url.rstrip("/") + path, headers={"Accept": "application/json"})
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _summarize(
    endpoint: dict[str, str],
    timings: list[float],
    status: str,
    error: str | None,
    bytes_read: int,
) -> dict[str, object]:
    if not timings:
        return {**endpoint, "status": status, "error": error, "bytes": bytes_read}
    ordered = sorted(timings)
    p95_index = min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))
    return {
        **endpoint,
        "status": status,
        "error": error,
        "bytes": bytes_read,
        "median_ms": statistics.median(ordered),
        "p95_ms": ordered[p95_index],
        "min_ms": ordered[0],
        "max_ms": ordered[-1],
    }


def _default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("reports") / f"artifact_read_benchmark_{stamp}.json"


if __name__ == "__main__":
    raise SystemExit(main())
