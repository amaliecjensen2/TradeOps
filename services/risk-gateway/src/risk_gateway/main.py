"""Indgangspunkt for risk gateway."""

from __future__ import annotations

import asyncio
import signal

import uvicorn

from risk_gateway.app import create_app
from risk_gateway.checks import CheckEngine
from risk_gateway.config import get_settings
from risk_gateway.logging_setup import configure_logging, get_logger
from risk_gateway.nats_sync import NATSStateSync

log = get_logger(__name__)


async def _main() -> None:
    settings = get_settings()
    configure_logging()

    log.info("risk_gateway.starting",
             port=settings.port, mode=settings.ibkr_mode)

    engine = CheckEngine(settings)
    nats_sync = NATSStateSync(settings, engine)

    await nats_sync.connect()
    await nats_sync.subscribe_all()

    app = create_app(engine, nats_sync)

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.port,
        log_config=None,    # structlog håndterer logging
        access_log=False,
    )
    server = uvicorn.Server(config)

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(
        signal.SIGTERM, server.handle_exit, signal.SIGTERM, None)

    await server.serve()
    await nats_sync.close()
    log.info("risk_gateway.stopped")


def run() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    run()
