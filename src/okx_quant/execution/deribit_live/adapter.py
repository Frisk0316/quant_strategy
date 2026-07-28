"""Thin ADR-0017 adapter over the frozen ADR-0011 H-014 intent path."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml
from dotenv import dotenv_values
from loguru import logger

from okx_quant.execution.deribit_shadow import runner as shadow_runner
from okx_quant.monitoring.telegram_alert import TelegramMonitor

from .private_client import DeribitPrivateClient

_OPTION_NAME = re.compile(r"^(BTC|ETH)-\d{1,2}[A-Z]{3}\d{2}-\d+(?:\.\d+)?-[CP]$")


class OrderRejectedError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveConfig:
    enabled: bool = False
    max_notional_per_symbol: float = 5_000.0
    max_notional_aggregate: float = 10_000.0
    daily_loss_stop: float = 500.0
    drawdown_reduce_only_threshold: float = 0.10
    env: str = "test"
    reprice_interval_seconds: float = 30.0
    max_reprices: int = 3

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "LiveConfig":
        values = raw.get("h014_live", raw)
        config = cls(**dict(values))
        if not isinstance(config.enabled, bool):
            raise ValueError("h014_live.enabled must be true or false")
        if config.env not in {"test", "live"}:
            raise ValueError("h014_live.env must be 'test' or 'live'")
        for name in (
            "max_notional_per_symbol",
            "max_notional_aggregate",
            "daily_loss_stop",
        ):
            value = float(getattr(config, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"h014_live.{name} must be positive and finite")
        if not 0 < config.drawdown_reduce_only_threshold <= 1:
            raise ValueError(
                "h014_live.drawdown_reduce_only_threshold must be in (0, 1]"
            )
        if (
            not math.isfinite(config.reprice_interval_seconds)
            or config.reprice_interval_seconds < 0
        ):
            raise ValueError(
                "h014_live.reprice_interval_seconds must be finite and non-negative"
            )
        if (
            not isinstance(config.max_reprices, int)
            or isinstance(config.max_reprices, bool)
            or config.max_reprices < 0
        ):
            raise ValueError("h014_live.max_reprices must be a non-negative integer")
        return config


@dataclass(frozen=True)
class RiskSnapshot:
    daily_pnl_usd: float = 0.0
    drawdown: float = 0.0
    notional_by_symbol: Mapping[str, float] = field(default_factory=dict)


def load_live_config(path: str | Path = "config/risk.yaml") -> LiveConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if "h014_live" not in raw:
        raise RuntimeError("config/risk.yaml is missing the h014_live block")
    return LiveConfig.from_mapping(raw)


def set_reduce_only_state(path: str | Path, reason: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "enabled": True,
        "reason": str(reason),
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)


@contextmanager
def _journal_lock(path: str | Path) -> Iterator[None]:
    lock_path = Path(f"{path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError("another H-014 live journal writer is running") from exc
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _append_jsonl(path: str | Path, record: dict[str, Any]) -> bool:
    target = Path(path)
    with _journal_lock(target):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            # ponytail: O(n) dedupe is enough for v1; add an index if the journal becomes large.
            for line in target.read_text(encoding="utf-8").splitlines():
                if json.loads(line).get("event_id") == record["event_id"]:
                    return False
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return True


def _default_notify(event: str, message: str) -> None:
    level = "ERROR" if event in {"rejection", "risk_stop", "adapter_failure"} else "INFO"
    logger.log(level, "H-014 live {}: {}", event, message)
    values = dotenv_values(".env") if Path(".env").exists() else {}
    token = os.environ.get("TELEGRAM_TOKEN") or values.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or values.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        # TODO: configure Telegram before activation; log-only is the approved fallback.
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:

        async def send() -> None:
            monitor = TelegramMonitor(token, chat_id)
            try:
                await monitor.send_alert(
                    f"H-014 live {event}: {message}",
                    level="critical" if level == "ERROR" else "info",
                )
            finally:
                await monitor._client.aclose()

        asyncio.run(send())
    else:
        logger.warning("H-014 live Telegram alert skipped inside an active event loop")


class H014LiveAdapter:
    def __init__(
        self,
        config: LiveConfig,
        *,
        client: DeribitPrivateClient | None = None,
        quote_provider: Callable[[str], Mapping[str, Any]] | None = None,
        live_journal_path: str | Path = "results/live_h014/orders.jsonl",
        shadow_journal_path: str | Path = "results/shadow_h014/journal.jsonl",
        reduce_only_state_path: str | Path = "results/live_h014/reduce_only.flag",
        sleep: Callable[[float], None] = time.sleep,
        notifier: Callable[[str, str], None] = _default_notify,
    ) -> None:
        if config.enabled and client is None:
            raise RuntimeError("enabled H-014 live adapter requires a private client")
        self.config = config
        self.client = client
        self.quote_provider = quote_provider
        self.live_journal_path = Path(live_journal_path)
        self.shadow_journal_path = Path(shadow_journal_path)
        self.reduce_only_state_path = Path(reduce_only_state_path)
        self.sleep = sleep
        self.notifier = notifier

    def _notify(self, event: str, message: str) -> None:
        try:
            self.notifier(event, message)
        except Exception as exc:
            logger.warning("H-014 live notification failed", event=event, exc=str(exc))

    def close(self) -> None:
        if self.client is not None:
            self.client.close()

    @classmethod
    def from_config(
        cls,
        config: LiveConfig,
        *,
        client_factory: Callable[[str], DeribitPrivateClient] | None = None,
        env_file: str | Path = ".env",
        **kwargs: Any,
    ) -> "H014LiveAdapter":
        if not config.enabled:
            return cls(config, client=None, **kwargs)
        client = (
            client_factory(config.env)
            if client_factory
            else DeribitPrivateClient.from_env(env=config.env, env_file=env_file)
        )
        return cls(config, client=client, **kwargs)

    @staticmethod
    def build_intents(
        currency: str,
        signal: dict[str, Any],
        instruments: list[dict[str, Any]],
        now: datetime,
    ) -> list[dict[str, Any]]:
        return shadow_runner.build_intent_legs(currency, signal, instruments, now)

    def _append_shadow(self, record: dict[str, Any]) -> tuple[bool, float]:
        with shadow_runner._journal_cycle_lock(self.shadow_journal_path):
            journal = shadow_runner.Journal(self.shadow_journal_path)
            event_date = datetime.fromisoformat(str(record["event_date"])).date()
            existing = next(
                (
                    row
                    for row in journal.records
                    if row["event_id"] == str(record["event_id"])
                ),
                None,
            )
            if existing is not None and existing != record:
                raise ValueError("shadow event_id already exists with different content")
            open_units = shadow_runner._open_units(
                journal,
                str(record["currency"]).upper(),
                event_date,
            )
            if (
                existing is not None
                and record.get("status") == "filled"
                and datetime.fromisoformat(str(record["intent"]["expiry"])).date() > event_date
            ):
                open_units = max(0.0, open_units - float(record["intent"]["units"]))
            return journal.append(record), open_units

    def _event(
        self,
        event_type: str,
        intent_id: str,
        *,
        suffix: str,
        **values: Any,
    ) -> bool:
        return _append_jsonl(
            self.live_journal_path,
            {
                "schema_version": 1,
                "event_id": f"{event_type}:{intent_id}:{suffix}",
                "event_type": event_type,
                "intent_id": intent_id,
                "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                **values,
            },
        )

    def _validate_entry(
        self,
        record: Mapping[str, Any],
        legs: list[dict[str, Any]],
        *,
        open_units: float,
        risk: RiskSnapshot,
    ) -> None:
        currency = str(record.get("currency") or "").upper()
        for leg in legs:
            self._validate_leg(leg, currency)
        tranche_units = max(float(leg["units"]) for leg in legs)
        shadow_runner.validate_intent_set(
            legs,
            tranche_units=tranche_units,
            open_units=open_units,
            unit_cap=shadow_runner.FROZEN_UNIT_CAP,
        )
        signal_price = float((record.get("signal") or {}).get("px") or 0)
        if not math.isfinite(signal_price) or signal_price <= 0:
            raise ValueError("H-014 live signal price must be positive and finite")
        proposed = tranche_units * signal_price
        current = {
            str(key).upper(): float(value)
            for key, value in risk.notional_by_symbol.items()
        }
        if any(not math.isfinite(value) or value < 0 for value in current.values()):
            raise ValueError("H-014 live existing notionals must be finite and non-negative")
        if current.get(currency, 0.0) + proposed > self.config.max_notional_per_symbol:
            raise ValueError(f"H-014 live per-symbol notional cap exceeded for {currency}")
        if sum(current.values()) + proposed > self.config.max_notional_aggregate:
            raise ValueError("H-014 live aggregate notional cap exceeded")

    @staticmethod
    def _validate_leg(leg: Mapping[str, Any], currency: str) -> None:
        instrument = str(leg.get("instrument") or "")
        match = _OPTION_NAME.fullmatch(instrument)
        kind = str(leg.get("kind") or "")
        side = str(leg.get("side") or "")
        if (
            not match
            or match.group(1) != currency
            or str(leg.get("currency") or "").upper() != currency
            or side not in {"buy", "sell"}
            or kind not in {"call", "put"}
            or (instrument.endswith("-C")) != (kind == "call")
        ):
            raise ValueError(f"instrument is not an allow-listed BTC/ETH option: {instrument}")

    def _risk_stop_reason(self, risk: RiskSnapshot) -> str | None:
        if (
            not math.isfinite(risk.daily_pnl_usd)
            or not math.isfinite(risk.drawdown)
            or risk.drawdown < 0
        ):
            return "invalid risk snapshot"
        if risk.daily_pnl_usd <= -self.config.daily_loss_stop:
            return (
                f"daily loss {risk.daily_pnl_usd} breached "
                f"-{self.config.daily_loss_stop}"
            )
        if risk.drawdown >= self.config.drawdown_reduce_only_threshold:
            return (
                f"drawdown {risk.drawdown} breached "
                f"{self.config.drawdown_reduce_only_threshold}"
            )
        if self.reduce_only_state_path.exists():
            return "persistent reduce-only state is active"
        return None

    @staticmethod
    def _order_view(result: Mapping[str, Any]) -> Mapping[str, Any]:
        order = result.get("order")
        return order if isinstance(order, Mapping) else result

    def _execute_leg(
        self,
        intent_id: str,
        currency: str,
        leg: dict[str, Any],
        *,
        reduce_only: bool,
    ) -> dict[str, Any]:
        if self.client is None or self.quote_provider is None:
            raise RuntimeError("enabled H-014 live execution requires client and quote provider")
        instrument = str(leg["instrument"])
        side = str(leg["side"])
        requested = float(leg["units"])
        filled_total = 0.0
        for attempt in range(self.config.max_reprices + 1):
            quote = self.quote_provider(instrument)
            price = float(quote["bid"] if side == "buy" else quote["ask"])
            remaining = requested - filled_total
            method = self.client.buy if side == "buy" else self.client.sell
            recorded = self._event(
                "order_attempt",
                intent_id,
                suffix=f"{leg['leg']}:{attempt}",
                currency=currency,
                instrument=instrument,
                leg=leg["leg"],
                side=side,
                amount=remaining,
                price=price,
                post_only=not reduce_only,
                reduce_only=reduce_only,
                attempt=attempt,
            )
            if not recorded:
                raise RuntimeError(
                    f"duplicate H-014 order attempt refused for {instrument} attempt {attempt}"
                )
            result = method(
                instrument,
                remaining,
                price,
                reduce_only=reduce_only,
                label=f"h014:{intent_id}:{leg['leg']}",
            )
            order = self._order_view(result)
            order_id = str(order.get("order_id") or "")
            order_filled = min(remaining, float(order.get("filled_amount") or 0))
            filled_total += order_filled
            if order.get("order_state") == "rejected":
                raise OrderRejectedError(f"Deribit rejected {instrument}")
            self._notify("order_placement", f"{side} {instrument} attempt {attempt}")
            if order_filled:
                self._event(
                    "fill",
                    intent_id,
                    suffix=f"{leg['leg']}:{attempt}",
                    currency=currency,
                    instrument=instrument,
                    leg=leg["leg"],
                    filled_amount=order_filled,
                    cumulative_filled=filled_total,
                    average_price=order.get("average_price"),
                )
            if filled_total + 1e-12 >= requested:
                return {"status": "filled", "filled_amount": filled_total}
            if not order_id:
                raise RuntimeError(f"Deribit returned no order_id for {instrument}")
            if attempt < self.config.max_reprices:
                self.sleep(self.config.reprice_interval_seconds)
            cancelled = self.client.cancel(order_id)
            cancel_filled = min(remaining, float(cancelled.get("filled_amount") or 0))
            if cancel_filled > order_filled:
                delta = cancel_filled - order_filled
                filled_total += delta
                self._event(
                    "fill",
                    intent_id,
                    suffix=f"{leg['leg']}:{attempt}:cancel",
                    currency=currency,
                    instrument=instrument,
                    leg=leg["leg"],
                    filled_amount=delta,
                    cumulative_filled=filled_total,
                    average_price=cancelled.get("average_price"),
                )
            if filled_total + 1e-12 >= requested:
                return {"status": "filled", "filled_amount": filled_total}
        self._event(
            "missed",
            intent_id,
            suffix=str(leg["leg"]),
            currency=currency,
            instrument=instrument,
            leg=leg["leg"],
            filled_amount=filled_total,
            requested_amount=requested,
        )
        return {"status": "missed", "filled_amount": filled_total}

    def execute_intent(
        self,
        shadow_record: dict[str, Any],
        *,
        open_units: float | None = None,
        risk: RiskSnapshot | None = None,
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        try:
            shadow_appended, journal_open_units = self._append_shadow(shadow_record)
        except Exception as exc:
            if self.config.enabled:
                self._notify("adapter_failure", f"shadow journal append failed: {exc}")
            raise
        if not self.config.enabled:
            return {"status": "disabled", "shadow_appended": shadow_appended}
        if shadow_record.get("status") != "filled":
            return {
                "status": f"shadow_{shadow_record.get('status')}",
                "shadow_appended": shadow_appended,
            }
        intent_id = str(shadow_record.get("intent_id") or shadow_record["event_id"])
        currency = str(shadow_record["currency"]).upper()
        legs = [dict(leg) for leg in shadow_record["legs"]]
        snapshot = risk or RiskSnapshot()
        try:
            if not reduce_only:
                provided_open_units = float(open_units or 0.0)
                if not math.isfinite(provided_open_units) or provided_open_units < 0:
                    raise ValueError("open_units must be finite and non-negative")
                self._validate_entry(
                    shadow_record,
                    legs,
                    open_units=max(journal_open_units, provided_open_units),
                    risk=snapshot,
                )
            else:
                for leg in legs:
                    self._validate_leg(leg, currency)
            stop_reason = self._risk_stop_reason(snapshot)
            if stop_reason and not reduce_only:
                set_reduce_only_state(self.reduce_only_state_path, stop_reason)
                self._event(
                    "risk_stop",
                    intent_id,
                    suffix="entry",
                    currency=currency,
                    reason=stop_reason,
                )
                self._notify("risk_stop", stop_reason)
                raise RuntimeError(f"H-014 live is reduce-only: {stop_reason}")
            # Establish the protective long put before either short option.
            ordered = sorted(
                legs,
                key=lambda leg: (
                    0 if leg.get("kind") == "put" and leg.get("side") == "buy" else 1,
                    str(leg.get("leg")),
                ),
            )
            outcomes = []
            for leg in ordered:
                outcome = self._execute_leg(
                    intent_id,
                    currency,
                    leg,
                    reduce_only=reduce_only,
                )
                outcomes.append(outcome)
                if outcome["status"] == "missed":
                    break
            status = "missed" if any(row["status"] == "missed" for row in outcomes) else "filled"
            return {
                "status": status,
                "shadow_appended": shadow_appended,
                "outcomes": outcomes,
            }
        except ValueError as exc:
            self._event(
                "reject",
                intent_id,
                suffix="validation",
                currency=currency,
                reason=str(exc),
            )
            self._notify("rejection", str(exc))
            raise
        except OrderRejectedError as exc:
            self._event(
                "reject",
                intent_id,
                suffix="venue",
                currency=currency,
                reason=str(exc),
            )
            self._notify("rejection", str(exc))
            raise
        except RuntimeError as exc:
            if not str(exc).startswith("H-014 live is reduce-only"):
                self._event(
                    "adapter_failure",
                    intent_id,
                    suffix="runtime",
                    currency=currency,
                    reason=str(exc),
                )
                self._notify("adapter_failure", str(exc))
            raise
        except Exception as exc:
            self._event(
                "adapter_failure",
                intent_id,
                suffix="exception",
                currency=currency,
                reason=str(exc),
            )
            self._notify("adapter_failure", str(exc))
            raise
