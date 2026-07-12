"""Unit tests for MarketDataHandler public-channel handling.

Covers the regression where a book seq-gap / checksum desync tore down the
whole public WS connection (books + trades + funding) and caused reconnect
churn. The fix re-subscribes only the affected book channel inline.
"""
from __future__ import annotations

import json

from okx_quant.data.market_data_handler import MarketDataHandler
from okx_quant.data.okx_book import OkxBook

INST = "BTC-USDT-SWAP"


class _FakeBus:
    def __init__(self) -> None:
        self.events: list = []

    async def put(self, event) -> None:
        self.events.append(event)


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, data: str) -> None:
        self.sent.append(json.loads(data))


class _LoginFailureWS(_FakeWS):
    async def recv(self) -> str:
        return json.dumps({"event": "error", "code": "60005", "msg": "Invalid apiKey"})


class _ConnectOnce:
    def __init__(self, ws) -> None:
        self.ws = ws
        self.yielded = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.yielded:
            raise AssertionError("terminal authentication failure must not reconnect")
        self.yielded = True
        return self.ws


def _handler() -> MarketDataHandler:
    return MarketDataHandler(
        bus=_FakeBus(), symbols=[INST], api_key="", secret="", passphrase=""
    )


def _snapshot(seq_id: int) -> dict:
    ref = OkxBook(INST)
    ref._apply("bids", [["100.0", "10.0"]])
    ref._apply("asks", [["100.1", "8.0"]])
    return {
        "arg": {"channel": "books", "instId": INST},
        "action": "snapshot",
        "data": [{
            "bids": [["100.0", "10.0", "0", "1"]],
            "asks": [["100.1", "8.0", "0", "1"]],
            "seqId": seq_id,
            "prevSeqId": -1,
            "checksum": ref._checksum(),
            "ts": "1",
        }],
    }


async def test_book_desync_resubscribes_without_disconnect():
    mdh = _handler()
    ws = _FakeWS()

    await mdh._handle_public_message(ws, _snapshot(seq_id=1))

    bad_update = {
        "arg": {"channel": "books", "instId": INST},
        "action": "update",
        "data": [{
            "bids": [], "asks": [],
            "seqId": 5, "prevSeqId": 3,  # gap: expected prevSeqId == 1
            "checksum": 0, "ts": "2",
        }],
    }
    # Must NOT raise — the old code re-raised and killed the connection.
    await mdh._handle_public_message(ws, bad_update)

    ops = [m["op"] for m in ws.sent]
    assert "unsubscribe" in ops and "subscribe" in ops
    # Stale book state was discarded (fresh empty book awaiting new snapshot).
    assert not mdh.books[INST].is_valid()


async def test_updates_after_resubscribe_do_not_storm():
    """After a resubscribe the book is empty; incoming updates that arrive
    before the fresh snapshot must be skipped, not trigger another resubscribe
    (which previously caused a tight desync/resubscribe loop)."""
    mdh = _handler()
    ws = _FakeWS()

    update = {
        "arg": {"channel": "books", "instId": INST},
        "action": "update",
        "data": [{
            "bids": [["100.0", "10.0", "0", "1"]], "asks": [],
            "seqId": 9, "prevSeqId": 8, "checksum": 0, "ts": "1",
        }],
    }
    # Fresh handler: book has no snapshot baseline yet.
    for _ in range(5):
        await mdh._handle_public_message(ws, update)

    assert ws.sent == []  # no unsubscribe/subscribe storm
    assert not mdh.books[INST].is_valid()


async def test_private_auth_failure_does_not_reconnect_or_trip_breaker(monkeypatch):
    mdh = _handler()
    connector = _ConnectOnce(_LoginFailureWS())
    monkeypatch.setattr("okx_quant.data.market_data_handler.websockets.connect", lambda *_args, **_kwargs: connector)

    await mdh.run_private()

    assert connector.yielded is True
    assert mdh._reconnect_times == []
