"""NATS subscriptions for the risk monitor.

Subscribes to:
  fills.>                   — execution reports → update realized PnL
  pnl.>                     — PnL snapshots from adapter
  positions.>               — position snapshots from adapter
  risk.adapter.heartbeat    — liveness signal from ibkr-adapter
  risk.adapter.disconnected — IBKR connection lost
  risk.adapter.reconnected  — IBKR connection restored

All messages are decoded with pydantic and written into AccountState.
"""

from __future__ import annotations

import json

import nats
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext

from risk_monitor.config import Settings
from risk_monitor.logging_setup import get_logger
from risk_monitor.state import AccountState

log = get_logger(__name__)


class NATSListener:
    def __init__(self, settings: Settings, state: AccountState) -> None:
        self._cfg = settings
        self._state = state
        self._nc: NATSClient | None = None
        self._js: JetStreamContext | None = None

    async def connect(self) -> None:
        self._nc = await nats.connect(
            self._cfg.nats_url,
            name="risk-monitor",
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
            error_cb=self._on_error,
            reconnected_cb=self._on_reconnected,
        )
        self._js = self._nc.jetstream()
        log.info("nats_listener.connected", url=self._cfg.nats_url)

    async def subscribe_all(self) -> None:
        assert self._nc is not None
        await self._nc.subscribe("fills.>",               cb=self._on_fill)
        await self._nc.subscribe("pnl.>",                 cb=self._on_pnl)
        await self._nc.subscribe("positions.>",           cb=self._on_position)
        await self._nc.subscribe("risk.adapter.heartbeat",   cb=self._on_heartbeat)
        await self._nc.subscribe("risk.adapter.disconnected", cb=self._on_adapter_disconnected)
        await self._nc.subscribe("risk.adapter.reconnected",  cb=self._on_adapter_reconnected)
        log.info("nats_listener.subscribed_all")

    async def publish(self, subject: str, payload: bytes) -> None:
        """Publish to NATS (used by kill switch to emit risk.halt)."""
        if self._js is None:
            return
        try:
            await self._js.publish(subject, payload)
        except Exception:
            if self._nc:
                await self._nc.publish(subject, payload)

    async def close(self) -> None:
        if self._nc:
            await self._nc.drain()

    # ------------------------------------------------------------------ #
    # Message handlers                                                     #
    # ------------------------------------------------------------------ #

    async def _on_fill(self, msg: nats.aio.client.Msg) -> None:
        try:
            data = json.loads(msg.data)
            account = data.get("account", self._cfg.ibkr_account)
            symbol = data.get("symbol", "")
            log.debug("nats_listener.fill", symbol=symbol, account=account)
            # Fills themselves don't update position directly; PnL snapshots do.
            # Log for audit trail purposes.
        except Exception as exc:
            log.warning("nats_listener.fill_decode_error", error=str(exc))

    async def _on_pnl(self, msg: nats.aio.client.Msg) -> None:
        try:
            data = json.loads(msg.data)
            self._state.update_pnl(
                daily_pnl=float(data.get("daily_pnl", 0)),
                unrealized_pnl=float(data.get("unrealized_pnl", 0)),
                realized_pnl=float(data.get("realized_pnl", 0)),
                net_liquidation=float(data.get("net_liquidation", 0)),
            )
            if not self._state.account and data.get("account"):
                self._state.account = data["account"]
            log.debug(
                "nats_listener.pnl_updated",
                daily_pnl=self._state.daily_pnl,
                drawdown_pct=f"{self._state.drawdown_pct:.2%}",
            )
        except Exception as exc:
            log.warning("nats_listener.pnl_decode_error", error=str(exc))

    async def _on_position(self, msg: nats.aio.client.Msg) -> None:
        try:
            data = json.loads(msg.data)
            self._state.update_position(
                symbol=data.get("symbol", ""),
                position=float(data.get("position", 0)),
                avg_cost=float(data.get("avg_cost", 0)),
                market_value=float(data.get("market_value", 0)),
            )
        except Exception as exc:
            log.warning("nats_listener.position_decode_error", error=str(exc))

    async def _on_heartbeat(self, msg: nats.aio.client.Msg) -> None:
        self._state.record_heartbeat()
        log.debug("nats_listener.heartbeat_received")

    async def _on_adapter_disconnected(self, msg: nats.aio.client.Msg) -> None:
        try:
            data = json.loads(msg.data)
            reason = data.get("reason", "unknown")
        except Exception:
            reason = "unknown"
        self._state.record_disconnect()
        log.warning("nats_listener.adapter_disconnected", reason=reason)

    async def _on_adapter_reconnected(self, msg: nats.aio.client.Msg) -> None:
        self._state.record_heartbeat()
        log.info("nats_listener.adapter_reconnected")

    async def _on_error(self, exc: Exception) -> None:
        log.error("nats_listener.error", error=str(exc))

    async def _on_reconnected(self) -> None:
        log.info("nats_listener.reconnected")
