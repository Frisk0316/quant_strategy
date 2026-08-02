"""Manual OKX demo credential and place/cancel smoke test."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.rest_client import OKXRestClient
from okx_quant.execution.broker import OKXBroker


_PLACEHOLDERS = {"your_api_key_here", "your_secret_here", "your_passphrase_here"}


def _data(response: dict, operation: str) -> list[dict]:
    if response.get("code") != "0":
        raise RuntimeError(
            f"{operation} failed: code={response.get('code', 'missing')} "
            f"msg={response.get('msg', '')}"
        )
    return response.get("data") or []


def _aligned(value: Decimal, step: Decimal, rounding: str) -> Decimal:
    return (value / step).to_integral_value(rounding=rounding) * step


async def smoke(inst_id: str) -> None:
    cfg = load_config()
    if not cfg.is_demo():
        raise RuntimeError(f"blocked: config mode is {cfg.system.mode!r}, expected 'demo'")

    credentials = (
        cfg.secrets.okx_api_key,
        cfg.secrets.okx_secret,
        cfg.secrets.okx_passphrase,
    )
    if any(not value or value.strip().lower() in _PLACEHOLDERS for value in credentials):
        raise RuntimeError(
            "blocked-pending-user-key: set a valid OKX Demo Trading "
            "OKX_API_KEY/OKX_SECRET/OKX_PASSPHRASE"
        )

    rest = OKXRestClient(*credentials, demo=True)
    broker = OKXBroker(*credentials, demo=True, strategy_name="demo-smoke")
    cl_ord_id = f"okxsmoke{int(time.time() * 1000)}"
    attempted = False
    cancelled = False
    error: Exception | None = None
    try:
        balance = _data(rest.get_balance("USDT"), "balance")
        details = (balance[0].get("details") or []) if balance else []
        usdt = next((row for row in details if row.get("ccy") == "USDT"), {})
        print(
            "balance ok:"
            f" totalEq={balance[0].get('totalEq', '') if balance else ''}"
            f" USDT.availBal={usdt.get('availBal', '')}"
        )

        instruments = _data(rest.get_instruments("SPOT"), "instrument lookup")
        spec = next((row for row in instruments if row.get("instId") == inst_id), None)
        if spec is None:
            raise RuntimeError(f"instrument lookup failed: {inst_id} not found")
        ticker_rows = _data(rest.get_ticker(inst_id), "ticker")
        if not ticker_rows:
            raise RuntimeError(f"ticker failed: no data for {inst_id}")

        market_px = Decimal(ticker_rows[0].get("bidPx") or ticker_rows[0]["last"])
        tick_sz = Decimal(spec["tickSz"])
        lot_sz = Decimal(spec["lotSz"])
        price = _aligned(market_px * Decimal("0.90"), tick_sz, ROUND_DOWN)
        size = _aligned(Decimal(spec["minSz"]), lot_sz, ROUND_CEILING)
        if price <= 0 or size <= 0:
            raise RuntimeError("instrument returned a non-positive price or size")

        order = {
            "inst_id": inst_id,
            "td_mode": "cash",
            "side": "buy",
            "ord_type": "post_only",
            "sz": format(size, "f"),
            "px": format(price, "f"),
            "cl_ord_id": cl_ord_id,
            "strategy": "demo-smoke",
        }
        attempted = True
        fill = await broker.submit(order)
        if fill is None or not fill.ord_id:
            raise RuntimeError("demo order was rejected or returned no order id")
        print(
            f"order placed: instId={inst_id} clOrdId={cl_ord_id} "
            f"ordId={fill.ord_id} px={order['px']} sz={order['sz']}"
        )
    except Exception as exc:
        error = exc
    finally:
        if attempted:
            cancelled = await broker.cancel(inst_id, cl_ord_id)
            print(f"cancel attempted: clOrdId={cl_ord_id} cancelled={cancelled}")
        rest.close()

    if error is not None:
        raise error
    if not cancelled:
        raise RuntimeError("demo order cancellation was not confirmed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inst-id", default="BTC-USDT")
    args = parser.parse_args()
    try:
        asyncio.run(smoke(args.inst_id))
    except Exception as exc:
        print(f"BLOCKED/FAILED: {exc}", file=sys.stderr)
        return 2
    print("OKX demo smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
