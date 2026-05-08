"""NATS listener — keeps CheckEngine state up to date.

Subscribes to:
  pnl.>           — per-account daily P&L (proxy for per-strategy loss)
  positions.>     — position snapshots
  marketdata.>    — last prices for fat-finger check
  risk.halt       — circuit-breaker tripped by risk-monitor
  risk.adapter.reconnected — clear halt if desired (manual only for now)
"""

from __future__ import annotations

import json

import nats
from nats.aio.client import Client as NATSClient

from risk_gateway.checks import CheckEngine
from risk_gateway.config import Settings
from risk_gateway.logging_setup import get_logger

log = get_logger(__name__)


class NATSStateSync:
    def __init__(self, settings: Settings, engine: CheckEngine) -> None:
        self._cfg = settings
        self._engine = engine
        self._nc: NATSClient | None = None

    async def connect(self) -> None:
        self._nc = await nats.connect(
            self._cfg.nats_url,
            name="risk-gateway",
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )
        log.info("nats_state_sync.connected", url=self._cfg.nats_url)

    async def subscribe_all(self) -> None:
        assert self._nc is not None
        await self._nc.subscribe("pnl.>",           cb=self._on_pnl)
        await self._nc.subscribe("positions.>",     cb=self._on_position)
        await self._nc.subscribe("marketdata.>",    cb=self._on_marketdata)
        await self._nc.subscribe("risk.halt",       cb=self._on_halt)
        log.info("nats_state_sync.subscribed")

    async def publish(self, subject: str, payload: bytes) -> None:
        if self._nc:
            await self._nc.publish(subject, payload)

    async def close(self) -> None:
        if self._nc:
            await self._nc.drain()

    async def _on_pnl(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            # Map account-level daily PnL to each strategy as a fallback.
            # When per-strategy PnL is available it will override this.
            account = data.get("account", "")
            daily_pnl = float(data.get("daily_pnl", 0))
            # Store under account key; per-strategy key set by strategy fills
            self._engine.strategy_daily_pnl[f"_account_{account}"] = daily_pnl
        except Exception as exc:
            log.warning("nats_state_sync.pnl_error", error=str(exc))

    async def _on_position(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            symbol = data.get("symbol", "")
            position = float(data.get("position", 0))
            # subject: positions.<account>.<symbol> — no strategy info here.
            # We store globally; per-strategy tracking requires strategy tags.
            account = data.get("account", "global")
            key = f"_account_{account}"
            if key not in self._engine.strategy_positions:
                self._engine.strategy_positions[key] = {}
            self._engine.strategy_positions[key][symbol] = position
        except Exception as exc:
            log.warning("nats_state_sync.position_error", error=str(exc))

    async def _on_marketdata(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            symbol = data.get("symbol", "")
            # Accept both bar (close) and tick (last) formats
            price = data.get("close") or data.get("last") or data.get("ask")
            if symbol and price:
                self._engine.last_prices[symbol] = float(price)
        except Exception as exc:
            log.warning("nats_state_sync.marketdata_error", error=str(exc))

    async def _on_halt(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            reason = data.get("reason", "risk-monitor halt")
        except Exception:
            reason = "risk-monitor halt"
        self._engine.halted = True
        self._engine.halt_reason = reason
        log.critical("nats_state_sync.halt_received", reason=reason)
