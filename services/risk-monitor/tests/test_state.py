"""Unit tests for AccountState."""

import time

import pytest

from risk_monitor.state import AccountState


class TestAccountState:
    def test_initial_state(self):
        s = AccountState(account="U12345")
        assert s.daily_pnl == 0.0
        assert s.gross_exposure == 0.0
        assert s.drawdown_pct == 0.0
        assert not s.halted

    def test_pnl_update(self):
        s = AccountState()
        s.update_pnl(daily_pnl=-100, unrealized_pnl=50, realized_pnl=-150)
        assert s.daily_pnl == -100
        assert s.unrealized_pnl == 50

    def test_hwm_only_moves_up(self):
        s = AccountState()
        s.update_pnl(0, 0, 0, net_liquidation=100_000)
        s.update_pnl(0, 0, 0, net_liquidation=110_000)  # new high
        s.update_pnl(0, 0, 0, net_liquidation=95_000)   # drawdown
        # HWM should be 110_000
        assert abs(s._pnl_hwm - 110_000) < 0.01
        # Drawdown = (110_000 - 95_000) / 110_000 ≈ 13.6%
        assert s.drawdown_pct > 0.13

    def test_gross_exposure(self):
        s = AccountState()
        s.update_position("AAPL", 100, 150, market_value=15_000)
        s.update_position("TSLA", -50, 200, market_value=-10_000)
        # Gross = |15_000| + |-10_000| = 25_000
        assert s.gross_exposure == 25_000

    def test_heartbeat_tracking(self):
        s = AccountState()
        assert s.seconds_since_heartbeat is None
        s.record_heartbeat()
        assert s.adapter_connected
        assert s.seconds_since_heartbeat is not None
        assert s.seconds_since_heartbeat < 1.0

    def test_disconnect(self):
        s = AccountState()
        s.record_heartbeat()
        s.record_disconnect()
        assert not s.adapter_connected
