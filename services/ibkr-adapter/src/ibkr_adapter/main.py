"""Entry point — wires all components together and runs the event loop.

Start order:
  1. Configure logging
  2. Start Prometheus metrics server
  3. Connect to NATS
  4. Start health-check HTTP server
  5. Connect to IBKR Gateway (blocks in reconnect loop)
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
    health.set_dependencies(None, nats_bridge)  # gateway set below
    await health.start()

    # IBKR Gateway — publish callback routes all TWS events to NATS
    gateway = IBKRGateway(settings, on_event=nats_bridge.publish)
    nats_bridge.set_gateway(gateway)
    health.set_dependencies(gateway, nats_bridge)

    # Subscribe to inbound order commands from strategies
    await nats_bridge.subscribe_orders()

    # Graceful shutdown
    loop = asyncio.get_running_loop()

    async def _shutdown() -> None:
        log.info("ibkr_adapter.shutting_down")
        await gateway.stop()
        await nats_bridge.close()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))

    # This blocks until gateway disconnects permanently (e.g., SIGTERM)
    await gateway.start()

    log.info("ibkr_adapter.stopped")


def run() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    run()
