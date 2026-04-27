"""Unit tests for RiskGuard — all order blocking scenarios."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

from okx_quant.core.events import OrderPayload
from okx_quant.risk.drawdown_tracker import DrawdownTracker, RiskLevel
from okx_quant.risk.risk_guard import RiskGuard


def make_risk_guard(equity=10_000.0, **kwargs):
    dd = DrawdownTracker(
        soft_drawdown_pct=kwargs.pop("soft_drawdown_pct", 0.10),
        hard_drawdown_pct=kwargs.pop("hard_drawdown_pct", 0.15),
        max_daily_loss_pct=kwargs.pop("max_daily_loss_pct", 0.05),
    )
    dd.set_initial_equity(equity)
    return RiskGuard(
        equity_fn=lambda: equity,
        drawdown_tracker=dd,
        **kwargs,
    )


def make_order(inst_id="BTC-USDT-SWAP", sz="1", px="100.0", side="buy", strategy="test"):
    return OrderPayload(
        cl_ord_id="test-id",
        inst_id=inst_id,
        side=side,
        ord_type="post_only",
        sz=sz,
        px=px,
        td_mode="cross",
        strategy=strategy,
    )


def test_normal_order_passes():
    rg = make_risk_guard(equity=10_000.0)
    order = make_order(sz="1", px="100.0")  # Notional = 100
    assert rg.check(order) is True


def test_fat_finger_blocked():
    rg = make_risk_guard(equity=10_000.0, max_order_notional_usd=500.0)
    order = make_order(sz="10", px="100.0")  # Notional = 1000 > 500
    assert rg.check(order) is False


def test_kill_switch_blocks_all():
    rg = make_risk_guard()
    rg.kill = True
    assert rg.check(make_order()) is False


def test_stale_quote_blocked():
    rg = make_risk_guard(equity=10_000.0, stale_quote_pct=0.02)
    order = make_order(sz="1", px="105.0")  # 5% drift from mid=100
    assert rg.check(order, current_mid=100.0) is False


def test_stale_quote_passes_within_threshold():
    rg = make_risk_guard(equity=10_000.0, stale_quote_pct=0.02)
    order = make_order(sz="1", px="101.0")  # 1% drift — within 2%
    assert rg.check(order, current_mid=100.0) is True


def test_soft_stop_triggered_on_drawdown():
    dd = DrawdownTracker(soft_drawdown_pct=0.10, hard_drawdown_pct=0.15)
    dd.set_initial_equity(10_000.0)
    dd.update(8_900.0)  # 11% drawdown → soft stop
    rg = RiskGuard(equity_fn=lambda: 8_900.0, drawdown_tracker=dd)
    order = make_order(sz="1", px="100.0")
    # Should pass but trigger soft stop
    result = rg.check(order)
    assert rg.soft_stop is True


def test_hard_stop_triggered_on_severe_drawdown():
    dd = DrawdownTracker(soft_drawdown_pct=0.10, hard_drawdown_pct=0.15)
    dd.set_initial_equity(10_000.0)
    dd.update(8_400.0)  # 16% drawdown → hard stop
    rg = RiskGuard(equity_fn=lambda: 8_400.0, drawdown_tracker=dd)
    order = make_order(sz="1", px="100.0")
    assert rg.check(order) is False
    assert rg.kill is True


def test_size_multiplier_default_one():
    rg = make_risk_guard()
    rg.register_strategy("test_strat")
    assert rg.get_size_multiplier("test_strat") == 1.0


def test_size_multiplier_after_soft_stop():
    rg = make_risk_guard()
    rg.register_strategy("test_strat")
    rg.trigger_soft_stop()
    assert rg.get_size_multiplier("test_strat") == 0.5


def test_size_multiplier_after_kill():
    rg = make_risk_guard()
    rg.register_strategy("test_strat")
    rg.kill = True
    assert rg.get_size_multiplier("test_strat") == 0.0


def test_reset_clears_kill():
    rg = make_risk_guard()
    rg.trigger_hard_stop()
    assert rg.kill is True
    rg.reset()
    assert rg.kill is False
