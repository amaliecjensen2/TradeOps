"""FastAPI applikation for risk gateway.

Ruter:
  POST /orders   pre trade check + videresend til NATS
  GET  /healthz  liveness
  GET  /readyz   readiness (NATS forbundet)
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from risk_gateway.checks import CheckEngine, RiskRejection
from risk_gateway.logging_setup import get_logger
from risk_gateway.models import OrderAccepted, OrderRejected, OrderRequest

log = get_logger(__name__)


def create_app(engine: CheckEngine, nats_sync) -> FastAPI:
    app = FastAPI(title="risk-gateway", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        # Hent NATS-klienten defensivt, selv om den er et internt felt.
        nc = getattr(nats_sync, "_nc", None)
        if nc is None or nc.is_closed:
            return JSONResponse(status_code=503, content={"status": "nats_disconnected"})
        if not engine.primed:
            return JSONResponse(
                status_code=503,
                content={"status": "priming", "reason": engine.prime_reason},
            )
        return {"status": "ready"}

    @app.post("/orders", response_model=OrderAccepted, status_code=status.HTTP_200_OK)
    async def submit_order(req: OrderRequest):
        import time
        t0 = time.perf_counter()
        # Fail-closed cold start: indtil adapteren har publiceret snapshot_complete
        # ville fat-finger / daily-loss / position-limit checks passere mod tom
        # state. Returnér 503 så strategier retry'er i stedet for at handle blindt.
        if not engine.primed:
            log.warning(
                "risk_gateway.order_rejected_priming",
                strategy=req.strategy,
                symbol=req.symbol,
                reason=engine.prime_reason,
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=OrderRejected(
                    reason=f"gateway priming: {engine.prime_reason}",
                    idempotency_key=req.idempotency_key,
                ).model_dump(mode="json"),
            )
        try:
            # Kaster RiskRejection hvis ordren bryder en risikoregel.
            engine.check(req)
        except RiskRejection as exc:
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
                    # Gør Pydantic-modellen klar til JSON-responsen.
                ).model_dump(mode="json"),
            )

        # Videresend accepteret ordre til NATS, til ibkr adapter
        # Subjectet styrer hvilken strategi og hvilket symbol ordren tilhører.
        subject = f"orders.{req.strategy}.{req.symbol}"
        # NATS forventer bytes, så modellen serialiseres til JSON først.
        payload = req.model_dump_json().encode()
        await nats_sync.publish(subject, payload)

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
