"""Lightweight API smoke check.

Set API_BASE_URL=http://localhost:8080 to exercise a running server.
Without API_BASE_URL this exits successfully with an explicit SKIP.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_ENDPOINTS = ("/api/backtest/runs", "/api/data/exchanges")


def _get_json(base_url: str, path: str, api_key: str | None) -> object:
    request = urllib.request.Request(base_url.rstrip("/") + path)
    if api_key:
        request.add_header("X-Api-Key", api_key)
    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read().decode("utf-8")
        if response.status >= 400:
            raise RuntimeError(f"{path} returned HTTP {response.status}")
        return json.loads(body)


def main() -> int:
    base_url = os.environ.get("API_BASE_URL", "").strip()
    if not base_url:
        print("SKIP api-smoke: API_BASE_URL is not set; no running server was required")
        print("Set API_BASE_URL=http://localhost:8080 to check live endpoints.")
        return 0

    api_key = os.environ.get("API_KEY")
    errors: list[str] = []
    for endpoint in DEFAULT_ENDPOINTS:
        try:
            payload = _get_json(base_url, endpoint, api_key)
            kind = type(payload).__name__
            size = len(payload) if hasattr(payload, "__len__") else "unknown"
            print(f"PASS {endpoint}: {kind} size={size}")
        except (OSError, urllib.error.URLError, json.JSONDecodeError, RuntimeError) as exc:
            errors.append(f"{endpoint}: {exc}")

    for error in errors:
        print(f"ERROR {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
