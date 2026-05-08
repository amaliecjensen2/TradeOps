"""Live risk state maintained by the NATS listener.

AccountState is a pure in-memory data structure — no external calls.
The NATS listener writes into it; the circuit breaker reads from it.
Thread-safety is achieved by running everything in a single asyncio event loop.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class PositionState:
    symbol: str
    position: float = 0.0          # number of shares/contracts (signed)
    avg_cost: float = 0.0
    market_value: float = 0.0      # updated when we receive position snapshots


@dataclass
class AccountState:
    account: str = ""

    # --------------------------------------------------------- P&L
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    net_liquidation: float = 0.0

    # High-water mark for intra-day drawdown calculation.
    # Set to net_liquidation on first PnL update; only moves up after that.
    _pnl_hwm: float = field(default=0.0, repr=False)
    _hwm_initialised: bool = field(default=False, repr=False)

    # --------------------------------------------------- Positions
    positions: dict[str, PositionState] = field(default_factory=dict)

    # --------------------------------------------------- Heartbeat
    # Unix timestamp of the last heartbeat received from the adapter.
    # None = never received (adapter may not have started yet).
    last_heartbeat_ts: float | None = None
    adapter_connected: bool = False

    # --------------------------------------------------- Halt flag
    # Set to True by the circuit breaker; prevents re-entry.
    halted: bool = False
    halt_reason: str = ""

    # ----------------------------------------------------------
    def update_pnl(self, daily_pnl: float, unrealized_pnl: float,
                   realized_pnl: float, net_liquidation: float = 0.0) -> None:
        self.daily_pnl = daily_pnl
        self.unrealized_pnl = unrealized_pnl
        self.realized_pnl = realized_pnl
        if net_liquidation:
            self.net_liquidation = net_liquidation

        # Initialise HWM on first data point
        if not self._hwm_initialised and net_liquidation > 0:
            self._pnl_hwm = net_liquidation
            self._hwm_initialised = True
        elif net_liquidation > self._pnl_hwm:
            self._pnl_hwm = net_liquidation

    def update_position(self, symbol: str, position: float,
                        avg_cost: float, market_value: float = 0.0) -> None:
        if symbol not in self.positions:
            self.positions[symbol] = PositionState(symbol=symbol)
        ps = self.positions[symbol]
        ps.position = position
        ps.avg_cost = avg_cost
        if market_value:
            ps.market_value = market_value

    def record_heartbeat(self) -> None:
        self.last_heartbeat_ts = time.monotonic()
        self.adapter_connected = True

    def record_disconnect(self) -> None:
        self.adapter_connected = False

    # ----------------------------------------------------------
    @property
    def gross_exposure(self) -> float:
        """Sum of absolute market values across all positions."""
        return sum(abs(p.market_value) for p in self.positions.values())

    @property
    def drawdown_pct(self) -> float:
        """Current drawdown from today's high-water mark (0.05 = 5%)."""
        if self._pnl_hwm <= 0:
            return 0.0
        return (self._pnl_hwm - self.net_liquidation) / self._pnl_hwm

    @property
    def seconds_since_heartbeat(self) -> float | None:
        if self.last_heartbeat_ts is None:
            return None
        return time.monotonic() - self.last_heartbeat_ts
