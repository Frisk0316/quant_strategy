from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from okx_quant.execution.deribit_live.private_client import DeribitPrivateClient


def _client(handler) -> DeribitPrivateClient:
    return DeribitPrivateClient(
        "unit-key",
        "unit-secret",
        transport=httpx.MockTransport(handler),
    )


def test_private_client_auth_and_method_request_shapes():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/public/auth"):
            return httpx.Response(200, json={"result": {"access_token": "token-1"}})
        if request.url.path.endswith("/private/get_positions"):
            return httpx.Response(200, json={"result": [{"instrument_name": "BTC-OPT"}]})
        if request.url.path.endswith("/private/get_account_summary"):
            return httpx.Response(200, json={"result": {"equity": 1.25}})
        if request.url.path.endswith("/private/cancel_all_by_currency"):
            return httpx.Response(200, json={"result": 2})
        return httpx.Response(
            200,
            json={
                "result": {
                    "order": {
                        "order_id": "order-1",
                        "order_state": "open",
                        "filled_amount": 0,
                    }
                }
            },
        )

    client = _client(handler)
    try:
        client.buy("BTC-30AUG26-100000-C", 0.1, 0.01, label="entry")
        client.sell("BTC-30AUG26-90000-P", 0.1, 0.02, reduce_only=True)
        client.cancel("order-1")
        assert client.cancel_all_by_currency("btc") == 2
        assert client.get_positions("BTC") == [{"instrument_name": "BTC-OPT"}]
        assert client.get_account_summary("BTC") == {"equity": 1.25}
    finally:
        client.close()

    auth = requests[0]
    assert auth.url.host == "test.deribit.com"
    assert auth.url.params["grant_type"] == "client_credentials"
    assert auth.url.params["client_id"] == "unit-key"
    assert auth.url.params["client_secret"] == "unit-secret"

    private = requests[1:]
    assert all(request.headers["Authorization"] == "Bearer token-1" for request in private)
    buy = private[0]
    assert buy.url.path.endswith("/private/buy")
    assert buy.url.params["type"] == "limit"
    assert buy.url.params["post_only"] == "true"
    assert "reduce_only" not in buy.url.params
    assert buy.url.params["label"] == "entry"

    sell = private[1]
    assert sell.url.path.endswith("/private/sell")
    assert sell.url.params["type"] == "limit"
    assert sell.url.params["post_only"] == "false"
    assert sell.url.params["reduce_only"] == "true"

    cancel = private[2]
    assert cancel.url.params["order_id"] == "order-1"
    cancel_all = private[3]
    assert cancel_all.url.params["currency"] == "BTC"
    assert cancel_all.url.params["kind"] == "option"
    positions = private[4]
    assert positions.url.params["currency"] == "BTC"
    assert positions.url.params["kind"] == "option"
    summary = private[5]
    assert summary.url.params["currency"] == "BTC"
    assert summary.url.params["extended"] == "false"


def test_private_client_refreshes_once_after_401():
    auth_count = 0
    private_tokens: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal auth_count
        if request.url.path.endswith("/public/auth"):
            auth_count += 1
            return httpx.Response(200, json={"result": {"access_token": f"token-{auth_count}"}})
        private_tokens.append(request.headers["Authorization"])
        if len(private_tokens) == 1:
            return httpx.Response(401, json={"error": {"message": "expired"}})
        return httpx.Response(200, json={"result": {"equity": 2.0}})

    client = _client(handler)
    try:
        assert client.get_account_summary("ETH") == {"equity": 2.0}
    finally:
        client.close()

    assert auth_count == 2
    assert private_tokens == ["Bearer token-1", "Bearer token-2"]


def test_private_client_second_401_fails_closed():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/public/auth"):
            return httpx.Response(200, json={"result": {"access_token": "token"}})
        return httpx.Response(401, json={"error": {"message": "still expired"}})

    client = _client(handler)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            client.get_positions("BTC")
    finally:
        client.close()


def test_private_client_loads_dotenv_and_rejects_missing_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("DERIBIT_API_KEY", raising=False)
    monkeypatch.delenv("DERIBIT_API_SECRET", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DERIBIT_API_KEY=from-file\nDERIBIT_API_SECRET=file-secret\n",
        encoding="utf-8",
    )
    client = DeribitPrivateClient.from_env(
        env_file=env_file,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={"result": {"access_token": "unused"}},
            )
        ),
    )
    client.close()

    with pytest.raises(RuntimeError, match="DERIBIT_API_KEY and DERIBIT_API_SECRET"):
        DeribitPrivateClient.from_env(env_file=tmp_path / "absent")


def test_plain_taker_order_is_not_expressible():
    assert "type" not in DeribitPrivateClient.buy.__annotations__
    assert "post_only" not in DeribitPrivateClient.buy.__annotations__
    assert "type" not in DeribitPrivateClient.sell.__annotations__
    assert "post_only" not in DeribitPrivateClient.sell.__annotations__
