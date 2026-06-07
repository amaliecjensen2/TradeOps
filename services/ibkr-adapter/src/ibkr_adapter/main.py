"""Indgangspunkt forbinder alle komponenter og kører event loopet.

Startrækkefølge:
  1. Konfigurer logging
  2. Start Prometheus metrics serveren
  3. Forbind til NATS
  4. Start health check HTTP serveren
  5. Forbind til IBKR Gateway (blokerer i reconnect loopet)
"""

from __future__ import annotations

import asyncio
import signal

from ibkr_adapter.config import get_settings
from ibkr_adapter.gateway import IBKRGateway
from ibkr_adapter.health import HealthServer
from ibkr_adapter.logging_setup import configure_logging, get_logger
from ibkr_adapter.metrics import start_metrics_server
from ibkr_adapter.nats_bridge import NATSBridge

log = get_logger(__name__)


async def _main() -> None:
    settings = get_settings()

    configure_logging()
    log.info("ibkr_adapter.starting",
             mode="paper" if settings.ibgw_port == 4002 else "live")

    # Metrics
    start_metrics_server(settings.metrics_port)
    log.info("ibkr_adapter.metrics_started", port=settings.metrics_port)

    # NATS
    nats_bridge = NATSBridge(settings)
    await nats_bridge.connect()

    # Health
    health = HealthServer(settings.health_port)
    health.set_dependencies(None, nats_bridge)  # gateway sættes nedenfor
    await health.start()

    # IBKR Gateway publish callback ruter alle TWS events til NATS
    gateway = IBKRGateway(settings, on_event=nats_bridge.publish)
    nats_bridge.set_gateway(gateway)
    health.set_dependencies(gateway, nats_bridge)

    # Abonnér på indkommende ordrekommandoer fra strategier
    await nats_bridge.subscribe_orders()

    # Graceful nedlukning
    loop = asyncio.get_running_loop()

    async def _shutdown() -> None:
        log.info("ibkr_adapter.shutting_down")
        await gateway.stop()
        await nats_bridge.close()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))

    # Dette blokerer indtil gatewayen permanent afbrydes (f.eks. SIGTERM)
    await gateway.start()

    log.info("ibkr_adapter.stopped")


def run() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    run()
