"""FastAPI application for trader-api.

All endpoints are read-only. Writes (orders) go through risk-gateway.

Routes:
  GET /healthz
  GET /readyz
  GET /status               — system status (connected, halted, mode)
  GET /positions            — current open positions
  GET /pnl                  — latest PnL snapshot
  GET /pnl/history          — time-series PnL (from TimescaleDB)
  GET /fills                — recent execution reports
  GET /orders               — recent order events
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from trader_api.db import Database
from trader_api.logging_setup import get_logger
from trader_api.realtime import RealtimeCache

log = get_logger(__name__)


def create_app(db: Database, cache: RealtimeCache, account: str) -> FastAPI:
    app = FastAPI(title="trader-api", version="0.1.0", docs_url="/docs")

    # CORS — dashboard is served from a different origin in development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # Tighten in production with specific domain
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
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
        # Prefer real-time cache; fall back to DB snapshot
        if cache.positions:
            return list(cache.positions.values())
        try:
            return await db.get_positions(account)
        except Exception as exc:
            log.warning("api.positions_db_error", error=str(exc))
            return []

    @app.get("/pnl")
    async def pnl_latest():
        if cache.pnl:
            return cache.pnl
        try:
            result = await db.get_latest_pnl(account)
            return result or {}
        except Exception as exc:
            log.warning("api.pnl_db_error", error=str(exc))
            return {}

    @app.get("/pnl/history")
    async def pnl_history(limit: int = Query(default=200, le=1000)):
        try:
            return await db.get_pnl_history(account, limit=limit)
        except Exception as exc:
            log.warning("api.pnl_history_db_error", error=str(exc))
            return []

    @app.get("/fills")
    async def fills(limit: int = Query(default=100, le=500)):
        try:
            return await db.get_fills(account, limit=limit)
        except Exception as exc:
            log.warning("api.fills_db_error", error=str(exc))
            return []

    @app.get("/orders")
    async def orders(limit: int = Query(default=100, le=500)):
        try:
            return await db.get_order_events(limit=limit)
        except Exception as exc:
            log.warning("api.orders_db_error", error=str(exc))
            return []

    return app
