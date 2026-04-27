"""
Event dataclasses — the contract between all system components.
No component imports another directly; they communicate only via events.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EvtType(Enum):
    MARKET = 1   # L2 book update, trade tick, funding rate
    SIGNAL = 2   # Strategy signal: direction + target quotes
    ORDER = 3    # Sized order ready for submission
    FILL = 4     # Execution confirmation
    RISK = 5     # Risk event: halt, soft-stop, circuit-break
    FUNDING = 6  # Funding rate update (dedicated channel)


@dataclass
class Event:
    type: EvtType
    ts: float = field(default_factory=time.time)
    payload: Any = None


# ---------------------------------------------------------------------------
# Typed payloads
# ---------------------------------------------------------------------------

@dataclass
class MarketPayload:
    inst_id: str
    ts: int             # epoch ms from OKX server
    bids: list          # [[px_str, sz_str, ...], ...]
    asks: list          # [[px_str, sz_str, ...], ...]
    seq_id: int
    channel: str        # 'books' | 'trades' | 'funding-rate' | 'tickers'
    checksum: Optional[int] = None
    action: Optional[str] = None  # 'snapshot' | 'update'
    # For trade channel
    trade_id: Optional[str] = None
    trade_price: Optional[float] = None
    trade_size: Optional[float] = None
    trade_side: Optional[str] = None  # 'buy' | 'sell'
    # For funding channel
    funding_rate: Optional[float] = None
    next_funding_time: Optional[int] = None


@dataclass
class SignalPayload:
    strategy: str          # Strategy name for audit
    inst_id: str
    side: str              # 'buy' | 'sell' | 'neutral'
    strength: float        # [0, 1]
    fair_value: float      # Estimated fair price
    # For market-making strategies
    target_bid: Optional[float] = None
    target_ask: Optional[float] = None
    # Metadata for monitoring and audit trail
    metadata: dict = field(default_factory=dict)


@dataclass
class OrderPayload:
    cl_ord_id: str         # UUID idempotency key (max 32 chars)
    inst_id: str
    side: str              # 'buy' | 'sell'
    ord_type: str          # ALWAYS 'post_only' for maker strategies
    sz: str                # String per OKX API requirement
    px: str                # Limit price as string
    td_mode: str           # 'cross' | 'isolated'
    strategy: str          # Originating strategy name
    reduce_only: bool = False
    pos_side: str = "net"  # 'net' | 'long' | 'short'
    notional_usd: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class FillPayload:
    cl_ord_id: str
    ord_id: str
    inst_id: str
    fill_px: float
    fill_sz: float
    fee: float
    fee_ccy: str
    side: str
    ts: int            # epoch ms
    strategy: str
    state: str = "filled"  # 'filled' | 'partially_filled'
    metadata: dict = field(default_factory=dict)


@dataclass
class RiskPayload:
    level: str         # 'soft_stop' | 'hard_stop' | 'circuit_break' | 'daily_loss'
    reason: str
    triggered_at: float = field(default_factory=time.time)
