"""starter process og binder filerne sammen"""
from __future__ import annotations
import asyncio
import signal
import uvicorn
from trader_api.app import create_app
from trader_api.config import get_settings
from trader_api.db import Database
from trader_api.logging_setup import configure_logging, get_logger
from trader_api.realtime import RealtimeCache

log = get_logger(__name__)


async def _main() -> None:
    settings = get_settings()
    configure_logging()
    log.info("trader_api.starting", port=settings.port)

    db = Database(settings)
    cache = RealtimeCache(settings)

    await db.connect()
    await cache.connect()
    await cache.subscribe_all()

    app = create_app(db, cache, account=settings.ibkr_account)

    config = uvicorn.Config(
        app, host="0.0.0.0", port=settings.port, log_config=None, access_log=False)
    server = uvicorn.Server(config)
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(
        signal.SIGTERM, server.handle_exit, signal.SIGTERM, None)

    await server.serve()
    await cache.close()
    await db.close()
    log.info("trader_api.stopped")


def run() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    run()
