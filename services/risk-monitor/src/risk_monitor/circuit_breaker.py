"""Circuit breaker — evaluates AccountState against configured thresholds.

Evaluation order (first breach wins):
  1. Max daily loss
  2. Max intra-day drawdown from high-water mark
  3. Max gross exposure
  4. Adapter heartbeat timeout → alert only (no halt by default)

The circuit breaker is stateless between calls — all mutable state lives
in AccountState. Once AccountState.halted = True, evaluate() returns
immediately without re-tripping.
"""

from __future__ import annotations

from dataclasses import dataclass

from risk_monitor.config import Settings
from risk_monitor.logging_setup import get_logger
from risk_monitor.state import AccountState

log = get_logger(__name__)


@dataclass
class BreachResult:
    should_halt: bool
    reason: str = ""
    alert_only: bool = False   # True = send alert but do NOT halt strategies


class CircuitBreaker:
    def __init__(self, settings: Settings) -> None:
        self._max_daily_loss = settings.max_daily_loss           # e.g. -500.0
        self._max_drawdown_pct = settings.max_drawdown_pct       # e.g. 0.05
        self._max_gross_exposure = settings.max_gross_exposure   # e.g. 1_000_000
        self._heartbeat_timeout = settings.heartbeat_timeout_s   # e.g. 60.0
        self._heartbeat_alerted = False   # avoid spamming repeated alerts

    def evaluate(self, state: AccountState) -> BreachResult:
        """Return a BreachResult. Caller decides what action to take."""

        # Already halted — no further action
        if state.halted:
            return BreachResult(should_halt=False)

        # 1. Daily loss limit
        if state.daily_pnl < self._max_daily_loss:
            reason = (
                f"Daily P&L ${state.daily_pnl:,.2f} "
                f"breached limit ${self._max_daily_loss:,.2f}"
            )
            log.warning("circuit_breaker.daily_loss_breach",
                        daily_pnl=state.daily_pnl)
            return BreachResult(should_halt=True, reason=reason)

        # 2. Intra-day drawdown
        if state.drawdown_pct >= self._max_drawdown_pct:
            reason = (
                f"Drawdown {state.drawdown_pct:.1%} "
                f"breached limit {self._max_drawdown_pct:.1%}"
            )
            log.warning("circuit_breaker.drawdown_breach",
                        drawdown_pct=state.drawdown_pct)
            return BreachResult(should_halt=True, reason=reason)

        # 3. Gross exposure
        if state.gross_exposure > self._max_gross_exposure:
            reason = (
                f"Gross exposure ${state.gross_exposure:,.0f} "
                f"exceeds limit ${self._max_gross_exposure:,.0f}"
            )
            log.warning("circuit_breaker.exposure_breach",
                        gross_exposure=state.gross_exposure)
            return BreachResult(should_halt=True, reason=reason)

        # 4. Heartbeat timeout — alert only, strategies keep running
        secs = state.seconds_since_heartbeat
        if secs is not None and secs > self._heartbeat_timeout:
            if not self._heartbeat_alerted:
                self._heartbeat_alerted = True
                return BreachResult(
                    should_halt=False,
                    alert_only=True,
                    reason=f"No heartbeat for {secs:.0f}s",
                )
        else:
            # Reset alert flag when heartbeat recovers
            self._heartbeat_alerted = False

        return BreachResult(should_halt=False)
