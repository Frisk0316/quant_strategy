from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

import scripts.h014_live_panic as panic_script
from okx_quant.execution.deribit_live.adapter import (
    H014LiveAdapter,
    LiveConfig,
    ReduceOnlyError,
    RiskSnapshot,
    load_live_config,
)
from okx_quant.execution.deribit_shadow.runner import (
    FROZEN_TRANCHE_UNITS,
    Journal,
    build_intent_legs,
)
from scripts.h014_live_panic import run_panic


NOW = datetime(2026, 7, 28, 9, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _signal(currency: str = "BTC") -> dict:
    return {
        "date": "2026-07-27",
        "currency": currency,
        "instrument": f"{currency}-USDT-SWAP",
        "dvol": 60.0,
        "px": 50_000.0 if currency == "BTC" else 3_000.0,
        "rv": 40.0,
        "vrp": 20.0,
        "z": 0.75,
        "ivp": 90.0,
        "rich": True,
        "as_of": "2026-07-28T08:00:00Z",
        "source": "db_f26_asof",
    }


def _instruments(currency: str = "BTC") -> list[dict]:
    expiry = int((NOW + timedelta(days=30)).timestamp() * 1000)
    expiry_name = "27AUG26"
    base = 50_000 if currency == "BTC" else 3_000
    rows = []
    for strike in (base * 1.1, base * 1.2):
        rows.append(
            {
                "instrument_name": f"{currency}-{expiry_name}-{strike:g}-C",
                "expiration_timestamp": expiry,
                "option_type": "call",
                "strike": strike,
            }
        )
    for strike in (base * 0.9, base * 0.8, base * 0.7):
        rows.append(
            {
                "instrument_name": f"{currency}-{expiry_name}-{strike:g}-P",
                "expiration_timestamp": expiry,
                "option_type": "put",
                "strike": strike,
            }
        )
    return rows


def _record(currency: str = "BTC") -> dict:
    signal = _signal(currency)
    legs = build_intent_legs(currency, signal, _instruments(currency), NOW)
    for leg in legs:
        leg["position_id"] = f"h014:2026-07-28:2026-07-27:{currency}:{leg['leg']}"
        leg["book"] = {"bid": 0.01, "ask": 0.02}
        leg["fill"] = {"price_coin": 0.01, "units": leg["units"]}
    return {
        "schema_version": 1,
        "event_id": f"intent:h014:2026-07-28:2026-07-27:{currency}",
        "event_type": "intent",
        "intent_id": f"h014:2026-07-28:2026-07-27:{currency}",
        "ts": "2026-07-28T09:00:00Z",
        "event_date": "2026-07-28",
        "currency": currency,
        "signal": signal,
        "status": "filled",
        "intent": {
            "entry_date": "2026-07-28",
            "expiry": legs[0]["expiry"],
            "units": FROZEN_TRANCHE_UNITS,
        },
        "legs": legs,
        "pnl_coin": 0.0,
    }


class FakeClient:
    def __init__(self, *, state: str = "filled") -> None:
        self.state = state
        self.orders: list[dict] = []
        self.cancels: list[str] = []
        self.cancel_labels: list[tuple[str, str | None]] = []
        self.cancel_all: list[str] = []
        self.order_state_queries: list[str] = []
        self.events: list[tuple[str, object]] = []

    def _order(self, side, instrument, amount, price, **kwargs):
        order_id = f"order-{len(self.orders) + 1}"
        call = {
            "order_id": order_id,
            "side": side,
            "instrument": instrument,
            "amount": amount,
            "price": price,
            **kwargs,
        }
        self.orders.append(call)
        self.events.append(("order", order_id))
        return {
            "order": {
                "order_id": order_id,
                "order_state": self.state,
                "filled_amount": amount if self.state == "filled" else 0,
                "average_price": price if self.state == "filled" else 0,
            }
        }

    def buy(self, instrument, amount, price, **kwargs):
        return self._order("buy", instrument, amount, price, **kwargs)

    def sell(self, instrument, amount, price, **kwargs):
        return self._order("sell", instrument, amount, price, **kwargs)

    def cancel(self, order_id):
        self.cancels.append(order_id)
        self.events.append(("cancel", order_id))
        return {"order_id": order_id, "order_state": "cancelled", "filled_amount": 0}

    def cancel_by_label(self, label, *, currency=None):
        self.cancel_labels.append((label, currency))
        return 0

    def cancel_all_by_currency(self, currency):
        self.cancel_all.append(currency)
        return 0

    def get_order_state(self, order_id):
        self.order_state_queries.append(order_id)
        order = next(row for row in self.orders if row["order_id"] == order_id)
        return {
            "order_id": order_id,
            "order_state": self.state,
            "filled_amount": order["amount"] if self.state == "filled" else 0,
            "average_price": order["price"] if self.state == "filled" else 0,
        }


def _adapter(
    tmp_path: Path,
    *,
    enabled: bool = True,
    client: FakeClient | None = None,
    **config_overrides,
) -> H014LiveAdapter:
    config_values = {
        "enabled": enabled,
        "max_notional_per_symbol": 100_000,
        "max_notional_aggregate": 200_000,
        "daily_loss_stop": 500,
        "drawdown_reduce_only_threshold": 0.10,
        "reprice_interval_seconds": 1,
        "max_reprices": 0,
        **config_overrides,
    }
    config = LiveConfig(**config_values)
    return H014LiveAdapter(
        config,
        client=client,
        quote_provider=lambda _instrument: {"bid": 0.01, "ask": 0.02},
        live_journal_path=tmp_path / "live" / "orders.jsonl",
        shadow_journal_path=tmp_path / "shadow" / "journal.jsonl",
        reduce_only_state_path=tmp_path / "live" / "reduce_only.flag",
        sleep=lambda _seconds: None,
        notifier=lambda _event, _message: None,
    )


def test_disabled_adapter_does_not_construct_client_and_keeps_shadow_journal(tmp_path: Path):
    constructed = []
    adapter = H014LiveAdapter.from_config(
        LiveConfig(enabled=False),
        client_factory=lambda env: constructed.append(env),  # type: ignore[arg-type]
        shadow_journal_path=tmp_path / "shadow.jsonl",
        live_journal_path=tmp_path / "live.jsonl",
    )
    result = adapter.execute_intent(_record())

    assert result == {"status": "disabled", "shadow_appended": True}
    assert constructed == []
    assert Journal(tmp_path / "shadow.jsonl").records[0]["intent_id"] == _record()["intent_id"]
    assert not (tmp_path / "live.jsonl").exists()


def test_enabled_adapter_missing_credentials_fails_at_startup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("DERIBIT_API_KEY", raising=False)
    monkeypatch.delenv("DERIBIT_API_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="DERIBIT_API_KEY and DERIBIT_API_SECRET"):
        H014LiveAdapter.from_config(
            LiveConfig(enabled=True),
            env_file=tmp_path / "missing.env",
        )


def test_repo_live_config_is_disabled_and_testnet_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    config = load_live_config()
    assert config.enabled is False
    assert config.env == "test"
    assert config.reprice_interval_seconds == 30
    assert config.max_reprices == 3


def test_zero_reprice_interval_rejects_before_client_call():
    client = FakeClient()

    with pytest.raises(ValueError, match="positive and finite"):
        H014LiveAdapter(
            LiveConfig(enabled=True, reprice_interval_seconds=0),
            client=client,
        )

    assert client.orders == []


def test_adapter_and_panic_default_paths_are_repo_root_anchored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    adapter = H014LiveAdapter(LiveConfig(enabled=False))

    assert adapter.live_journal_path == REPO_ROOT / "results" / "live_h014" / "orders.jsonl"
    assert adapter.shadow_journal_path == REPO_ROOT / "results" / "shadow_h014" / "journal.jsonl"
    assert adapter.reduce_only_state_path == (
        REPO_ROOT / "results" / "live_h014" / "reduce_only.flag"
    )

    state_paths: list[Path] = []
    monkeypatch.setattr(
        panic_script,
        "set_reduce_only_state",
        lambda path, _reason: state_paths.append(Path(path)),
    )
    panic_script.run_panic(FakeClient(), dry_run=False)
    assert state_paths == [REPO_ROOT / "results" / "live_h014" / "reduce_only.flag"]


def test_live_intents_byte_match_shadow_builder(tmp_path: Path):
    signal = _signal()
    instruments = _instruments()
    adapter = _adapter(tmp_path, client=FakeClient())

    shadow = build_intent_legs("BTC", signal, instruments, NOW)
    live = adapter.build_intents("BTC", signal, instruments, NOW)

    compact = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"))
    assert compact(live) == compact(shadow)


def test_non_allowlisted_instrument_rejects_before_client_call(tmp_path: Path):
    client = FakeClient()
    adapter = _adapter(tmp_path, client=client)
    record = _record()
    record["legs"][0]["instrument"] = "SOL-27AUG26-100-C"

    with pytest.raises(ValueError, match="not an allow-listed"):
        adapter.execute_intent(record)

    assert client.orders == []
    rows = _live_rows(tmp_path)
    assert rows[-1]["event_type"] == "reject"


def test_naked_put_rejects_before_client_call(tmp_path: Path):
    client = FakeClient()
    adapter = _adapter(tmp_path, client=client)
    record = _record()
    record["legs"] = [leg for leg in record["legs"] if leg["leg"] != "put_10d"]

    with pytest.raises(ValueError, match="naked short put"):
        adapter.execute_intent(record)

    assert client.orders == []


@pytest.mark.parametrize(
    ("snapshot", "reason"),
    [
        (RiskSnapshot(daily_pnl_usd=-500), "daily loss"),
        (RiskSnapshot(drawdown=0.10), "drawdown"),
        (RiskSnapshot(drawdown=float("nan")), "invalid risk snapshot"),
    ],
)
def test_risk_stop_sets_reduce_only_and_rejects_new_entry(
    tmp_path: Path,
    snapshot: RiskSnapshot,
    reason: str,
):
    client = FakeClient()
    alerts: list[tuple[str, str]] = []
    adapter = _adapter(tmp_path, client=client)
    adapter.notifier = lambda event, message: alerts.append((event, message))

    with pytest.raises(ReduceOnlyError, match="reduce-only"):
        adapter.execute_intent(_record(), risk=snapshot)

    assert client.orders == []
    state = json.loads((tmp_path / "live" / "reduce_only.flag").read_text(encoding="utf-8"))
    assert reason in state["reason"]
    assert alerts[0][0] == "risk_stop"
    assert _live_rows(tmp_path)[-1]["event_type"] == "risk_stop"


def test_pre_existing_reduce_only_flag_blocks_fresh_adapter_entry(tmp_path: Path):
    state_path = tmp_path / "live" / "reduce_only.flag"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"enabled":true}\n', encoding="utf-8")
    client = FakeClient()
    adapter = _adapter(tmp_path, client=client)

    with pytest.raises(ReduceOnlyError, match="persistent reduce-only state"):
        adapter.execute_intent(_record())

    assert client.orders == []
    assert [row["event_type"] for row in _live_rows(tmp_path)] == ["risk_stop"]


def test_venue_rejection_is_journaled_as_reject(tmp_path: Path):
    client = FakeClient(state="rejected")
    adapter = _adapter(tmp_path, client=client)

    with pytest.raises(RuntimeError, match="Deribit rejected"):
        adapter.execute_intent(_record())

    assert [row["event_type"] for row in _live_rows(tmp_path)][-1] == "reject"


def test_notional_cap_rejects_before_client_call(tmp_path: Path):
    client = FakeClient()
    adapter = _adapter(tmp_path, client=client)
    adapter.config = LiveConfig(
        enabled=True,
        max_notional_per_symbol=1_000,
        max_notional_aggregate=2_000,
    )
    with pytest.raises(ValueError, match="per-symbol notional"):
        adapter.execute_intent(_record())
    assert client.orders == []


def test_unit_cap_uses_existing_shadow_journal_before_client_call(tmp_path: Path):
    client = FakeClient()
    adapter = _adapter(tmp_path, client=client)
    journal = Journal(adapter.shadow_journal_path)
    for index in range(30):
        prior = _record()
        prior["event_id"] = f"intent:prior:{index}"
        prior["intent_id"] = f"prior:{index}"
        journal.append(prior)

    with pytest.raises(ValueError, match="unit cap exceeded"):
        adapter.execute_intent(_record())

    assert client.orders == []


def test_already_appended_shadow_record_can_be_consumed_once(tmp_path: Path):
    client = FakeClient()
    adapter = _adapter(tmp_path, client=client)
    record = _record()
    Journal(adapter.shadow_journal_path).append(record)

    result = adapter.execute_intent(record)

    assert result["shadow_appended"] is False
    assert result["status"] == "filled"
    assert len(client.orders) == 3


def test_shadow_event_id_collision_fails_before_client_call(tmp_path: Path):
    client = FakeClient()
    adapter = _adapter(tmp_path, client=client)
    record = _record()
    Journal(adapter.shadow_journal_path).append(record)
    record["legs"][0]["instrument"] = "BTC-27AUG26-1-C"

    with pytest.raises(ValueError, match="different content"):
        adapter.execute_intent(record)

    assert client.orders == []


def test_filled_intent_orders_protection_first_and_journals_attempts_and_fills(
    tmp_path: Path,
):
    client = FakeClient()
    adapter = _adapter(tmp_path, client=client)
    alerts: list[tuple[str, str]] = []
    adapter.notifier = lambda event, message: alerts.append((event, message))

    result = adapter.execute_intent(_record())

    assert result["status"] == "filled"
    assert client.orders[0]["side"] == "buy"
    assert client.orders[0]["instrument"].endswith("-P")
    assert all(call["reduce_only"] is False for call in client.orders)
    rows = _live_rows(tmp_path)
    assert [row["event_type"] for row in rows].count("order_attempt") == 3
    assert [row["event_type"] for row in rows].count("fill") == 3
    assert [event for event, _message in alerts] == ["order_placement"] * 3
    assert (tmp_path / "live" / "orders.jsonl.lock").exists()


def test_adapter_failure_is_journaled_and_alerted(tmp_path: Path):
    client = FakeClient()
    alerts: list[tuple[str, str]] = []
    adapter = _adapter(tmp_path, client=client)
    adapter.quote_provider = lambda _instrument: (_ for _ in ()).throw(OSError("book down"))
    adapter.notifier = lambda event, message: alerts.append((event, message))

    with pytest.raises(OSError, match="book down"):
        adapter.execute_intent(_record())

    assert _live_rows(tmp_path)[-1]["event_type"] == "adapter_failure"
    assert alerts == [("adapter_failure", "book down")]


def test_bounded_reprices_cancel_then_journal_missed(tmp_path: Path):
    client = FakeClient(state="open")
    adapter = _adapter(tmp_path, client=client)
    adapter.config = LiveConfig(
        enabled=True,
        max_notional_per_symbol=100_000,
        max_notional_aggregate=200_000,
        reprice_interval_seconds=5,
        max_reprices=1,
    )
    adapter.sleep = lambda seconds: client.events.append(("sleep", seconds))

    result = adapter.execute_intent(_record())

    assert result["status"] == "missed"
    assert len(client.orders) == 2
    assert len(client.cancels) == 2
    assert client.events == [
        ("order", "order-1"),
        ("sleep", 5),
        ("cancel", "order-1"),
        ("order", "order-2"),
        ("sleep", 5),
        ("cancel", "order-2"),
    ]
    assert _live_rows(tmp_path)[-1]["event_type"] == "missed"


def test_cancel_error_reconciles_fill_and_continues_sibling_legs(tmp_path: Path):
    class FilledDuringCancelClient(FakeClient):
        def __init__(self):
            super().__init__(state="open")

        def cancel(self, order_id):
            self.cancels.append(order_id)
            raise RuntimeError("order is no longer open")

        def get_order_state(self, order_id):
            self.order_state_queries.append(order_id)
            order = next(row for row in self.orders if row["order_id"] == order_id)
            return {
                "order_id": order_id,
                "order_state": "filled",
                "filled_amount": order["amount"],
                "average_price": order["price"],
            }

    client = FilledDuringCancelClient()
    adapter = _adapter(tmp_path, client=client)

    result = adapter.execute_intent(_record())

    assert result["status"] == "filled"
    assert len(client.orders) == 3
    assert client.order_state_queries == ["order-1", "order-2", "order-3"]
    event_types = [row["event_type"] for row in _live_rows(tmp_path)]
    assert event_types.count("fill") == 3
    assert "adapter_failure" not in event_types


def test_cancel_error_reconciles_terminal_partial_fill_before_reprice(
    tmp_path: Path,
):
    class PartialDuringCancelClient(FakeClient):
        def __init__(self):
            super().__init__(state="open")

        def _order(self, side, instrument, amount, price, **kwargs):
            result = super()._order(side, instrument, amount, price, **kwargs)
            if len(self.orders) == 2:
                result["order"].update(
                    order_state="filled",
                    filled_amount=amount,
                    average_price=price,
                )
            return result

        def cancel(self, order_id):
            self.cancels.append(order_id)
            raise RuntimeError("cancel response lost")

        def get_order_state(self, order_id):
            self.order_state_queries.append(order_id)
            order = self.orders[0]
            return {
                "order_id": order_id,
                "order_state": "cancelled",
                "filled_amount": order["amount"] / 2,
                "average_price": order["price"],
            }

    client = PartialDuringCancelClient()
    adapter = _adapter(tmp_path, client=client)
    adapter.config = LiveConfig(
        enabled=True,
        max_notional_per_symbol=100_000,
        max_notional_aggregate=200_000,
        reprice_interval_seconds=5,
        max_reprices=1,
    )
    leg = next(row for row in _record()["legs"] if row["leg"] == "put_10d")

    outcome = adapter._execute_leg("partial-intent", "BTC", leg, reduce_only=False)

    assert outcome == {"status": "filled", "filled_amount": pytest.approx(leg["units"])}
    fills = [row for row in _live_rows(tmp_path) if row["event_type"] == "fill"]
    assert len(fills) == 2
    assert fills[-1]["cumulative_filled"] == pytest.approx(leg["units"])


def test_cancel_error_sweeps_open_partial_before_reprice(tmp_path: Path):
    class OpenPartialDuringCancelClient(FakeClient):
        def __init__(self):
            super().__init__(state="open")
            self.swept = False

        def _order(self, side, instrument, amount, price, **kwargs):
            result = super()._order(side, instrument, amount, price, **kwargs)
            if len(self.orders) == 2:
                result["order"].update(
                    order_state="filled",
                    filled_amount=amount,
                    average_price=price,
                )
            return result

        def cancel(self, order_id):
            self.cancels.append(order_id)
            raise RuntimeError("cancel response lost")

        def cancel_by_label(self, label, *, currency=None):
            self.cancel_labels.append((label, currency))
            self.swept = True
            return 1

        def get_order_state(self, order_id):
            self.order_state_queries.append(order_id)
            order = self.orders[0]
            return {
                "order_id": order_id,
                "order_state": "cancelled" if self.swept else "open",
                "filled_amount": order["amount"] / 2,
                "average_price": order["price"],
            }

    client = OpenPartialDuringCancelClient()
    adapter = _adapter(
        tmp_path,
        client=client,
        reprice_interval_seconds=5,
        max_reprices=1,
    )
    leg = next(row for row in _record()["legs"] if row["leg"] == "put_10d")

    outcome = adapter._execute_leg("partial-open-intent", "BTC", leg, reduce_only=False)

    assert outcome == {"status": "filled", "filled_amount": pytest.approx(leg["units"])}
    assert client.order_state_queries == ["order-1", "order-1"]
    assert client.cancel_labels == [
        ("h014:partial-open-intent:put_10d", "BTC")
    ]
    fills = [row for row in _live_rows(tmp_path) if row["event_type"] == "fill"]
    assert len(fills) == 2
    assert fills[-1]["cumulative_filled"] == pytest.approx(leg["units"])
    assert any(row["event_type"] == "cancel_sweep" for row in _live_rows(tmp_path))


def test_transport_error_attempts_label_sweep_and_reraises_original(tmp_path: Path):
    class LostResponseClient(FakeClient):
        def __init__(self, error):
            super().__init__(state="open")
            self.error = error

        def buy(self, instrument, amount, price, **kwargs):
            self._order("buy", instrument, amount, price, **kwargs)
            raise self.error

    error = httpx.ReadTimeout(
        "response lost after send",
        request=httpx.Request("GET", "https://test.deribit.com/api/v2/private/buy"),
    )
    client = LostResponseClient(error)
    adapter = _adapter(tmp_path, client=client)

    with pytest.raises(httpx.ReadTimeout) as caught:
        adapter.execute_intent(_record())

    assert caught.value is error
    assert client.cancel_labels == [
        ("h014:h014:2026-07-28:2026-07-27:BTC:put_10d", "BTC")
    ]
    assert client.cancel_all == []
    sweep = next(row for row in _live_rows(tmp_path) if row["event_type"] == "cancel_sweep")
    assert sweep["scope"] == "label"
    assert sweep["status"] == "succeeded"


def test_failed_cancel_sweep_does_not_mask_transport_error(tmp_path: Path):
    class FailedSweepClient(FakeClient):
        def __init__(self, error):
            super().__init__(state="open")
            self.error = error

        def buy(self, instrument, amount, price, **kwargs):
            self._order("buy", instrument, amount, price, **kwargs)
            raise self.error

        def cancel_by_label(self, label, *, currency=None):
            self.cancel_labels.append((label, currency))
            raise RuntimeError("label sweep failed")

        def cancel_all_by_currency(self, currency):
            self.cancel_all.append(currency)
            raise RuntimeError("currency sweep failed")

    error = httpx.ConnectError(
        "connection lost after send",
        request=httpx.Request("GET", "https://test.deribit.com/api/v2/private/buy"),
    )
    client = FailedSweepClient(error)
    adapter = _adapter(tmp_path, client=client)

    with pytest.raises(httpx.ConnectError) as caught:
        adapter.execute_intent(_record())

    assert caught.value is error
    assert client.cancel_labels
    assert client.cancel_all == ["BTC"]
    sweep = next(row for row in _live_rows(tmp_path) if row["event_type"] == "cancel_sweep")
    assert sweep["scope"] == "currency"
    assert sweep["status"] == "failed"


def test_panic_dry_run_calls_both_currencies_without_writing_state(tmp_path: Path):
    client = FakeClient()
    state = tmp_path / "reduce_only.flag"

    result = run_panic(client, state_path=state, dry_run=True)

    assert client.cancel_all == ["BTC", "ETH"]
    assert result["reduce_only"] is False
    assert not state.exists()


def _live_rows(tmp_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (tmp_path / "live" / "orders.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
