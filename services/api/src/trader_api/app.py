"""FastAPI applikation for trader api.

Alle endpoints er kun læs.

Ruter:
  GET /healthz
  GET /readyz
  GET /status               systemstatus (connected, halted, mode)
  GET /positions            åbne positioner
  GET /pnl                  seneste PnL snapshot
  GET /pnl/history          tidsserie PnL (fra TimescaleDB)
  GET /fills                seneste udførelsesrapporter
  GET /orders               seneste ordreevents
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

    app.add_middleware(
        CORSMiddleware,  # browseren må kalde api fra en anden orgin
        allow_origins=["*"],  # Alle må kalde API
        allow_methods=["GET"],  # kun get req er tilladt
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz():  # tjek for at apis kan kaldes / lever processen?
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        nc = getattr(cache, "_nc", None)  # prøver at hente nats fra cachen
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

    @app.get("/positions")  # retunerer aktuelle positioner
    async def positions():
        # forsøger først cachen, hvis tom hent fra DB
        if cache.positions:
            return list(cache.positions.values())
        try:
            return await db.get_positions(account)
        except Exception as exc:
            log.warning("api.positions_db_error", error=str(exc))
            return []

    @app.get("/pnl")  # retunerer profit n loss
    async def pnl_latest():
        if cache.pnl:
            return cache.pnl
        try:
            result = await db.get_latest_pnl(account)
            return result or {}
        except Exception as exc:
            log.warning("api.pnl_db_error", error=str(exc))
            return {}

    @app.get("/pnl/history")  # retunerer pnl over tid
    async def pnl_history(limit: int = Query(default=200, le=1000)):
        try:
            # query db for pnl history, med limit på def 200 rækker og max 1000 rækker
            # til skalering kan der indføres pagination, hvor man deler data op i sider, f.eks giv mig 1 side med 20 rækker
            return await db.get_pnl_history(account, limit=limit)
        except Exception as exc:
            log.warning("api.pnl_history_db_error", error=str(exc))
            return []

    @app.get("/fills")  # retunerer faktiske udførte handler
    async def fills(limit: int = Query(default=100, le=500)):
        try:
            return await db.get_fills(account, limit=limit)
        except Exception as exc:
            log.warning("api.fills_db_error", error=str(exc))
            return []

    @app.get("/orders")  # retunerer odrer
    async def orders(limit: int = Query(default=100, le=500)):
        try:
            return await db.get_order_events(limit=limit)
        except Exception as exc:
            log.warning("api.orders_db_error", error=str(exc))
            return []

    return app
