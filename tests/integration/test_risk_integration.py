from __future__ import annotations

import pytest

from okx_quant.core.events import OrderPayload
from okx_quant.risk.drawdown_tracker import DrawdownTracker
from okx_quant.risk.risk_guard import RiskGuard


def _order(sz: str = "1", px: str = "100", notional_usd: float = 0.0) -> OrderPayload:
    return OrderPayload(
        cl_ord_id="risk-test",
        inst_id="BTC-USDT-SWAP",
        side="buy",
        ord_type="post_only",
        sz=sz,
        px=px,
        td_mode="cross",
        strategy="risk_test",
        notional_usd=notional_usd,
    )


def _guard(equity: float, tracker: DrawdownTracker, **kwargs) -> RiskGuard:
    return RiskGuard(equity_fn=lambda: equity, drawdown_tracker=tracker, **kwargs)


def test_daily_pnl_does_not_reset_without_explicit_call():
    tracker = DrawdownTracker()
    tracker.set_initial_equity(10_000.0)
    tracker._day_start_ts -= 25 * 3600
    tracker.update(9_900.0)

    assert tracker.daily_pnl() == pytest.approx(-100.0)

    tracker.reset_daily()

    assert tracker.daily_pnl() == pytest.approx(0.0)


def test_soft_stop_then_daily_reset_then_re_trigger():
    tracker = DrawdownTracker(soft_drawdown_pct=0.10, hard_drawdown_pct=0.15, max_daily_loss_pct=1.0)
    tracker.set_initial_equity(10_000.0)
    guard = _guard(8_900.0, tracker, max_daily_loss_pct=1.0)
    guard.register_strategy("risk_test")

    tracker.update(8_900.0)
    assert guard.check(_order()) is True
    assert guard.get_size_multiplier("risk_test") == pytest.approx(0.5)

    guard.reset_daily()
    assert guard.get_size_multiplier("risk_test") == pytest.approx(1.0)

    guard.check(_order())
    assert guard.get_size_multiplier("risk_test") == pytest.approx(0.5)


def test_position_limit_at_exact_boundary(prod_risk_cfg):
    equity = 10_000.0
    tracker = DrawdownTracker()
    tracker.set_initial_equity(equity)
    guard = _guard(
        equity,
        tracker,
        max_order_notional_usd=prod_risk_cfg.max_order_notional_usd,
        max_pos_pct_equity=prod_risk_cfg.max_pos_pct_equity,
    )

    assert guard.check(_order(sz="1", px="1"), current_pos_notional=2_999.0) is True
    assert guard.check(_order(sz="1", px="1"), current_pos_notional=3_000.0) is False


def test_stale_quote_exact_2pct_boundary(prod_risk_cfg):
    tracker = DrawdownTracker()
    tracker.set_initial_equity(10_000.0)
    guard = _guard(
        10_000.0,
        tracker,
        stale_quote_pct=prod_risk_cfg.stale_quote_pct,
    )

    assert guard.check(_order(sz="1", px="102.0"), current_mid=100.0) is True
    assert guard.check(_order(sz="1", px="102.01"), current_mid=100.0) is False


def test_fat_finger_exactly_500_usd(prod_risk_cfg):
    tracker = DrawdownTracker()
    tracker.set_initial_equity(10_000.0)
    guard = _guard(
        10_000.0,
        tracker,
        max_order_notional_usd=prod_risk_cfg.max_order_notional_usd,
    )

    assert guard.check(_order(notional_usd=500.0)) is True
    assert guard.check(_order(notional_usd=500.01)) is False


def test_daily_loss_kills_independently_of_drawdown(prod_risk_cfg):
    tracker = DrawdownTracker(
        soft_drawdown_pct=prod_risk_cfg.soft_drawdown_pct,
        hard_drawdown_pct=prod_risk_cfg.hard_drawdown_pct,
        max_daily_loss_pct=prod_risk_cfg.max_daily_loss_pct,
    )
    tracker.set_initial_equity(10_000.0)
    tracker.update(9_400.0)
    guard = _guard(9_400.0, tracker, max_daily_loss_pct=prod_risk_cfg.max_daily_loss_pct)

    assert tracker.current_drawdown() > -prod_risk_cfg.soft_drawdown_pct
    assert guard.check(_order()) is False
    assert guard.kill is True
