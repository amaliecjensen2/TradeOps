"""Health check HTTP server til Kubernetes probes."""

from __future__ import annotations

from aiohttp import web

from risk_monitor.logging_setup import get_logger

log = get_logger(__name__)


class HealthServer:
    def __init__(self, port: int) -> None:
        self._port = port
        self._state = None
        self._is_leader_fn = lambda: False

    def set_dependencies(self, state, is_leader_fn) -> None:
        self._state = state
        self._is_leader_fn = is_leader_fn

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/healthz", self._healthz)
        app.router.add_get("/readyz", self._readyz)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._port)
        await site.start()
        log.info("health_server.started", port=self._port)

    async def _healthz(self, _: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def _readyz(self, _: web.Request) -> web.Response:
        # Klar når state har modtaget mindst ét heartbeat ELLER vi er follower
        if self._state is None:
            return web.Response(status=503, text="not_initialised")
        return web.Response(text="ready")
