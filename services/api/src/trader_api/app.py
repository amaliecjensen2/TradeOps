"""FastAPI applikation for trader-api.

Alle endpoints er read-only og leverer live state fra NATS cachen.

Ruter:
  GET /healthz    liveness probe (processen kører)
  GET /readyz     readiness probe (NATS forbindelsen er oppe)
  GET /status     systemstatus (adapter connected, halt state, mode)
  GET /positions  åbne positioner
  GET /pnl        seneste PnL snapshot
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from trader_api.logging_setup import get_logger
from trader_api.realtime import RealtimeCache

log = get_logger(__name__)


def create_app(cache: RealtimeCache, account: str) -> FastAPI:
    app = FastAPI(title="trader-api", version="0.1.0", docs_url="/docs")

    # CORS: dashboarden kører på et andet origin (sin egen pod / domæne) og
    # skal kunne kalde API'en fra browseren. Kun GET er tilladt da alt er read-only.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        # Cachen tæller først som klar når NATS forbindelsen er etableret.
        nc = getattr(cache, "_nc", None)
        if nc is None or nc.is_closed:
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {"status": "ready"}

    @app.get("/status")
    async def system_status():
        return {
            "adapter_connected": cache.adapter_connected,
            "halted": cache.halted,
            "halt_reason": cache.halt_reason,
            "account": account,
        }

    @app.get("/positions")
    async def positions():
        return list(cache.positions.values())

    @app.get("/pnl")
    async def pnl_latest():
        return cache.pnl or {}

    return app
