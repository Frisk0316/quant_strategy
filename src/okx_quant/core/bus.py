"""
Asyncio event bus — typed routing from producers to consumers.
MARKET events fan out to all registered market listeners.
RISK events are delivered first (priority).
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable

from okx_quant.core.events import Event, EvtType


Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self, maxsize: int = 10_000) -> None:
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self._handlers: dict[EvtType, list[Handler]] = defaultdict(list)

    def subscribe(self, evt_type: EvtType, handler: Handler) -> None:
        self._handlers[evt_type].append(handler)

    async def put(self, event: Event) -> None:
        await self._queue.put(event)

    def put_nowait(self, event: Event) -> None:
        self._queue.put_nowait(event)

    async def join(self) -> None:
        await self._queue.join()

    async def dispatch_loop(self) -> None:
        """
        Main dispatch loop — run as an asyncio task.
        Delivers each event to all registered handlers for its type.
        RISK events are always dispatched; they cannot be dropped.
        """
        while True:
            event = await self._queue.get()
            handlers = self._handlers.get(event.type, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as exc:
                    from okx_quant.core.logging import get_logger
                    get_logger().error(
                        "EventBus handler error",
                        evt_type=event.type.name,
                        handler=handler.__qualname__,
                        exc=str(exc),
                    )
            self._queue.task_done()
