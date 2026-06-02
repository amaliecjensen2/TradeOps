"""NATS bridge - subscribes to order commands, publishes all events.

This module owns the NATS connection and routes:
  - Inbound:  orders.> to IBKRGateway.place_order()
  - Outbound: any subject to JetStream publish with core NATS fallback
"""

from __future__ import annotations

import json

import nats
import nats.js
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext

from ibkr_adapter import metrics, subjects
from ibkr_adapter.config import Settings
from ibkr_adapter.logging_setup import get_logger
from ibkr_adapter.models import OrderCommand

log = get_logger(__name__)

# Streams that must exist before the adapter can publish.
# The chart's nats-streams.yaml (NACK CRDs) creates them in Kubernetes.
# In dev you can run `nats stream add` manually.
_JETSTREAM_SUBJECTS = {
    "ORDERS",
    "FILLS",
    "RISK",
}


class NATSBridge:
    """Manages the NATS connection and acts as the event bus for the adapter."""

    def __init__(self, settings: Settings) -> None:
        self._cfg = settings
        self._nc: NATSClient | None = None
        self._js: JetStreamContext | None = None
        self._gateway = None  # set by Adapter.run() after construction

    def set_gateway(self, gateway) -> None:  # avoids circular import
        self._gateway = gateway

    async def connect(self) -> None:
        self._nc = await nats.connect(
            self._cfg.nats_url,
            name="ibkr-adapter",
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,  # infinite
            error_cb=self._on_error,
            disconnected_cb=self._on_disconnected,
            reconnected_cb=self._on_reconnected,
        )
        self._js = self._nc.jetstream()
        log.info("nats_bridge.connected", url=self._cfg.nats_url)

    async def subscribe_orders(self) -> None:
        """Subscribe to orders.> and forward to IBKR gateway."""
        assert self._nc is not None, "call connect() first"
        await self._nc.subscribe(subjects.ORDERS_INBOX, cb=self._handle_order_msg)
        log.info("nats_bridge.subscribed_orders", subject=subjects.ORDERS_INBOX)

    async def publish(self, subject: str, payload: bytes) -> None:
        """Publish a raw payload. Falls back to core NATS if JS publish fails."""
        if self._js is None:
            return
        try:
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

    # ------------------------------------------------------------------ #
    # Internal callbacks
    # ------------------------------------------------------------------ #

    async def _handle_order_msg(self, msg: nats.aio.client.Msg) -> None:
        """Decode an OrderCommand and forward to IBKR."""
        try:
            data = json.loads(msg.data)
            cmd = OrderCommand.model_validate(data)
        except Exception as exc:
            log.warning("nats_bridge.order_decode_error", error=str(exc))
            metrics.ORDERS_REJECTED.labels(
                strategy="unknown", reason="decode_error"
            ).inc()
            return

        metrics.ORDERS_RECEIVED.labels(strategy=cmd.strategy).inc()

        if self._gateway is None or not self._gateway.is_connected:
            log.warning(
                "nats_bridge.order_dropped_no_connection",
                strategy=cmd.strategy,
                symbol=cmd.symbol,
            )
            metrics.ORDERS_REJECTED.labels(
                strategy=cmd.strategy, reason="not_connected"
            ).inc()
            return

        import time

        t0 = time.perf_counter()
        try:
            await self._gateway.place_order(cmd)
            metrics.ORDERS_PLACED.labels(strategy=cmd.strategy).inc()
            metrics.ORDER_LATENCY.observe(time.perf_counter() - t0)
        except Exception as exc:
            log.error(
                "nats_bridge.place_order_failed",
                strategy=cmd.strategy,
                symbol=cmd.symbol,
                error=str(exc),
            )
            metrics.ORDERS_REJECTED.labels(
                strategy=cmd.strategy, reason="tws_error"
            ).inc()

    async def _on_error(self, exc: Exception) -> None:
        log.error("nats_bridge.error", error=str(exc))

    async def _on_disconnected(self) -> None:
        log.warning("nats_bridge.disconnected")

    async def _on_reconnected(self) -> None:
        log.info("nats_bridge.reconnected")
