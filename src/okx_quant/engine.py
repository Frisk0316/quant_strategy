"""
Main asyncio event loop orchestrator.
Wires all components together and manages the full lifecycle.

Deployment stages (from §6 iron law #9):
  Demo 4 weeks → Shadow 2 weeks → Half-size live → Full-size live

Usage:
    import asyncio
    from okx_quant.engine import main
    from okx_quant.core.config import load_config
    asyncio.run(main(load_config()))
"""
from __future__ import annotations

import asyncio
import signal
import sys
from typing import Optional

from loguru import logger

from okx_quant.core.bus import EventBus
from okx_quant.core.config import AppConfig
from okx_quant.core.events import Event, EvtType, RiskPayload
from okx_quant.core.logging import setup_logging
from okx_quant.data.feed_store import FeedStore
from okx_quant.data.market_data_handler import MarketDataHandler
from okx_quant.data.rest_client import OKXRestClient
from okx_quant.execution.broker import OKXBroker, ShadowBroker, SimBroker
from okx_quant.execution.execution_handler import ExecutionHandler
from okx_quant.execution.order_manager import OrderManager
from okx_quant.execution.rate_limiter import RateLimiter
from okx_quant.monitoring.telegram_alert import TelegramMonitor
from okx_quant.portfolio.portfolio_manager import PortfolioManager
from okx_quant.portfolio.positions import PositionLedger
from okx_quant.risk.circuit_breaker import CircuitBreaker
from okx_quant.risk.drawdown_tracker import DrawdownTracker
from okx_quant.risk.risk_guard import RiskGuard
from okx_quant.strategies.as_market_maker import ASMarketMaker
from okx_quant.strategies.base import Strategy
from okx_quant.strategies.funding_carry import FundingCarryStrategy
from okx_quant.strategies.obi_market_maker import OBIMarketMaker
from okx_quant.strategies.pairs_trading import PairsTradingStrategy


def _should_use_demo_environment(cfg: AppConfig) -> bool:
    return cfg.is_demo() or cfg.system.mode == "shadow"


def _build_broker(cfg: AppConfig, sim_broker: bool = False):
    if cfg.system.mode == "shadow":
        return ShadowBroker(
            primary=SimBroker(slippage_bps=2.0),
            mirror=OKXBroker(
                api_key=cfg.secrets.okx_api_key,
                secret=cfg.secrets.okx_secret,
                passphrase=cfg.secrets.okx_passphrase,
                demo=True,
            ),
        )

    if sim_broker:
        return SimBroker(slippage_bps=2.0)

    return OKXBroker(
        api_key=cfg.secrets.okx_api_key,
        secret=cfg.secrets.okx_secret,
        passphrase=cfg.secrets.okx_passphrase,
        demo=cfg.is_demo(),
    )


async def main(cfg: AppConfig, sim_broker: bool = False) -> None:
    setup_logging(cfg.system.log_level, cfg.system.json_logs)
    logger.info("Starting OKX Quant Engine", mode=cfg.system.mode)
    use_demo_environment = _should_use_demo_environment(cfg)

    # ------------------------------------------------------------------
    # REST client + clock sync
    # ------------------------------------------------------------------
    rest = OKXRestClient(
        api_key=cfg.secrets.okx_api_key,
        secret=cfg.secrets.okx_secret,
        passphrase=cfg.secrets.okx_passphrase,
        base_url=cfg.okx.base_url,
        demo=use_demo_environment,
    )
    rest.sync_clock()
    logger.info("Clock synced")

    # ------------------------------------------------------------------
    # Fetch instrument specs for sizing
    # ------------------------------------------------------------------
    instrument_specs = {}
    market_symbols = list(dict.fromkeys(cfg.system.symbols + cfg.system.spot_symbols))
    try:
        for inst_type, symbols in (("SWAP", cfg.system.symbols), ("SPOT", cfg.system.spot_symbols)):
            instr_resp = rest.get_instruments(inst_type)
            symbol_set = set(symbols)
            for instr in instr_resp.get("data", []):
                inst_id = instr.get("instId", "")
                if inst_id in symbol_set:
                    instrument_specs[inst_id] = {
                        "ctVal": float(instr.get("ctVal", 0.01 if inst_type == "SWAP" else 1.0)),
                        "minSz": float(instr.get("minSz", 1 if inst_type == "SWAP" else 0.0001)),
                        "lotSz": float(instr.get("lotSz", 1 if inst_type == "SWAP" else 0.0001)),
                        "tickSz": float(instr.get("tickSz", 0.1)),
                        "tdMode": "cross",
                    }
        logger.info("Instrument specs loaded", count=len(instrument_specs))
    except Exception as e:
        logger.warning("Could not fetch instrument specs, using defaults", exc=str(e))
        for s in cfg.system.symbols:
            instrument_specs[s] = {"ctVal": 0.01, "minSz": 1, "lotSz": 1, "tickSz": 0.1, "tdMode": "cross"}
        for s in cfg.system.spot_symbols:
            instrument_specs[s] = {"ctVal": 1.0, "minSz": 0.0001, "lotSz": 0.0001, "tickSz": 0.1, "tdMode": "cross"}

    # ------------------------------------------------------------------
    # Initial equity from account balance
    # ------------------------------------------------------------------
    initial_equity = cfg.system.equity_usd
    try:
        bal_resp = rest.get_balance()
        for item in bal_resp.get("data", [{}])[0].get("details", []):
            if item.get("ccy") == "USDT":
                initial_equity = float(item.get("eq", initial_equity))
                break
        logger.info("Initial equity", equity=initial_equity)
    except Exception as e:
        logger.warning("Could not fetch balance, using config equity", exc=str(e))

    # ------------------------------------------------------------------
    # Core components
    # ------------------------------------------------------------------
    bus = EventBus()
    positions = PositionLedger(initial_equity=initial_equity, redis_url=cfg.storage.redis_url)
    dd_tracker = DrawdownTracker(
        soft_drawdown_pct=cfg.risk.soft_drawdown_pct,
        hard_drawdown_pct=cfg.risk.hard_drawdown_pct,
        max_daily_loss_pct=cfg.risk.max_daily_loss_pct,
    )
    dd_tracker.set_initial_equity(initial_equity)

    # ------------------------------------------------------------------
    # Monitoring & Telegram
    # ------------------------------------------------------------------
    telegram: Optional[TelegramMonitor] = None
    if cfg.secrets.telegram_token and cfg.secrets.telegram_chat_id:
        telegram = TelegramMonitor(
            token=cfg.secrets.telegram_token,
            chat_id=cfg.secrets.telegram_chat_id,
        )

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------
    async def on_circuit_trip(reason: str) -> None:
        logger.error("Circuit breaker tripped, halting all strategies", reason=reason)
        risk_guard.trigger_hard_stop(reason)
        if telegram:
            await telegram.send_alert(f"CIRCUIT BREAKER: {reason}", level="critical")

    circuit_breaker = CircuitBreaker(
        ws_reconnect_threshold=cfg.risk.ws_reconnect_circuit_threshold,
        ws_window_secs=cfg.risk.ws_reconnect_window_secs,
        rest_error_threshold=cfg.risk.rest_error_rate_circuit_threshold,
        rest_window=cfg.risk.rest_error_rate_window,
        on_trip_callback=lambda r: asyncio.create_task(on_circuit_trip(r)),
    )

    risk_guard = RiskGuard(
        equity_fn=positions.get_equity,
        drawdown_tracker=dd_tracker,
        max_order_notional_usd=cfg.risk.max_order_notional_usd,
        max_pos_pct_equity=cfg.risk.max_pos_pct_equity,
        max_leverage=cfg.risk.max_leverage,
        max_daily_loss_pct=cfg.risk.max_daily_loss_pct,
        soft_drawdown_pct=cfg.risk.soft_drawdown_pct,
        hard_drawdown_pct=cfg.risk.hard_drawdown_pct,
        stale_quote_pct=cfg.risk.stale_quote_pct,
    )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    rate_limiter = RateLimiter()

    broker = _build_broker(cfg, sim_broker=sim_broker)

    order_manager = OrderManager(broker=broker, rate_limiter=rate_limiter)
    exec_handler = ExecutionHandler(bus=bus, order_manager=order_manager,
                                    stale_quote_pct=cfg.risk.stale_quote_pct)

    portfolio_mgr = PortfolioManager(
        bus=bus,
        positions=positions,
        risk_guard=risk_guard,
        target_ann_vol=0.20,
        instrument_specs=instrument_specs,
    )

    # ------------------------------------------------------------------
    # Strategies
    # ------------------------------------------------------------------
    strategies: list[Strategy] = []
    strat_cfg = cfg.strategies

    if strat_cfg.obi_market_maker.enabled:
        strat = OBIMarketMaker(strat_cfg.obi_market_maker.model_dump())
        strategies.append(strat)
        risk_guard.register_strategy(strat.name)
        logger.info("Strategy enabled", name=strat.name)

    if strat_cfg.as_market_maker.enabled:
        strat = ASMarketMaker(strat_cfg.as_market_maker.model_dump())
        strategies.append(strat)
        risk_guard.register_strategy(strat.name)
        logger.info("Strategy enabled", name=strat.name)

    if strat_cfg.funding_carry.enabled:
        strat = FundingCarryStrategy(strat_cfg.funding_carry.model_dump())
        strategies.append(strat)
        risk_guard.register_strategy(strat.name)
        logger.info("Strategy enabled", name=strat.name)

    if strat_cfg.pairs_trading.enabled:
        strat = PairsTradingStrategy(strat_cfg.pairs_trading.model_dump())
        strategies.append(strat)
        risk_guard.register_strategy(strat.name)
        logger.info("Strategy enabled", name=strat.name)

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------
    mdh = MarketDataHandler(
        bus=bus,
        symbols=market_symbols,
        api_key=cfg.secrets.okx_api_key,
        secret=cfg.secrets.okx_secret,
        passphrase=cfg.secrets.okx_passphrase,
        ws_public_url=cfg.okx.ws_public,
        ws_private_url=cfg.okx.ws_private,
        demo=use_demo_environment,
        reconnect_limit=cfg.risk.ws_reconnect_circuit_threshold,
        reconnect_window_secs=cfg.risk.ws_reconnect_window_secs,
    )

    feed_store = FeedStore(
        backend=cfg.storage.backend,
        parquet_dir=cfg.storage.parquet_dir,
        timescale_dsn=cfg.storage.timescale_dsn,
    )

    # ------------------------------------------------------------------
    # Event bus routing
    # ------------------------------------------------------------------
    async def on_market_event(event: Event) -> None:
        payload = event.payload
        inst_id = getattr(payload, "inst_id", "")
        channel = getattr(payload, "channel", "books")

        # Update exec handler mid prices
        await exec_handler.on_market(event)
        portfolio_mgr.on_market(payload)

        # Persist tick data
        if channel == "books" and payload.bids and payload.asks:
            await feed_store.write_book_snapshot(inst_id, payload.ts, payload.bids, payload.asks)
        elif channel == "trades" and payload.trade_id:
            await feed_store.write_trade(
                inst_id, payload.ts, payload.trade_id,
                payload.trade_price, payload.trade_size, payload.trade_side,
            )

        # Fan out to all strategies
        book = mdh.books.get(inst_id)
        for strat in strategies:
            if strat.is_active:
                signal = await strat.on_market(event, book)
                if signal:
                    await bus.put(Event(EvtType.SIGNAL, payload=signal))

    async def on_funding_event(event: Event) -> None:
        payload = event.payload
        await feed_store.write_funding(
            payload.inst_id, payload.ts, payload.funding_rate, payload.next_funding_time or 0
        )
        for strat in strategies:
            if strat.is_active:
                signal = await strat.on_market(event)
                if signal:
                    await bus.put(Event(EvtType.SIGNAL, payload=signal))

    async def on_signal_event(event: Event) -> None:
        await portfolio_mgr.on_signal(event)

    async def on_order_event(event: Event) -> None:
        await exec_handler.on_order(event)

    async def on_fill_event(event: Event) -> None:
        payload = event.payload
        # Handle both structured FillPayload and raw WS dict
        if isinstance(payload, dict):
            await exec_handler.on_fill_ws(payload)
            return
        await portfolio_mgr.on_fill(event)
        dd_tracker.update(positions.get_equity())
        for strat in strategies:
            if strat.name == payload.strategy:
                await strat.on_fill(event)

    bus.subscribe(EvtType.MARKET, on_market_event)
    bus.subscribe(EvtType.FUNDING, on_funding_event)
    bus.subscribe(EvtType.SIGNAL, on_signal_event)
    bus.subscribe(EvtType.ORDER, on_order_event)
    bus.subscribe(EvtType.FILL, on_fill_event)

    # ------------------------------------------------------------------
    # Graceful shutdown
    # ------------------------------------------------------------------
    stop_event = asyncio.Event()

    def _shutdown(sig_name: str) -> None:
        logger.warning(f"Signal received: {sig_name}, shutting down...")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig.name: _shutdown(s))

    # ------------------------------------------------------------------
    # Start background tasks
    # ------------------------------------------------------------------
    tasks = [
        asyncio.create_task(bus.dispatch_loop(), name="bus"),
        asyncio.create_task(mdh.run_public(), name="ws_public"),
        asyncio.create_task(mdh.run_private(), name="ws_private"),
        asyncio.create_task(feed_store.flush_loop(), name="feed_store"),
        asyncio.create_task(_clock_sync_loop(rest, cfg.clock.sync_interval_secs), name="clock_sync"),
        asyncio.create_task(_daily_reset_loop(risk_guard), name="daily_reset"),
    ]

    if telegram:
        tasks.append(asyncio.create_task(
            telegram.command_loop(risk_guard, positions), name="telegram"
        ))

    logger.info("Engine running", strategy_count=len(strategies), symbols=cfg.system.symbols)
    if telegram:
        await telegram.send_alert(
            f"Engine started: {cfg.system.mode} mode, {len(strategies)} strategies",
            level="info"
        )

    # Wait for shutdown signal
    await stop_event.wait()

    # Cleanup
    logger.warning("Shutting down engine...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    if telegram:
        await telegram.send_alert("Engine stopped", level="warning")

    rest.close()
    logger.info("Engine shutdown complete")


# ------------------------------------------------------------------
# Background helpers
# ------------------------------------------------------------------

async def _clock_sync_loop(rest: OKXRestClient, interval_secs: int) -> None:
    while True:
        await asyncio.sleep(interval_secs)
        try:
            rest.sync_clock()
        except Exception as e:
            logger.warning("Clock sync failed", exc=str(e))


async def _daily_reset_loop(risk_guard: RiskGuard) -> None:
    """Reset daily PnL counter at UTC midnight."""
    import datetime
    while True:
        now = datetime.datetime.utcnow()
        next_midnight = (now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=5, microsecond=0
        )
        wait_secs = (next_midnight - now).total_seconds()
        await asyncio.sleep(wait_secs)
        risk_guard.reset_daily()
