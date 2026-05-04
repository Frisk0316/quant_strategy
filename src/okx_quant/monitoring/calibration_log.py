"""Shadow/demo execution calibration logger.

Captures mirror order submissions and WS fills to measure:
  - fill_rate  (filled / submitted)          → queue_fill_fraction
  - order_latency_ms  (fill_ts − submit_ts)  → order_latency_ms
  - cancel_latency_ms (cancel_ack − cancel_request) → cancel_latency_ms
  - slippage_bps  (|fill_px − order_px| / order_px × 10000)  → informational

One JSONL event file is written per engine session.
run_calibration_apply.py aggregates these files and back-fills
config/risk.yaml backtest section.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Optional

from loguru import logger


@dataclass
class CalibrationLogger:
    output_dir: Path | str

    _session_id: str = field(init=False)
    _jsonl_path: Path = field(init=False)
    _jsonl_file: Optional[IO[str]] = field(init=False, default=None)

    # Pending submits keyed by mirror cl_ord_id
    _submits: dict[str, dict] = field(init=False, default_factory=dict)
    # Cancel request timestamps keyed by mirror cl_ord_id
    _cancel_requests: dict[str, int] = field(init=False, default_factory=dict)

    # In-memory accumulators for fast session_summary()
    _fill_latencies: list[float] = field(init=False, default_factory=list)
    _slippages: list[float] = field(init=False, default_factory=list)
    _cancel_latencies: list[float] = field(init=False, default_factory=list)
    _n_submitted: int = field(init=False, default=0)
    _n_filled: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        out = Path(self.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        self._session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._jsonl_path = out / f"calib_{self._session_id}.jsonl"
        self._jsonl_file = open(self._jsonl_path, "a", encoding="utf-8")
        logger.info("CalibrationLogger started", path=str(self._jsonl_path))

    # ------------------------------------------------------------------
    # Event recorders
    # ------------------------------------------------------------------

    def record_submit(
        self,
        cl_ord_id: str,
        inst_id: str,
        side: str,
        order_px: float,
        order_sz: float,
        submit_ts: int,
    ) -> None:
        record = {
            "type": "submit",
            "cl_ord_id": cl_ord_id,
            "inst_id": inst_id,
            "side": side,
            "order_px": order_px,
            "order_sz": order_sz,
            "submit_ts": submit_ts,
        }
        self._submits[cl_ord_id] = record
        self._n_submitted += 1
        self._write(record)

    def record_fill(
        self,
        cl_ord_id: str,
        inst_id: str,
        fill_px: float,
        fill_sz: float,
        fill_ts: int,
        state: str,
    ) -> None:
        submit = self._submits.get(cl_ord_id)
        record: dict = {
            "type": "fill",
            "cl_ord_id": cl_ord_id,
            "inst_id": inst_id,
            "fill_px": fill_px,
            "fill_sz": fill_sz,
            "fill_ts": fill_ts,
            "state": state,
        }
        if submit:
            latency_ms = float(fill_ts - submit["submit_ts"])
            slippage_bps = (
                abs(fill_px - submit["order_px"]) / submit["order_px"] * 10_000
                if submit["order_px"] > 0
                else 0.0
            )
            record.update({
                "order_px": submit["order_px"],
                "latency_ms": latency_ms,
                "slippage_bps": slippage_bps,
            })
            if latency_ms >= 0:
                self._fill_latencies.append(latency_ms)
            self._slippages.append(slippage_bps)
        self._n_filled += 1
        self._write(record)

    def record_cancel_request(self, cl_ord_id: str, ts: int) -> None:
        self._cancel_requests[cl_ord_id] = ts
        self._write({"type": "cancel_request", "cl_ord_id": cl_ord_id, "ts": ts})

    def record_cancel_ack(self, cl_ord_id: str, ack_ts: int) -> None:
        req_ts = self._cancel_requests.pop(cl_ord_id, None)
        record: dict = {"type": "cancel_ack", "cl_ord_id": cl_ord_id, "ack_ts": ack_ts}
        if req_ts is not None:
            latency = float(ack_ts - req_ts)
            record["cancel_latency_ms"] = latency
            if latency >= 0:
                self._cancel_latencies.append(latency)
        self._write(record)

    # ------------------------------------------------------------------
    # Aggregation and flush
    # ------------------------------------------------------------------

    def session_summary(self) -> dict:
        fill_rate = self._n_filled / self._n_submitted if self._n_submitted > 0 else 0.0
        return {
            "session_id": self._session_id,
            "n_submitted": self._n_submitted,
            "n_filled": self._n_filled,
            "fill_rate": round(fill_rate, 4),
            "mean_order_latency_ms": round(_mean(self._fill_latencies), 1),
            "p95_order_latency_ms": round(_percentile(self._fill_latencies, 95), 1),
            "mean_cancel_latency_ms": round(_mean(self._cancel_latencies), 1),
            "p95_cancel_latency_ms": round(_percentile(self._cancel_latencies, 95), 1),
            "mean_slippage_bps": round(_mean(self._slippages), 2),
            "p95_slippage_bps": round(_percentile(self._slippages, 95), 2),
        }

    def flush_summary(self) -> dict:
        summary = self.session_summary()
        summary_path = self._jsonl_path.with_name(f"summary_{self._session_id}.json")
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        if self._jsonl_file is not None:
            self._jsonl_file.close()
            self._jsonl_file = None
        logger.info("Calibration summary written", path=str(summary_path), **summary)
        return summary

    def _write(self, record: dict) -> None:
        if self._jsonl_file is not None:
            self._jsonl_file.write(json.dumps(record) + "\n")
            self._jsonl_file.flush()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * pct / 100)
    return sorted_v[min(idx, len(sorted_v) - 1)]
