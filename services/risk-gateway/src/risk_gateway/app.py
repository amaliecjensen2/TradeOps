"""FastAPI application for the risk-gateway.

Routes:
  POST /orders   — pre-trade check + forward to NATS
  GET  /healthz  — liveness
  GET  /readyz   — readiness (NATS connected)
  GET  /metrics  — Prometheus (separate port via prometheus-client)
"""

from __future__ import annotations

import json

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app

from risk_gateway.checks import CheckEngine, RiskRejection
from risk_gateway.logging_setup import get_logger
from risk_gateway.models import OrderAccepted, OrderRejected, OrderRequest

log = get_logger(__name__)

# ── Prometheus metrics ─────────────────────────────────────────────────────
ORDERS_ACCEPTED = Counter(
    "risk_gateway_orders_accepted_total", "Orders passed pre-trade checks", [
        "strategy"]
)
ORDERS_REJECTED = Counter(
    "risk_gateway_orders_rejected_total", "Orders rejected by pre-trade checks",
    ["strategy", "reason_type"],
)
CHECK_LATENCY = Histogram(
    "risk_gateway_check_latency_seconds", "Pre-trade check pipeline latency",
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.010, 0.025, 0.050],
)


def create_app(engine: CheckEngine, nats_sync) -> FastAPI:
    app = FastAPI(title="risk-gateway", docs_url=None, redoc_url=None)

    # Mount Prometheus metrics on /metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        nc = getattr(nats_sync, "_nc", None)
        if nc is None or nc.is_closed:
            return JSONResponse(status_code=503, content={"status": "nats_disconnected"})
        return {"status": "ready"}

    @app.post("/orders", response_model=OrderAccepted, status_code=status.HTTP_200_OK)
    async def submit_order(req: OrderRequest):
        import time
        t0 = time.perf_counter()
        try:
            with CHECK_LATENCY.time():
                engine.check(req)
        except RiskRejection as exc:
            reason_type = _classify_reason(exc.reason)
            ORDERS_REJECTED.labels(strategy=req.strategy,
                                   reason_type=reason_type).inc()
            log.warning(
                "risk_gateway.order_rejected",
                strategy=req.strategy,
                symbol=req.symbol,
                reason=exc.reason,
            )
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=OrderRejected(
                    reason=exc.reason,
                    idempotency_key=req.idempotency_key,
                ).model_dump(mode="json"),
            )

        # Forward accepted order to NATS → ibkr-adapter
        subject = f"orders.{req.strategy}.{req.symbol}"
        payload = req.model_dump_json().encode()
        await nats_sync.publish(subject, payload)

        ORDERS_ACCEPTED.labels(strategy=req.strategy).inc()
        log.info(
            "risk_gateway.order_accepted",
            strategy=req.strategy,
            symbol=req.symbol,
            side=req.side,
            qty=req.quantity,
            latency_ms=f"{(time.perf_counter() - t0) * 1000:.2f}",
        )
        return OrderAccepted(idempotency_key=req.idempotency_key)

    return app


def _classify_reason(reason: str) -> str:
    """Map rejection reason text to a short label for Prometheus."""
    r = reason.lower()
    if "halt" in r:
        return "halt"
    if "fat" in r:
        return "fat_finger"
    if "notional" in r:
        return "notional"
    if "daily" in r or "loss" in r:
        return "daily_loss"
    if "position" in r:
        return "position_limit"
    if "rate" in r:
        return "rate_limit"
    if "duplicate" in r or "idempotency" in r:
        return "duplicate"
    if "restricted" in r:
        return "restricted_symbol"
    return "other"
