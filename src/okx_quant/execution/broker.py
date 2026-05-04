"""
Broker abstraction — same strategy code works for backtesting and live.
Extracted from §5.4 of Crypto_Quant_Plan_v1.md.

OKXBroker: real exchange via python-okx TradeAPI
SimBroker: immediate simulated fill at mid-price with configurable slippage
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from loguru import logger

from okx_quant.core.events import FillPayload, MarketPayload
from okx_quant.execution.replay_execution import ReplayExecutionModel
from okx_quant.portfolio.sizing import validate_ct_val


_SHADOW_MIRROR_PREFIX = "m_"


def to_shadow_mirror_cl_ord_id(cl_ord_id: str) -> str:
    """Derive a stable mirror order ID that stays within OKX's 32-char limit."""
    return f"{_SHADOW_MIRROR_PREFIX}{cl_ord_id[:30]}"


def is_shadow_mirror_cl_ord_id(cl_ord_id: str) -> bool:
    return cl_ord_id.startswith(_SHADOW_MIRROR_PREFIX)


class Broker(ABC):
    @abstractmethod
    async def submit(self, order: dict) -> Optional[FillPayload]:
        """Submit an order. Returns FillPayload on fill, None on rejection."""
        ...

    @abstractmethod
    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        """Cancel an order by client order ID. Returns True if cancelled."""
        ...

    @abstractmethod
    async def close_all(self) -> None:
        """Emergency close all positions."""
        ...


class OKXBroker(Broker):
    """
    Live/demo broker using python-okx TradeAPI.
    flag="1" for demo, flag="0" for live.
    """

    def __init__(
        self,
        api_key: str,
        secret: str,
        passphrase: str,
        demo: bool = True,
        strategy_name: str = "",
    ) -> None:
        try:
            from okx import Trade, Account
        except ImportError:
            raise ImportError("python-okx required: pip install python-okx")

        flag = "1" if demo else "0"
        self._trade = Trade.TradeAPI(api_key, secret, passphrase, use_server_time=False, flag=flag)
        self._account = Account.AccountAPI(api_key, secret, passphrase, use_server_time=False, flag=flag)
        self._strategy = strategy_name
        self._demo = demo

    async def submit(self, order: dict) -> Optional[FillPayload]:
        """
        Submit a post_only order via OKX REST.
        post_only rejection (code 51026) is logged but NOT retried as market order.
        """
        import asyncio
        try:
            result = await asyncio.to_thread(
                self._trade.place_order,
                instId=order["inst_id"],
                tdMode=order.get("td_mode", "cross"),
                side=order["side"],
                ordType=order.get("ord_type", "post_only"),
                sz=str(order["sz"]),
                px=str(order["px"]),
                clOrdId=order.get("cl_ord_id", "")[:32],
                tag=order.get("strategy", "")[:16],
            )
            if result.get("code") == "51026":
                # post_only rejection — price crossed the book
                logger.debug(
                    "post_only rejected (market moved)",
                    inst_id=order["inst_id"],
                    side=order["side"],
                    px=order["px"],
                )
                return None
            if result.get("code") != "0":
                logger.warning("Order rejected", code=result.get("code"), msg=result.get("msg"), order=order)
                return None

            data = result.get("data", [{}])[0]
            return FillPayload(
                cl_ord_id=order.get("cl_ord_id", ""),
                ord_id=data.get("ordId", ""),
                inst_id=order["inst_id"],
                fill_px=0.0,   # Actual fill comes via WS order update
                fill_sz=0.0,
                fee=0.0,
                fee_ccy="USDT",
                side=order["side"],
                ts=int(time.time() * 1000),
                strategy=order.get("strategy", self._strategy),
                state="pending",
                metadata=order.get("metadata", {}),
            )
        except Exception as e:
            logger.error("OKXBroker submit error", exc=str(e), order=order)
            return None

    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        import asyncio
        try:
            result = await asyncio.to_thread(
                self._trade.cancel_order,
                instId=inst_id,
                clOrdId=cl_ord_id,
            )
            return result.get("code") == "0"
        except Exception as e:
            logger.error("OKXBroker cancel error", exc=str(e))
            return False

    async def close_all(self) -> None:
        """Close all open positions via /close-position."""
        import asyncio
        try:
            positions = await asyncio.to_thread(
                self._account.get_positions,
                instType="SWAP",
            )
            for pos in positions.get("data", []):
                inst_id = pos.get("instId", "")
                if inst_id and float(pos.get("pos", 0)) != 0:
                    await asyncio.to_thread(
                        self._trade.close_positions,
                        instId=inst_id,
                        mgnMode="cross",
                    )
                    logger.info("Closed position", inst_id=inst_id)
        except Exception as e:
            logger.error("close_all error", exc=str(e))


class SimBroker(Broker):
    """
    Simulated broker for backtesting and shadow mode.
    Fills immediately at mid-price with configurable slippage.
    """

    def __init__(
        self,
        slippage_bps: float = 2.0,
        fill_probability: float = 0.95,
        strategy_name: str = "sim",
        instrument_specs: dict | None = None,
        maker_fee_rate: float = 0.0002,
        execution_model: ReplayExecutionModel | None = None,
    ) -> None:
        self._slippage = slippage_bps / 10_000
        self._fill_prob = fill_probability
        self._strategy = strategy_name
        self._specs = instrument_specs or {}
        self._maker_fee_rate = maker_fee_rate
        self._execution_model = execution_model
        self._positions: dict[str, float] = {}

    async def submit(self, order: dict) -> Optional[FillPayload]:
        """Simulate a fill with slippage."""
        if self._execution_model is not None:
            return self._execution_model.submit(order)

        if random.random() > self._fill_prob:
            logger.debug("SimBroker: order not filled (probability)", order=order)
            return None

        price = float(order["px"])
        slippage = price * self._slippage
        if order["side"] == "buy":
            fill_px = price + slippage
        else:
            fill_px = price - slippage

        fill_sz = float(order["sz"])
        ct_val = validate_ct_val(float(self._specs.get(order["inst_id"], {}).get("ctVal", 1.0)), order["inst_id"])
        notional_usd = fill_px * fill_sz * ct_val
        fee = notional_usd * self._maker_fee_rate

        inst_id = order["inst_id"]
        signed_size = fill_sz if order["side"] == "buy" else -fill_sz
        self._positions[inst_id] = self._positions.get(inst_id, 0) + signed_size

        metadata = dict(order.get("metadata", {}))
        metadata.setdefault("notional_usd", notional_usd)
        metadata.setdefault("fee_rate", self._maker_fee_rate)
        metadata.setdefault("ct_val", ct_val)

        return FillPayload(
            cl_ord_id=order.get("cl_ord_id", str(uuid.uuid4())),
            ord_id=str(uuid.uuid4()),
            inst_id=inst_id,
            fill_px=fill_px,
            fill_sz=fill_sz,
            fee=fee,
            fee_ccy="USDT",
            side=order["side"],
            ts=int(time.time() * 1000),
            strategy=order.get("strategy", self._strategy),
            state="filled",
            metadata=metadata,
        )

    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        if self._execution_model is not None:
            return self._execution_model.cancel(inst_id, cl_ord_id)
        return True

    async def close_all(self) -> None:
        if self._execution_model is not None:
            self._execution_model.close_all()
        self._positions.clear()
        logger.info("SimBroker: all positions cleared")

    def on_market(self, payload: MarketPayload) -> list[FillPayload]:
        if self._execution_model is None:
            return []
        return self._execution_model.on_market(payload)


class ShadowBroker(Broker):
    """
    Shadow execution broker.

    Primary fills come from the simulated broker and drive local accounting.
    Mirror orders are also sent to OKX demo using a derived client order ID so
    demo fills can be observed without contaminating local PnL.
    """

    def __init__(self, primary: Broker, mirror: Broker, calibration_log=None) -> None:
        self._primary = primary
        self._mirror = mirror
        self._mirror_tasks: set[asyncio.Task] = set()
        self._calibration_log = calibration_log

    async def submit(self, order: dict) -> Optional[FillPayload]:
        primary_fill = await self._primary.submit(order)

        mirror_order = dict(order)
        mirror_cl_ord_id: Optional[str] = None
        if mirror_order.get("cl_ord_id"):
            mirror_cl_ord_id = to_shadow_mirror_cl_ord_id(mirror_order["cl_ord_id"])
            mirror_order["cl_ord_id"] = mirror_cl_ord_id

        if self._calibration_log is not None and mirror_cl_ord_id:
            self._calibration_log.record_submit(
                cl_ord_id=mirror_cl_ord_id,
                inst_id=order.get("inst_id", ""),
                side=order.get("side", ""),
                order_px=float(order.get("px", 0)),
                order_sz=float(order.get("sz", 0)),
                submit_ts=int(time.time() * 1000),
            )

        task = asyncio.create_task(self._submit_mirror(mirror_order))
        self._mirror_tasks.add(task)
        task.add_done_callback(self._mirror_tasks.discard)

        return primary_fill

    async def _submit_mirror(self, order: dict) -> None:
        try:
            await self._mirror.submit(order)
        except Exception as exc:
            logger.warning("Shadow mirror submit failed", exc=str(exc), order=order)

    async def cancel(self, inst_id: str, cl_ord_id: str) -> bool:
        primary_result = await self._primary.cancel(inst_id, cl_ord_id)
        mirror_cl_ord_id = to_shadow_mirror_cl_ord_id(cl_ord_id)
        if self._calibration_log is not None:
            self._calibration_log.record_cancel_request(
                cl_ord_id=mirror_cl_ord_id,
                ts=int(time.time() * 1000),
            )
        try:
            await self._mirror.cancel(inst_id, mirror_cl_ord_id)
        except Exception as exc:
            logger.warning("Shadow mirror cancel failed", exc=str(exc), cl_ord_id=cl_ord_id)
        return primary_result

    async def close_all(self) -> None:
        results = await asyncio.gather(
            self._primary.close_all(),
            self._mirror.close_all(),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Shadow close_all error", exc=str(result))
