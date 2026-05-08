"""Unit tests for circuit breaker logic."""

import pytest

from risk_monitor.circuit_breaker import CircuitBreaker
from risk_monitor.config import Settings
from risk_monitor.state import AccountState


@pytest.fixture
def settings():
    return Settings(
        MAX_DAILY_LOSS=-500.0,
        MAX_DRAWDOWN_PCT=0.05,
        MAX_GROSS_EXPOSURE=1_000_000.0,
        HEARTBEAT_TIMEOUT_S=60.0,
        KILL_SWITCH_ENABLED=False,
        IBKR_ACCOUNT="U12345",
    )


@pytest.fixture
def cb(settings):
    return CircuitBreaker(settings)


@pytest.fixture
def state():
    return AccountState(account="U12345")


class TestCircuitBreaker:
    def test_no_breach_on_fresh_state(self, cb, state):
        result = cb.evaluate(state)
        assert not result.should_halt

    def test_daily_loss_breach(self, cb, state):
        state.update_pnl(daily_pnl=-600.0, unrealized_pnl=0, realized_pnl=0)
        result = cb.evaluate(state)
        assert result.should_halt
        assert "Daily P&L" in result.reason

    def test_daily_loss_at_limit_no_breach(self, cb, state):
        state.update_pnl(daily_pnl=-499.0, unrealized_pnl=0, realized_pnl=0)
        result = cb.evaluate(state)
        assert not result.should_halt

    def test_drawdown_breach(self, cb, state):
        # HWM = 100_000, now at 94_000 → 6% drawdown > 5% limit
        state.update_pnl(0, 0, 0, net_liquidation=100_000)
        state.update_pnl(0, 0, 0, net_liquidation=94_000)
        result = cb.evaluate(state)
        assert result.should_halt
        assert "Drawdown" in result.reason

    def test_drawdown_below_limit(self, cb, state):
        state.update_pnl(0, 0, 0, net_liquidation=100_000)
        state.update_pnl(0, 0, 0, net_liquidation=96_000)  # 4% < 5%
        result = cb.evaluate(state)
        assert not result.should_halt

    def test_gross_exposure_breach(self, cb, state):
        state.update_position("AAPL", 10_000, 100, market_value=1_100_000)
        result = cb.evaluate(state)
        assert result.should_halt
        assert "exposure" in result.reason.lower()

    def test_no_re_trip_when_halted(self, cb, state):
        state.update_pnl(daily_pnl=-999.0, unrealized_pnl=0, realized_pnl=0)
        state.halted = True   # already halted
        result = cb.evaluate(state)
        assert not result.should_halt  # should not re-trigger

    def test_heartbeat_timeout_alert_only(self, cb, state):
        import time
        state.last_heartbeat_ts = time.monotonic() - 120  # 2 min ago
        result = cb.evaluate(state)
        assert not result.should_halt
        assert result.alert_only
        assert "heartbeat" in result.reason.lower()
