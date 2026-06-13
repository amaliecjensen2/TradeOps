"""NATS bro, abonnerer på ordrekommandoer og publicerer alle events.

Dette modul ejer NATS forbindelsen og ruter:
  Indkommende:  orders.> til IBKRGateway.place_order()
  Udgående: et hvilket som helst subject til JetStream publish med core NATS fallback
"""

from __future__ import annotations

import json

import nats
import nats.js
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext

from ibkr_adapter import subjects
from ibkr_adapter.config import Settings
from ibkr_adapter.logging_setup import get_logger
from ibkr_adapter.models import OrderCommand

log = get_logger(__name__)


class NATSBridge:
    """Håndterer NATS forbindelsen og fungerer som event bus for adapteren."""

    def __init__(self, settings: Settings) -> None:
        self._cfg = settings
        self._nc: NATSClient | None = None
        self._js: JetStreamContext | None = None
        self._gateway = None  # sættes af Adapter.run() efter konstruktion

    def set_gateway(self, gateway) -> None:  # undgår cirkulær import
        self._gateway = gateway

    async def connect(self) -> None:
        self._nc = await nats.connect(
            self._cfg.nats_url,
            name="ibkr-adapter",
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,  # uendeligt
            error_cb=self._on_error,
            disconnected_cb=self._on_disconnected,
            reconnected_cb=self._on_reconnected,
        )
        self._js = self._nc.jetstream()
        log.info("nats_bridge.connected", url=self._cfg.nats_url)

    async def subscribe_orders(self) -> None:
        """Abonnér på orders.> og videresend til IBKR gateway."""
        assert self._nc is not None, "kald connect() først"
        # Adapterens indgående side: interne ordrekommandoer kommer ind via NATS.
        await self._nc.subscribe(subjects.ORDERS_INBOX, cb=self._handle_order_msg)
        log.info("nats_bridge.subscribed_orders", subject=subjects.ORDERS_INBOX)

    async def publish(self, subject: str, payload: bytes) -> None:
        """Publicér en rå payload. Falder tilbage til core NATS hvis JS publish fejler."""
        if self._js is None:
            return
        try:
            # Adapterens udgående side: IBKR events publiceres tilbage på bussen.
            await self._js.publish(subject, payload)
        except (nats.js.errors.NoStreamResponseError, nats.errors.TimeoutError) as exc:
            log.warning(
                "nats_bridge.jetstream_publish_failed",
                subject=subject,
                error=str(exc),
            )
            if self._nc:
                await self._nc.publish(subject, payload)

    async def close(self) -> None:
        if self._nc:
            await self._nc.drain()

    # Interne callbacks

    async def _handle_order_msg(self, msg: nats.aio.client.Msg) -> None:
        """Afkod en OrderCommand og videresend til IBKR."""
        try:
            data = json.loads(msg.data)
            cmd = OrderCommand.model_validate(data)
        except Exception as exc:
            log.warning("nats_bridge.order_decode_error", error=str(exc))
            return

        if self._gateway is None or not self._gateway.is_connected:
            log.warning(
                "nats_bridge.order_dropped_no_connection",
                strategy=cmd.strategy,
                symbol=cmd.symbol,
            )
            return

        try:
            # Broens kerneopgave: oversæt en intern ordrebesked til et gateway-kald mod IBKR.
            await self._gateway.place_order(cmd)
        except Exception as exc:
            log.error(
                "nats_bridge.place_order_failed",
                strategy=cmd.strategy,
                symbol=cmd.symbol,
                error=str(exc),
            )

    async def _on_error(self, exc: Exception) -> None:
        log.error("nats_bridge.error", error=str(exc))

    async def _on_disconnected(self) -> None:
        log.warning("nats_bridge.disconnected")

    async def _on_reconnected(self) -> None:
        log.info("nats_bridge.reconnected")
