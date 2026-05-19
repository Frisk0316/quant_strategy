"""Research-only strategies driven by external feature observations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from okx_quant.core.events import Event, EvtType, FeaturePayload, SignalPayload
from okx_quant.data.okx_book import OkxBook
from okx_quant.strategies.base import Strategy

_FNG_LABELS = {
    "extreme fear": "Extreme Fear",
    "fear": "Fear",
    "neutral": "Neutral",
    "greed": "Greed",
    "extreme greed": "Extreme Greed",
}


def _event_ts(payload: object) -> int:
    return int(getattr(payload, "ts", 0) or 0)


def _feature_time(payload: FeaturePayload) -> int:
    return int(payload.published_at or payload.observed_at or payload.ts)


def _feature_age_seconds(payload: FeaturePayload, ts: int) -> float:
    feature_ts = _feature_time(payload)
    return max(0.0, (int(ts) - feature_ts) / 1000.0)


def _book_mid(book: Optional[OkxBook]) -> Optional[float]:
    if book is None or not book.is_valid():
        return None
    return float(book.mid())


class FearGreedSentimentStrategy(Strategy):
    """Long/flat BTC research strategy using Fear & Greed as-of values.

    Neutral and Fear labels intentionally hold an existing position; exit waits
    for Greed/Extreme Greed or the configured numeric exit threshold.
    """

    def __init__(self, params: dict) -> None:
        super().__init__("fear_greed_sentiment", params)
        self.symbol = str(params.get("symbol") or "BTC-USDT-SWAP")
        self.dataset_id = str(params.get("dataset_id") or "fear_greed_btc")
        self.max_age_seconds = int(params.get("max_age_seconds", 48 * 3600))
        self.extreme_fear_label = _canonical_fng_label(params.get("extreme_fear_label") or "Extreme Fear")
        exit_labels = params.get("exit_labels") or ["Greed", "Extreme Greed"]
        self.exit_labels = {_canonical_fng_label(label) for label in exit_labels}
        self.extreme_fear_threshold = float(params.get("extreme_fear_threshold", 25.0))
        self.exit_value_threshold = float(params.get("exit_value_threshold", 51.0))
        self.max_missing_signal_ratio = float(params.get("max_missing_signal_ratio", 0.05))
        self.max_stale_signal_ratio = float(params.get("max_stale_signal_ratio", 0.05))
        self.td_mode = str(params.get("td_mode") or "cross")
        self._latest_feature: Optional[FeaturePayload] = None
        self._in_position = False
        self.coverage_status = {
            "dataset_id": self.dataset_id,
            "required": True,
            "market_event_count": 0,
            "missing_no_signal_count": 0,
            "stale_no_signal_count": 0,
            "missing_no_signal_ratio": 0.0,
            "stale_no_signal_ratio": 0.0,
            "max_missing_signal_ratio": self.max_missing_signal_ratio,
            "max_stale_signal_ratio": self.max_stale_signal_ratio,
            "feature_gate_passed": True,
            "last_feature_ts": None,
            "last_feature_value_text": None,
        }

    async def on_market(
        self,
        event: Event,
        book: Optional[OkxBook] = None,
    ) -> Optional[SignalPayload]:
        if event.type == EvtType.FEATURE:
            payload = event.payload
            if isinstance(payload, FeaturePayload) and payload.dataset_id == self.dataset_id:
                payload.value_text = _canonical_fng_label(payload.value_text or "")
                self._latest_feature = payload
                self.coverage_status["last_feature_ts"] = payload.ts
                self.coverage_status["last_feature_value_text"] = payload.value_text
            return None

        payload = event.payload
        if getattr(payload, "inst_id", None) != self.symbol or getattr(payload, "channel", "") != "books":
            return None
        price = _book_mid(book)
        if price is None:
            return None
        self._record_market_event()
        feature = self._latest_feature
        if feature is None:
            self.coverage_status["missing_no_signal_count"] += 1
            self._refresh_feature_gate()
            return None
        if _feature_age_seconds(feature, _event_ts(payload)) > self.max_age_seconds:
            self.coverage_status["stale_no_signal_count"] += 1
            self._refresh_feature_gate()
            return None

        label = _canonical_fng_label(feature.value_text or "")
        value_num = _optional_float(feature.value_num)
        metadata = {
            "dataset_id": self.dataset_id,
            "feature_observed_at": feature.observed_at,
            "feature_published_at": feature.published_at,
            "feature_value_num": feature.value_num,
            "feature_value_text": label,
            "extreme_fear_threshold": self.extreme_fear_threshold,
            "exit_value_threshold": self.exit_value_threshold,
            "feature_age_seconds": _feature_age_seconds(feature, _event_ts(payload)),
            "cancel_existing": True,
            "mode": "long_flat",
            "td_mode": self.td_mode,
            "research_only": True,
        }
        is_extreme_fear = label == self.extreme_fear_label or (
            value_num is not None and value_num <= self.extreme_fear_threshold
        )
        is_exit = label in self.exit_labels or (
            value_num is not None and value_num >= self.exit_value_threshold
        )
        if is_extreme_fear and not self._in_position:
            return SignalPayload(
                strategy=self.name,
                inst_id=self.symbol,
                side="buy",
                strength=max(0.0, float(self.size_multiplier)),
                fair_value=price,
                metadata={**metadata, "action": "entry"},
            )
        if is_exit and self._in_position:
            return SignalPayload(
                strategy=self.name,
                inst_id=self.symbol,
                side="sell",
                strength=max(0.0, float(self.size_multiplier)),
                fair_value=price,
                metadata={**metadata, "action": "exit"},
            )
        return None

    def _record_market_event(self) -> None:
        self.coverage_status["market_event_count"] += 1
        self._refresh_feature_gate()

    def _refresh_feature_gate(self) -> None:
        total = max(1, int(self.coverage_status["market_event_count"]))
        missing_ratio = float(self.coverage_status["missing_no_signal_count"]) / total
        stale_ratio = float(self.coverage_status["stale_no_signal_count"]) / total
        self.coverage_status["missing_no_signal_ratio"] = missing_ratio
        self.coverage_status["stale_no_signal_ratio"] = stale_ratio
        self.coverage_status["feature_gate_passed"] = (
            missing_ratio <= self.max_missing_signal_ratio
            and stale_ratio <= self.max_stale_signal_ratio
        )

    async def on_fill(self, event: Event) -> None:
        fill = event.payload
        if fill.strategy != self.name or fill.inst_id != self.symbol or fill.fill_sz <= 0:
            return
        if fill.side == "buy":
            self._in_position = True
        elif fill.side == "sell":
            remaining = fill.metadata.get("remaining_sz") if fill.metadata else None
            try:
                remaining_sz = float(remaining)
            except (TypeError, ValueError):
                remaining_sz = 0.0 if fill.state == "filled" else float("inf")
            if fill.state == "filled" or remaining_sz <= 1e-12:
                self._in_position = False


@dataclass
class _ActiveGap:
    direction: str
    cme_target_price: float
    cme_gap_open_price: float
    gap_bps: float
    detected_ts: int
    expires_at: int
    entered: bool = False
    entry_side: Optional[str] = None
    okx_entry_anchor_price: Optional[float] = None
    okx_target_price: Optional[float] = None


class CMEGapFillStrategy(Strategy):
    """Delayed daily CME gap baseline for OKX BTC swap.

    This consumes daily CME observations after their publication policy. It is
    not an intraday real-time gap-fill implementation. The default direction
    filter is long_only, which is regime-fitted to the BTC 2024-26 uptrend and
    must be re-validated against bear-regime walk-forward before promotion.
    """

    def __init__(self, params: dict) -> None:
        super().__init__("cme_gap_fill", params)
        self.symbol = str(params.get("symbol") or "BTC-USDT-SWAP")
        self.dataset_id = str(params.get("dataset_id") or "cme_btc1_continuous")
        self.max_age_seconds = int(params.get("max_age_seconds", 7 * 86400))
        self.min_gap_bps = float(params.get("min_gap_bps", 25.0))
        self.max_hold_days = float(params.get("max_hold_days", 2.0))
        self.stop_loss_bps_mult = float(params.get("stop_loss_bps_mult", 1.5))
        self.max_gap_bps = float(params.get("max_gap_bps", 0.0))
        self.allow_direction = str(params.get("allow_direction") or "long_only")
        self.roll_dates = {str(d) for d in params.get("roll_dates", [])}
        self.max_missing_signal_ratio = float(params.get("max_missing_signal_ratio", 0.05))
        self.max_stale_signal_ratio = float(params.get("max_stale_signal_ratio", 0.05))
        self.td_mode = str(params.get("td_mode") or "cross")
        self._previous_feature: Optional[FeaturePayload] = None
        self._active_gap: Optional[_ActiveGap] = None
        self._in_position = False
        self.coverage_status = {
            "dataset_id": self.dataset_id,
            "required": True,
            "market_event_count": 0,
            "missing_no_signal_count": 0,
            "stale_no_signal_count": 0,
            "missing_no_signal_ratio": 0.0,
            "stale_no_signal_ratio": 0.0,
            "max_missing_signal_ratio": self.max_missing_signal_ratio,
            "max_stale_signal_ratio": self.max_stale_signal_ratio,
            "feature_gate_passed": True,
            "detected_gap_count": 0,
            "roll_skip_count": 0,
            "max_gap_skip_count": 0,
            "direction_skip_count": 0,
            "last_feature_ts": None,
        }

    async def on_market(
        self,
        event: Event,
        book: Optional[OkxBook] = None,
    ) -> Optional[SignalPayload]:
        if event.type == EvtType.FEATURE:
            payload = event.payload
            if isinstance(payload, FeaturePayload) and payload.dataset_id == self.dataset_id:
                self._handle_feature(payload)
            return None

        payload = event.payload
        if getattr(payload, "inst_id", None) != self.symbol or getattr(payload, "channel", "") != "books":
            return None
        price = _book_mid(book)
        if price is None:
            return None
        self._record_market_event()
        ts = _event_ts(payload)
        if self._previous_feature is None and self._active_gap is None:
            self.coverage_status["missing_no_signal_count"] += 1
            self._refresh_feature_gate()
            return None
        if (
            self._previous_feature
            and not self._in_position
            and _feature_age_seconds(self._previous_feature, ts) > self.max_age_seconds
        ):
            self.coverage_status["stale_no_signal_count"] += 1
            self._refresh_feature_gate()
            return None

        gap = self._active_gap
        if gap is None:
            return None
        if self._in_position:
            target = gap.okx_target_price
            if target is not None and self._target_touched(gap.direction, price, target):
                return self._gap_signal(gap, price, "exit", "target_fill")
            if self._stop_loss_touched(gap, price):
                return self._gap_signal(gap, price, "exit", "stop_loss")
            if ts >= gap.expires_at:
                return self._gap_signal(gap, price, "exit", "timeout")
            return None
        if not gap.entered:
            gap.entered = True
            gap.okx_entry_anchor_price = price
            gap.okx_target_price = self._okx_target_from_anchor(gap.direction, price, gap.gap_bps)
            return self._gap_signal(gap, price, "entry", "gap_open")
        return None

    def _handle_feature(self, payload: FeaturePayload) -> None:
        self.coverage_status["last_feature_ts"] = payload.ts
        current_open = _field_float(payload.fields, "open")
        current_observed = _payload_datetime(payload)
        previous = self._previous_feature
        if previous is not None and current_open is not None and current_observed is not None:
            prev_close = _field_float(previous.fields, "close")
            prev_observed = _payload_datetime(previous)
            if prev_close and prev_close > 0 and prev_observed is not None:
                if _is_roll_day(previous, self.roll_dates) or _is_roll_day(payload, self.roll_dates):
                    self.coverage_status["roll_skip_count"] += 1
                elif _is_weekend_reopen(prev_observed, current_observed):
                    gap_bps = abs(current_open - prev_close) / prev_close * 10_000.0
                    if gap_bps >= self.min_gap_bps:
                        direction = "short" if current_open > prev_close else "long"
                        if self.max_gap_bps > 0 and gap_bps > self.max_gap_bps:
                            self.coverage_status["max_gap_skip_count"] += 1
                            self._previous_feature = payload
                            return
                        if not _trade_direction_allowed(direction, self.allow_direction):
                            self.coverage_status["direction_skip_count"] += 1
                            self._previous_feature = payload
                            return
                        self._active_gap = _ActiveGap(
                            direction=direction,
                            cme_target_price=float(prev_close),
                            cme_gap_open_price=float(current_open),
                            gap_bps=float(gap_bps),
                            detected_ts=int(payload.ts),
                            expires_at=int(payload.ts + self.max_hold_days * 86400 * 1000),
                        )
                        self.coverage_status["detected_gap_count"] += 1
        self._previous_feature = payload

    def _gap_signal(
        self,
        gap: _ActiveGap,
        price: float,
        action: str,
        reason: str,
    ) -> SignalPayload:
        if action == "entry":
            side = "sell" if gap.direction == "short" else "buy"
            gap.entry_side = side
        else:
            side = "buy" if gap.direction == "short" else "sell"
        return SignalPayload(
            strategy=self.name,
            inst_id=self.symbol,
            side=side,
            strength=max(0.0, float(self.size_multiplier)),
            fair_value=price,
            metadata={
                "action": action,
                "reason": reason,
                "dataset_id": self.dataset_id,
                "gap_direction": gap.direction,
                "gap_target_price": gap.okx_target_price,
                "okx_target_price": gap.okx_target_price,
                "okx_entry_anchor_price": gap.okx_entry_anchor_price,
                "cme_target_price": gap.cme_target_price,
                "cme_gap_open_price": gap.cme_gap_open_price,
                "gap_bps": gap.gap_bps,
                "stop_loss_bps_mult": self.stop_loss_bps_mult,
                "stop_loss_price": self._stop_loss_price(gap),
                "detected_ts": gap.detected_ts,
                "expires_at": gap.expires_at,
                "cancel_existing": True,
                "mode": "long_flat",
                "td_mode": self.td_mode,
                "research_only": True,
                "baseline": "daily_cme_delayed_not_realtime_gap_fill",
            },
        )

    async def on_fill(self, event: Event) -> None:
        fill = event.payload
        if fill.strategy != self.name or fill.inst_id != self.symbol or fill.fill_sz <= 0:
            return
        action = fill.metadata.get("action") if fill.metadata else None
        if action == "entry":
            self._in_position = True
        elif action == "exit":
            remaining = fill.metadata.get("remaining_sz") if fill.metadata else None
            try:
                remaining_sz = float(remaining)
            except (TypeError, ValueError):
                remaining_sz = 0.0 if fill.state == "filled" else float("inf")
            if fill.state == "filled" or remaining_sz <= 1e-12:
                self._in_position = False
                self._active_gap = None

    @staticmethod
    def _target_touched(direction: str, price: float, target: float) -> bool:
        if direction == "short":
            return price <= target
        return price >= target

    def _stop_loss_touched(self, gap: _ActiveGap, price: float) -> bool:
        stop_price = self._stop_loss_price(gap)
        if stop_price is None:
            return False
        if gap.direction == "short":
            return price >= stop_price
        return price <= stop_price

    def _stop_loss_price(self, gap: _ActiveGap) -> Optional[float]:
        if self.stop_loss_bps_mult <= 0 or gap.okx_entry_anchor_price is None:
            return None
        stop_pct = self.stop_loss_bps_mult * float(gap.gap_bps) / 10_000.0
        if gap.direction == "short":
            return gap.okx_entry_anchor_price * (1.0 + stop_pct)
        return gap.okx_entry_anchor_price * (1.0 - stop_pct)

    @staticmethod
    def _okx_target_from_anchor(direction: str, anchor_price: float, gap_bps: float) -> float:
        gap_pct = float(gap_bps) / 10_000.0
        if direction == "short":
            return anchor_price * (1.0 - gap_pct)
        return anchor_price * (1.0 + gap_pct)

    def _record_market_event(self) -> None:
        self.coverage_status["market_event_count"] += 1
        self._refresh_feature_gate()

    def _refresh_feature_gate(self) -> None:
        total = max(1, int(self.coverage_status["market_event_count"]))
        missing_ratio = float(self.coverage_status["missing_no_signal_count"]) / total
        stale_ratio = float(self.coverage_status["stale_no_signal_count"]) / total
        self.coverage_status["missing_no_signal_ratio"] = missing_ratio
        self.coverage_status["stale_no_signal_ratio"] = stale_ratio
        self.coverage_status["feature_gate_passed"] = (
            missing_ratio <= self.max_missing_signal_ratio
            and stale_ratio <= self.max_stale_signal_ratio
        )


def _field_float(fields: dict, key: str) -> Optional[float]:
    value = fields.get(key)
    if value in (None, "", "."):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _payload_datetime(payload: FeaturePayload) -> Optional[pd.Timestamp]:
    raw = payload.observed_at or payload.ts
    if not raw:
        return None
    return pd.Timestamp(int(raw), unit="ms", tz="UTC")


def _canonical_fng_label(value: object) -> str:
    text = str(value or "").strip()
    return _FNG_LABELS.get(text.casefold(), text)


def _optional_float(value: object) -> Optional[float]:
    if value in (None, "", "."):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _is_weekend_reopen(prev_observed: pd.Timestamp, current_observed: pd.Timestamp) -> bool:
    gap_days = (current_observed.date() - prev_observed.date()).days
    if prev_observed.weekday() != 4 or gap_days < 2:
        return False
    # Most CME daily sources label the Sunday evening Globex session as Monday;
    # a few source conventions may emit Sunday. Tuesday/Wednesday covers US
    # market holidays without silently dropping long weekends.
    return current_observed.weekday() in {6, 0, 1, 2}


def _is_roll_day(payload: FeaturePayload, configured_roll_dates: set[str]) -> bool:
    observed = _payload_datetime(payload)
    observed_date = observed.date().isoformat() if observed is not None else None
    raw = payload.fields or {}
    field_flag = raw.get("is_roll_day", raw.get("roll_day", raw.get("is_roll", False)))
    if isinstance(field_flag, str):
        field_flag = field_flag.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(field_flag) or (observed_date in configured_roll_dates if observed_date else False)


def _trade_direction_allowed(trade_direction: str, allow_direction: str) -> bool:
    """Return whether a gap trade passes the configured direction filter.

    The configured default is long_only for the research baseline; that default
    is regime-fitted and should be revisited if bear-regime validation fails.
    """
    if allow_direction == "long_only":
        return trade_direction == "long"
    if allow_direction == "short_only":
        return trade_direction == "short"
    return True
