"""Run one bounded Binance Spot and USD-M Futures non-production order round trip."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_DOWN
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / ".env"
for search_path in (ROOT, ROOT / "src"):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from okx_quant.execution.binance_testnet import (
    BinanceFuturesTestnetClient,
    BinanceSpotTestnetClient,
)


class SmokeBlocked(RuntimeError):
    """The smoke run cannot place an order without increasing exposure."""


def _decimal(value: Any, name: str) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise SmokeBlocked(f"{name} is not numeric") from exc
    if not number.is_finite() or number <= 0:
        raise SmokeBlocked(f"{name} must be positive")
    return number


def _down(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def _up(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_CEILING) * step


def _text(value: Decimal) -> str:
    return format(value, "f")


def _symbol_info(exchange_info: dict[str, Any], symbol: str) -> dict[str, Any]:
    for item in exchange_info.get("symbols", []):
        if isinstance(item, dict) and str(item.get("symbol", "")).upper() == symbol:
            return item
    raise SmokeBlocked(f"{symbol} is absent from testnet exchangeInfo")


def _filters(symbol_info: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("filterType")): item
        for item in symbol_info.get("filters", [])
        if isinstance(item, dict) and item.get("filterType")
    }


def _minimum_notional(filters: dict[str, dict[str, Any]]) -> Decimal:
    for filter_name in ("NOTIONAL", "MIN_NOTIONAL"):
        rule = filters.get(filter_name, {})
        raw = rule.get("minNotional", rule.get("notional", "0"))
        value = Decimal(str(raw))
        if value.is_finite() and value > 0:
            return value
    return Decimal("0")


def _factor(
    filters: dict[str, dict[str, Any]],
    *,
    side: str,
) -> Decimal:
    by_side = filters.get("PERCENT_PRICE_BY_SIDE", {})
    percent = filters.get("PERCENT_PRICE", {})
    if side == "BUY":
        raw = by_side.get("bidMultiplierDown", percent.get("multiplierDown", "0"))
        boundary = Decimal(str(raw))
        return (Decimal("1") + boundary) / 2 if 0 < boundary < 1 else Decimal("0.5")
    raw = by_side.get("askMultiplierUp", percent.get("multiplierUp", "0"))
    boundary = Decimal(str(raw))
    return (Decimal("1") + boundary) / 2 if boundary > 1 else Decimal("2")


def _order_values(
    *,
    ticker: dict[str, Any],
    symbol_info: dict[str, Any],
    side: str,
    maximum_quantity: Decimal | None = None,
) -> tuple[str, str]:
    rules = _filters(symbol_info)
    price_rule = rules.get("PRICE_FILTER", {})
    lot_rule = rules.get("LOT_SIZE", {})
    tick = _decimal(price_rule.get("tickSize"), "PRICE_FILTER.tickSize")
    step = _decimal(lot_rule.get("stepSize"), "LOT_SIZE.stepSize")
    min_price = _decimal(price_rule.get("minPrice"), "PRICE_FILTER.minPrice")
    min_qty = _decimal(lot_rule.get("minQty"), "LOT_SIZE.minQty")

    if side == "BUY":
        near_price = _decimal(ticker.get("bidPrice"), "bidPrice")
        price = _down(near_price * _factor(rules, side=side), tick)
        price = max(price, _up(min_price, tick))
        if price >= near_price:
            raise SmokeBlocked("could not derive a below-market BUY price")
    else:
        near_price = _decimal(ticker.get("askPrice"), "askPrice")
        price = _up(near_price * _factor(rules, side=side), tick)
        max_price = Decimal(str(price_rule.get("maxPrice", "0")))
        if max_price > 0:
            price = min(price, _down(max_price, tick))
        if price <= near_price:
            raise SmokeBlocked("could not derive an above-market SELL price")

    quantity = min_qty
    min_notional = _minimum_notional(rules)
    if min_notional > 0:
        quantity = max(quantity, _up(min_notional / price, step))
    max_qty = Decimal(str(lot_rule.get("maxQty", "0")))
    if max_qty > 0 and quantity > max_qty:
        raise SmokeBlocked("minimum valid order exceeds LOT_SIZE.maxQty")
    if maximum_quantity is not None and quantity > maximum_quantity:
        raise SmokeBlocked("position is smaller than the minimum valid reduce-only futures order")
    return _text(quantity), _text(price)


def _spot_order_values(
    client: BinanceSpotTestnetClient,
    symbol: str,
) -> tuple[str, str]:
    ticker = client.book_ticker(symbol)
    info = _symbol_info(client.exchange_info(symbol), symbol)
    return _order_values(ticker=ticker, symbol_info=info, side="BUY")


def _safe_futures_order(
    client: BinanceFuturesTestnetClient,
    positions: list[dict[str, Any]],
    exchange_info: dict[str, Any],
    requested_symbol: str | None,
) -> dict[str, str]:
    requested_symbol = requested_symbol.upper() if requested_symbol else None
    candidates = sorted(
        (
            position
            for position in positions
            if isinstance(position, dict)
            and str(position.get("positionSide", "")).upper() == "BOTH"
            and Decimal(str(position.get("positionAmt", "0"))) != 0
            and (
                requested_symbol is None
                or str(position.get("symbol", "")).upper() == requested_symbol
            )
        ),
        key=lambda position: str(position.get("symbol", "")),
    )
    errors: list[str] = []
    for position in candidates:
        symbol = str(position["symbol"]).upper()
        amount = Decimal(str(position["positionAmt"]))
        side = "SELL" if amount > 0 else "BUY"
        try:
            quantity, price = _order_values(
                ticker=client.book_ticker(symbol),
                symbol_info=_symbol_info(exchange_info, symbol),
                side=side,
                maximum_quantity=abs(amount),
            )
        except SmokeBlocked as exc:
            errors.append(f"{symbol}: {exc}")
            continue
        return {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "positionAmt": _text(amount),
        }
    detail = f" ({'; '.join(errors)})" if errors else ""
    requested = f" for {requested_symbol}" if requested_symbol else ""
    raise SmokeBlocked(
        "futures smoke requires an existing nonzero one-way positionSide=BOTH "
        f"position{requested}; it will not open exposure or change position mode{detail}"
    )


def _order_id(payload: dict[str, Any], venue: str) -> str | int:
    order_id = payload.get("orderId")
    if order_id is None or not str(order_id).strip():
        raise RuntimeError(f"{venue} order response did not include orderId")
    return order_id


def _client_order_id(venue: str) -> str:
    return f"qs-{venue}-{uuid.uuid4().hex[:24]}"


def _note_cancel_error(original: Exception, cancel_error: Exception) -> None:
    add_note = getattr(original, "add_note", None)
    if callable(add_note):
        add_note(f"orphan-order cancel attempt also failed: {cancel_error}")


def _spot_round_trip(
    client: BinanceSpotTestnetClient,
    *,
    symbol: str,
    quantity: str,
    price: str,
) -> dict[str, Any]:
    client_order_id = _client_order_id("spot")
    placed: dict[str, Any] | None = None
    cancelled: dict[str, Any] | None = None
    placement_error: Exception | None = None
    try:
        placed = client.place_limit_order(
            symbol,
            "BUY",
            quantity,
            price,
            client_order_id=client_order_id,
        )
        _order_id(placed, "spot")
    except Exception as exc:
        placement_error = exc
    finally:
        try:
            cancelled = client.cancel_order(
                symbol,
                orig_client_order_id=client_order_id,
            )
        except Exception as cancel_error:
            if placement_error is None:
                raise
            _note_cancel_error(placement_error, cancel_error)
    if placement_error is not None:
        raise placement_error
    return {
        "client_order_id": client_order_id,
        "placed": placed,
        "cancelled": cancelled,
        "open_orders_after_cancel": client.open_orders(symbol),
    }


def _futures_round_trip(
    client: BinanceFuturesTestnetClient,
    order: dict[str, str],
) -> dict[str, Any]:
    client_order_id = _client_order_id("fut")
    placed: dict[str, Any] | None = None
    cancelled: dict[str, Any] | None = None
    placement_error: Exception | None = None
    try:
        placed = client.place_limit_order(
            order["symbol"],
            order["side"],
            order["quantity"],
            order["price"],
            client_order_id=client_order_id,
        )
        _order_id(placed, "futures")
    except Exception as exc:
        placement_error = exc
    finally:
        try:
            cancelled = client.cancel_order(
                order["symbol"],
                orig_client_order_id=client_order_id,
            )
        except Exception as cancel_error:
            if placement_error is None:
                raise
            _note_cancel_error(placement_error, cancel_error)
    if placement_error is not None:
        raise placement_error
    return {
        "client_order_id": client_order_id,
        "placed": placed,
        "cancelled": cancelled,
        "open_orders_after_cancel": client.open_orders(order["symbol"]),
    }


def _nonzero_balances(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for row in rows:
        values = [
            row.get("free", "0"),
            row.get("locked", "0"),
            row.get("balance", "0"),
            row.get("walletBalance", "0"),
        ]
        try:
            if any(Decimal(str(value)) != 0 for value in values):
                kept.append(row)
        except InvalidOperation:
            kept.append(row)
    return kept


def _run_spot(
    spot: BinanceSpotTestnetClient,
    *,
    spot_symbol: str,
) -> dict[str, Any]:
    spot_symbol = spot_symbol.upper()
    spot_account = spot.account_info()
    snapshot = {
        "accountType": spot_account.get("accountType"),
        "canTrade": spot_account.get("canTrade"),
        "balances": _nonzero_balances(spot_account.get("balances", [])),
    }
    try:
        spot_quantity, spot_price = _spot_order_values(spot, spot_symbol)
    except SmokeBlocked as exc:
        return {
            "status": "blocked",
            "reason": str(exc),
            "host": BinanceSpotTestnetClient.BASE_URL,
            "account_snapshot": snapshot,
        }
    spot_test = spot.test_limit_order(spot_symbol, "BUY", spot_quantity, spot_price)
    spot_result = _spot_round_trip(
        spot,
        symbol=spot_symbol,
        quantity=spot_quantity,
        price=spot_price,
    )
    spot_result["test_order"] = spot_test
    return {
        "status": "ok",
        "host": BinanceSpotTestnetClient.BASE_URL,
        "account_snapshot": snapshot,
        "order": {
            "symbol": spot_symbol,
            "side": "BUY",
            "quantity": spot_quantity,
            "price": spot_price,
            **spot_result,
        },
    }


def _run_futures(
    futures: BinanceFuturesTestnetClient,
    *,
    futures_symbol: str | None,
) -> dict[str, Any]:
    futures_balance = futures.balance()
    positions = futures.positions(futures_symbol)
    snapshot = {
        "futures_balances": _nonzero_balances(futures_balance),
        "futures_positions": [
            position
            for position in positions
            if Decimal(str(position.get("positionAmt", "0"))) != 0
        ],
    }
    futures_info = futures.exchange_info()
    try:
        futures_order = _safe_futures_order(
            futures,
            positions,
            futures_info,
            futures_symbol,
        )
    except SmokeBlocked as exc:
        return {
            "status": "blocked",
            "reason": str(exc),
            "host": BinanceFuturesTestnetClient.BASE_URL,
            "account_snapshot": snapshot,
        }
    futures_test = futures.test_limit_order(
        futures_order["symbol"],
        futures_order["side"],
        futures_order["quantity"],
        futures_order["price"],
    )
    futures_result = _futures_round_trip(futures, futures_order)
    futures_result["test_order"] = futures_test
    return {
        "status": "ok",
        "host": BinanceFuturesTestnetClient.BASE_URL,
        "account_snapshot": snapshot,
        "order": {**futures_order, **futures_result},
    }


def _capture_venue(host: str, callback) -> dict[str, Any]:
    try:
        return callback()
    except SmokeBlocked as exc:
        return {"status": "blocked", "reason": str(exc), "host": host}
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "host": host}


def _aggregate(venues: dict[str, dict[str, Any]]) -> dict[str, Any]:
    statuses = [result["status"] for result in venues.values()]
    if any(status == "failed" for status in statuses):
        status = "failed"
    elif statuses and all(item == "ok" for item in statuses):
        status = "ok"
    elif any(item == "ok" for item in statuses):
        status = "partial"
    else:
        status = "blocked"
    return {"status": status, "venues": venues}


def _run(
    spot: BinanceSpotTestnetClient | None,
    futures: BinanceFuturesTestnetClient | None,
    *,
    spot_symbol: str,
    futures_symbol: str | None,
) -> dict[str, Any]:
    venues: dict[str, dict[str, Any]] = {}
    if spot is not None:
        venues["spot"] = _capture_venue(
            BinanceSpotTestnetClient.BASE_URL,
            lambda: _run_spot(spot, spot_symbol=spot_symbol),
        )
    if futures is not None:
        venues["futures"] = _capture_venue(
            BinanceFuturesTestnetClient.BASE_URL,
            lambda: _run_futures(futures, futures_symbol=futures_symbol),
        )
    return _aggregate(venues)


def _missing_credentials(error: RuntimeError) -> bool:
    message = str(error)
    return "requires BINANCE_" in message or "requires BINANCE " in message


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--venue", choices=("all", "spot", "futures"), default="all")
    parser.add_argument("--spot-symbol", default="BTCUSDT")
    parser.add_argument(
        "--futures-symbol",
        help="optional existing one-way position to reduce; otherwise choose the first safe one",
    )
    args = parser.parse_args()

    venues: dict[str, dict[str, Any]] = {}
    if args.venue in {"all", "spot"}:
        spot: BinanceSpotTestnetClient | None = None
        try:
            spot = BinanceSpotTestnetClient.from_env(env_file=args.env_file)
        except RuntimeError as exc:
            if _missing_credentials(exc):
                venues["spot"] = {
                    "status": "blocked",
                    "reason": "blocked-pending-user-key",
                    "host": BinanceSpotTestnetClient.BASE_URL,
                }
            else:
                venues["spot"] = {
                    "status": "failed",
                    "error": str(exc),
                    "host": BinanceSpotTestnetClient.BASE_URL,
                }
        else:
            venues["spot"] = _capture_venue(
                BinanceSpotTestnetClient.BASE_URL,
                lambda: _run_spot(spot, spot_symbol=args.spot_symbol),
            )
        finally:
            if spot is not None:
                spot.close()

    if args.venue in {"all", "futures"}:
        futures: BinanceFuturesTestnetClient | None = None
        try:
            futures = BinanceFuturesTestnetClient.from_env(env_file=args.env_file)
        except RuntimeError as exc:
            if _missing_credentials(exc):
                venues["futures"] = {
                    "status": "blocked",
                    "reason": "blocked-pending-user-key",
                    "host": BinanceFuturesTestnetClient.BASE_URL,
                }
            else:
                venues["futures"] = {
                    "status": "failed",
                    "error": str(exc),
                    "host": BinanceFuturesTestnetClient.BASE_URL,
                }
        else:
            venues["futures"] = _capture_venue(
                BinanceFuturesTestnetClient.BASE_URL,
                lambda: _run_futures(
                    futures,
                    futures_symbol=args.futures_symbol,
                ),
            )
        finally:
            if futures is not None:
                futures.close()

    output = _aggregate(venues)
    print(json.dumps(output, indent=2, sort_keys=True))
    if output["status"] == "ok":
        return 0
    if output["status"] in {"blocked", "partial"}:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
