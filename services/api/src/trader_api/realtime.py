"""NATS real-time state cache.

Keeps an in-memory snapshot of current positions, PnL, and system status
so the API can serve low-latency reads without hitting the database.
Updates are pushed from ibkr-adapter via NATS.
"""

from __future__ import annotations

import json

import nats

from trader_api.config import Settings
from trader_api.logging_setup import get_logger

log = get_logger(__name__)


class RealtimeCache:
    def __init__(self, settings: Settings) -> None:
        self._cfg = settings
        self._nc = None

        # Snapshots — overwritten on every NATS message
        self.positions: dict[str, dict] = {}    # symbol → snapshot
        self.pnl: dict | None = None
        self.adapter_connected: bool = False
        self.halted: bool = False
        self.halt_reason: str = ""

    async def connect(self) -> None:
        self._nc = await nats.connect(
            self._cfg.nats_url,
            name="trader-api",
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )
        log.info("realtime_cache.connected")

    async def subscribe_all(self) -> None:
        assert self._nc
        await self._nc.subscribe("positions.>",           cb=self._on_position)
        await self._nc.subscribe("pnl.>",                 cb=self._on_pnl)
        await self._nc.subscribe("risk.adapter.heartbeat",   cb=self._on_heartbeat)
        await self._nc.subscribe("risk.adapter.disconnected", cb=self._on_disconnect)
        await self._nc.subscribe("risk.halt",             cb=self._on_halt)

    async def close(self) -> None:
        if self._nc:
            await self._nc.drain()

    async def _on_position(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            symbol = data.get("symbol", "")
            if symbol:
                self.positions[symbol] = data
        except Exception:
            pass

    async def _on_pnl(self, msg) -> None:
        try:
            self.pnl = json.loads(msg.data)
        except Exception:
            pass

    async def _on_heartbeat(self, msg) -> None:
        self.adapter_connected = True

    async def _on_disconnect(self, msg) -> None:
        self.adapter_connected = False

    async def _on_halt(self, msg) -> None:
        try:
            data = json.loads(msg.data)
            self.halt_reason = data.get("reason", "")
        except Exception:
            pass
        self.halted = True
