"""Minimal asynkron HTTP server til Kubernetes liveness/readiness probes.

  GET /healthz  altid 200 (processen er i live)
  GET /readyz   200 når der er forbindelse til både NATS og TWS, 503 ellers
"""

from __future__ import annotations

import asyncio

from aiohttp import web

from ibkr_adapter.logging_setup import get_logger

log = get_logger(__name__)


class HealthServer:
    def __init__(self, port: int) -> None:
        self._port = port
        self._gateway = None
        self._nats_bridge = None

    def set_dependencies(self, gateway, nats_bridge) -> None:
        self._gateway = gateway
        self._nats_bridge = nats_bridge

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/healthz", self._healthz)
        app.router.add_get("/readyz", self._readyz)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._port)
        await site.start()
        log.info("health_server.started", port=self._port)

    async def _healthz(self, _request: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def _readyz(self, _request: web.Request) -> web.Response:
        ibkr_ok = self._gateway is not None and self._gateway.is_connected
        nats_ok = (
            self._nats_bridge is not None
            and self._nats_bridge._nc is not None
            and not self._nats_bridge._nc.is_closed
        )

        if ibkr_ok and nats_ok:
            return web.Response(text="ready")

        problems = []
        if not ibkr_ok:
            problems.append("ibkr_disconnected")
        if not nats_ok:
            problems.append("nats_disconnected")

        return web.Response(
            status=503,
            text=", ".join(problems),
        )
