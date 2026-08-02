from __future__ import annotations

import hashlib
import hmac
import json
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from okx_quant.execution.binance_testnet import (
    BinanceFuturesTestnetClient,
    BinanceSpotTestnetClient,
)
from okx_quant.execution.binance_testnet import futures_client as futures_module
from okx_quant.execution.binance_testnet import spot_client as spot_module
from scripts.run_binance_testnet_smoke import (
    _futures_round_trip,
    _run,
    _safe_futures_order,
    _spot_round_trip,
    main as smoke_main,
)


@pytest.mark.parametrize(
    ("module", "client_class", "message"),
    [
        (
            spot_module,
            BinanceSpotTestnetClient,
            "BINANCE_API_KEY and BINANCE_SECRET",
        ),
        (
            futures_module,
            BinanceFuturesTestnetClient,
            "BINANCE_FUTURES_API_KEY and BINANCE_FUTURES_SECRET",
        ),
    ],
)
def test_missing_credentials_fail_before_http_client_construction(
    monkeypatch: pytest.MonkeyPatch,
    module,
    client_class,
    message: str,
):
    def forbidden_client(*_args, **_kwargs):
        raise AssertionError("httpx.Client must not be constructed without credentials")

    monkeypatch.setattr(module.httpx, "Client", forbidden_client)
    with pytest.raises(RuntimeError, match=message):
        client_class("", " ")


def test_spot_official_signature_vector_and_order_round_trip():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v3/order/test":
            return httpx.Response(200, json={})
        if request.url.path == "/api/v3/order" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "symbol": "LTCBTC",
                    "orderId": 7,
                    "status": "NEW",
                    "price": "0.1",
                    "origQty": "1",
                },
            )
        if request.url.path == "/api/v3/order" and request.method == "DELETE":
            return httpx.Response(
                200,
                json={"symbol": "LTCBTC", "orderId": 7, "status": "CANCELED"},
            )
        if request.url.path == "/api/v3/openOrders":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request {request.method} {request.url.path}")

    # Public HMAC example from Binance's Spot Test Network documentation.
    client = BinanceSpotTestnetClient(
        "vmPUZE6mv9SD5VNHk4HlWFsOr6aKE2zvsw0MuIgwCIPy6utIco14y7Ju91duEh8A",
        "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j",
        clock_ms=lambda: 1499827319559,
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.test_limit_order("ltcbtc", "buy", "1", "0.1") == {}
        placed = client.place_limit_order("LTCBTC", "BUY", "1", "0.1")
        cancelled = client.cancel_order("LTCBTC", placed["orderId"])
        assert client.open_orders("LTCBTC") == []
    finally:
        client.close()

    assert placed["orderId"] == 7
    assert placed["status"] == "NEW"
    assert cancelled == {"symbol": "LTCBTC", "orderId": 7, "status": "CANCELED"}

    signed = requests[0]
    assert signed.url.host == "testnet.binance.vision"
    assert signed.url.path == "/api/v3/order/test"
    assert signed.headers["X-MBX-APIKEY"].startswith("vmPUZ")
    assert signed.url.query.decode("ascii") == (
        "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1"
        "&recvWindow=5000&timestamp=1499827319559"
        "&signature=c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71"
    )

    cancel_params = requests[2].url.params
    assert requests[2].method == "DELETE"
    assert cancel_params["symbol"] == "LTCBTC"
    assert cancel_params["orderId"] == "7"


def test_futures_signed_v3_reads_and_reduce_only_order_round_trip():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/fapi/v3/balance":
            return httpx.Response(200, json=[{"asset": "USDT", "balance": "1000"}])
        if request.url.path == "/fapi/v3/positionRisk":
            return httpx.Response(
                200,
                json=[
                    {
                        "symbol": "BTCUSDT",
                        "positionAmt": "0.002",
                        "positionSide": "BOTH",
                    }
                ],
            )
        if request.url.path == "/fapi/v1/order/test":
            return httpx.Response(200, json={})
        if request.url.path == "/fapi/v1/order" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "symbol": "BTCUSDT",
                    "orderId": 42,
                    "status": "NEW",
                    "reduceOnly": True,
                },
            )
        if request.url.path == "/fapi/v1/order" and request.method == "DELETE":
            return httpx.Response(
                200,
                json={"symbol": "BTCUSDT", "orderId": 42, "status": "CANCELED"},
            )
        if request.url.path == "/fapi/v1/openOrders":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request {request.method} {request.url.path}")

    client = BinanceFuturesTestnetClient(
        "futures-unit-key",
        "futures-unit-secret",
        clock_ms=lambda: 1591702613943,
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.balance() == [{"asset": "USDT", "balance": "1000"}]
        assert client.positions("BTCUSDT")[0]["positionSide"] == "BOTH"
        assert client.test_limit_order("BTCUSDT", "SELL", "0.001", "120000") == {}
        placed = client.place_limit_order("BTCUSDT", "SELL", "0.001", "120000")
        cancelled = client.cancel_order("BTCUSDT", placed["orderId"])
        assert client.open_orders("BTCUSDT") == []
    finally:
        client.close()

    assert placed == {
        "symbol": "BTCUSDT",
        "orderId": 42,
        "status": "NEW",
        "reduceOnly": True,
    }
    assert cancelled["status"] == "CANCELED"
    assert all(request.url.host == "demo-fapi.binance.com" for request in requests)

    order_requests = [
        request
        for request in requests
        if request.url.path in {"/fapi/v1/order/test", "/fapi/v1/order"}
        and request.method == "POST"
    ]
    assert len(order_requests) == 2
    for request in order_requests:
        query = request.url.query.decode("ascii")
        unsigned, signature = query.rsplit("&signature=", 1)
        expected = hmac.new(
            b"futures-unit-secret",
            unsigned.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        assert signature == expected
        params = parse_qs(unsigned)
        assert request.headers["X-MBX-APIKEY"] == "futures-unit-key"
        assert params["positionSide"] == ["BOTH"]
        assert params["reduceOnly"] == ["true"]
        assert params["type"] == ["LIMIT"]
        assert params["timeInForce"] == ["GTC"]

    assert requests[0].url.path == "/fapi/v3/balance"
    assert requests[1].url.path == "/fapi/v3/positionRisk"
    assert requests[-2].method == "DELETE"
    assert requests[-2].url.params["orderId"] == "42"


def test_from_env_uses_distinct_spot_and_futures_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("BINANCE_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_SECRET", raising=False)
    monkeypatch.delenv("BINANCE_FUTURES_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_FUTURES_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "BINANCE_API_KEY=spot-key",
                "BINANCE_SECRET=spot-secret",
                "BINANCE_FUTURES_API_KEY=futures-key",
                "BINANCE_FUTURES_SECRET=futures-secret",
            ]
        ),
        encoding="utf-8",
    )
    seen_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(request.headers["X-MBX-APIKEY"])
        return httpx.Response(200, json={} if request.url.path.endswith("/account") else [])

    transport = httpx.MockTransport(handler)
    spot = BinanceSpotTestnetClient.from_env(
        env_file=env_file,
        clock_ms=lambda: 1,
        transport=transport,
    )
    futures = BinanceFuturesTestnetClient.from_env(
        env_file=env_file,
        clock_ms=lambda: 1,
        transport=transport,
    )
    try:
        assert spot.account_info() == {}
        assert futures.balance() == []
    finally:
        futures.close()
        spot.close()

    assert seen_headers == ["spot-key", "futures-key"]


def test_smoke_blocks_flat_or_hedge_accounts_and_derives_safe_one_way_orders():
    exchange_info = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "filters": [
                    {
                        "filterType": "PRICE_FILTER",
                        "minPrice": "0.1",
                        "maxPrice": "1000000",
                        "tickSize": "0.1",
                    },
                    {
                        "filterType": "LOT_SIZE",
                        "minQty": "0.001",
                        "maxQty": "100",
                        "stepSize": "0.001",
                    },
                    {
                        "filterType": "MIN_NOTIONAL",
                        "notional": "5",
                    },
                    {
                        "filterType": "PERCENT_PRICE",
                        "multiplierDown": "0.95",
                        "multiplierUp": "1.05",
                    },
                ],
            }
        ]
    }

    class Spot:
        def __init__(self):
            self.order_calls: list[str] = []

        def account_info(self):
            return {"accountType": "SPOT", "canTrade": True, "balances": []}

        def book_ticker(self, _symbol):
            return {"bidPrice": "100000", "askPrice": "100001"}

        def exchange_info(self, _symbol):
            return exchange_info

        def test_limit_order(self, *_args):
            self.order_calls.append("test")
            return {}

        def place_limit_order(self, *_args, **_kwargs):
            self.order_calls.append("place")
            return {"orderId": 1, "status": "NEW"}

        def cancel_order(self, *_args, **_kwargs):
            self.order_calls.append("cancel")
            return {"orderId": 1, "status": "CANCELED"}

        def open_orders(self, *_args):
            self.order_calls.append("open")
            return []

    class Futures:
        def __init__(self, positions):
            self._positions = positions
            self.order_calls: list[str] = []

        def balance(self):
            return []

        def positions(self, _symbol=None):
            return self._positions

        def exchange_info(self):
            return exchange_info

        def book_ticker(self, _symbol):
            return {"bidPrice": "100000", "askPrice": "100001"}

        def test_limit_order(self, *_args):
            self.order_calls.append("test")
            raise AssertionError("flat/hedge preflight must block before futures order test")

        def place_limit_order(self, *_args):
            self.order_calls.append("place")
            raise AssertionError("flat/hedge preflight must block before futures order")

    unsafe_positions = [
        [{"symbol": "BTCUSDT", "positionAmt": "0", "positionSide": "BOTH"}],
        [{"symbol": "BTCUSDT", "positionAmt": "0.002", "positionSide": "LONG"}],
    ]
    for positions in unsafe_positions:
        spot = Spot()
        futures = Futures(positions)
        result = _run(
            spot,
            futures,
            spot_symbol="BTCUSDT",
            futures_symbol="BTCUSDT",
        )
        assert result["status"] == "partial"
        assert result["venues"]["spot"]["status"] == "ok"
        assert result["venues"]["futures"]["status"] == "blocked"
        assert spot.order_calls == ["test", "place", "cancel", "open"]
        assert futures.order_calls == []

    for position_amount, expected_side in (("0.002", "SELL"), ("-0.002", "BUY")):
        futures = Futures(
            [
                {
                    "symbol": "BTCUSDT",
                    "positionAmt": position_amount,
                    "positionSide": "BOTH",
                }
            ]
        )
        order = _safe_futures_order(
            futures,
            futures.positions(),
            exchange_info,
            "BTCUSDT",
        )
        assert order["side"] == expected_side
        assert Decimal(order["quantity"]) <= abs(Decimal(position_amount))


@pytest.mark.parametrize("venue", ["spot", "futures"])
@pytest.mark.parametrize("cancel_status", [200, 400])
def test_smoke_timeout_still_cancels_by_generated_client_id(
    venue: str,
    cancel_status: int,
):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            raise httpx.ReadTimeout("placement response was lost", request=request)
        if request.method == "DELETE":
            if cancel_status == 200:
                return httpx.Response(
                    200,
                    json={
                        "symbol": "BTCUSDT",
                        "origClientOrderId": request.url.params["origClientOrderId"],
                        "status": "CANCELED",
                    },
                )
            return httpx.Response(400, json={"code": -2011, "msg": "Unknown order"})
        raise AssertionError(f"unexpected request {request.method} {request.url.path}")

    transport = httpx.MockTransport(handler)
    if venue == "spot":
        client = BinanceSpotTestnetClient(
            "spot-key",
            "spot-secret",
            clock_ms=lambda: 1,
            transport=transport,
        )
        run_round_trip = lambda: _spot_round_trip(
            client,
            symbol="BTCUSDT",
            quantity="0.001",
            price="50000",
        )
        expected_path = "/api/v3/order"
    else:
        client = BinanceFuturesTestnetClient(
            "futures-key",
            "futures-secret",
            clock_ms=lambda: 1,
            transport=transport,
        )
        run_round_trip = lambda: _futures_round_trip(
            client,
            {
                "symbol": "BTCUSDT",
                "side": "SELL",
                "quantity": "0.001",
                "price": "120000",
            },
        )
        expected_path = "/fapi/v1/order"

    try:
        with pytest.raises(httpx.ReadTimeout, match="placement response was lost"):
            run_round_trip()
    finally:
        client.close()

    assert [(request.method, request.url.path) for request in requests] == [
        ("POST", expected_path),
        ("DELETE", expected_path),
    ]
    generated_id = requests[0].url.params["newClientOrderId"]
    assert 1 <= len(generated_id) <= 36
    assert requests[1].url.params["origClientOrderId"] == generated_id
    assert "orderId" not in requests[1].url.params
    if venue == "futures":
        assert requests[0].url.params["reduceOnly"] == "true"


def test_smoke_cli_reports_missing_keys_as_blocked_per_venue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    for name in (
        "BINANCE_API_KEY",
        "BINANCE_SECRET",
        "BINANCE_FUTURES_API_KEY",
        "BINANCE_FUTURES_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_binance_testnet_smoke.py",
            "--env-file",
            str(tmp_path / "absent.env"),
        ],
    )

    assert smoke_main() == 2
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "blocked"
    assert output["venues"]["spot"]["reason"] == "blocked-pending-user-key"
    assert output["venues"]["futures"]["reason"] == "blocked-pending-user-key"
