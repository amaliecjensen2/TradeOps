"""BaseStrategy, genbrugelig fundament for alle ibkrtrader strategier."""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod

import httpx
import nats
from aiohttp import web
from prometheus_client import Counter, start_http_server

from strategy_nvidia.config import Settings
from strategy_nvidia.logging_setup import get_logger

log = get_logger(__name__)

ORDERS_SENT = Counter("strategy_orders_sent_total",
                      "Orders submitted to risk-gateway", ["strategy", "side"])
ORDERS_REJECTED = Counter("strategy_orders_rejected_total",
                          "Orders rejected by risk-gateway", ["strategy"])
BARS_PROCESSED = Counter("strategy_bars_processed_total",
                         "Market data bars processed", ["strategy", "symbol"])


class BaseStrategy(ABC):
    def __init__(self, settings: Settings) -> None:
        self._cfg = settings
        self._nc = None
        self._http: httpx.AsyncClient | None = None
        self._running = True

    async def run(self) -> None:
        from strategy_nvidia.logging_setup import configure_logging
        configure_logging()

        log.info("strategy.starting", name=self._cfg.strategy_name)

        start_http_server(self._cfg.metrics_port)

        self._http = httpx.AsyncClient(
            base_url=self._cfg.risk_gateway_url,
            timeout=5.0,
        )

        asyncio.create_task(self._start_health_server())

        self._nc = await nats.connect(
            self._cfg.nats_url,
            name=self._cfg.strategy_name,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )

        for symbol in self._cfg.universe:
            subject = f"marketdata.realtime.{symbol}"
            await self._nc.subscribe(subject, cb=self._on_marketdata_msg)
            log.info("strategy.subscribed", subject=subject)

        log.info("strategy.ready", universe=self._cfg.universe)

        try:
            while self._running:
                await asyncio.sleep(1)
        finally:
            await self._cleanup()

    async def _on_marketdata_msg(self, msg: nats.aio.client.Msg) -> None:
        try:
            bar = json.loads(msg.data)
            symbol = bar.get("symbol", "")
            BARS_PROCESSED.labels(
                strategy=self._cfg.strategy_name, symbol=symbol).inc()
            await self.on_bar(bar)
        except Exception as exc:
            log.error("strategy.on_bar_error", error=str(exc))

    @abstractmethod
    async def on_bar(self, bar: dict) -> None:
        """Overskriv denne med din handelslogik."""

    async def buy(self, symbol: str, quantity: float,
                  limit_price: float | None = None) -> bool:
        return await self._submit_order(symbol, "BUY", quantity, limit_price)

    async def sell(self, symbol: str, quantity: float,
                   limit_price: float | None = None) -> bool:
        return await self._submit_order(symbol, "SELL", quantity, limit_price)

    async def _submit_order(self, symbol: str, side: str, quantity: float,
                            limit_price: float | None) -> bool:
        assert self._http is not None
        payload = {
            "strategy": self._cfg.strategy_name,
            "client_id": self._cfg.client_id,
            "idempotency_key": str(uuid.uuid4()),
            "symbol": symbol,
            "side": side,
            "order_type": "LMT" if limit_price else "MKT",
            "quantity": quantity,
            "limit_price": limit_price,
        }
        try:
            resp = await self._http.post("/orders", json=payload)
            if resp.status_code == 200:
                ORDERS_SENT.labels(
                    strategy=self._cfg.strategy_name, side=side).inc()
                log.info("strategy.order_sent", symbol=symbol,
                         side=side, qty=quantity)
                return True
            else:
                data = resp.json()
                ORDERS_REJECTED.labels(strategy=self._cfg.strategy_name).inc()
                log.warning("strategy.order_rejected",
                            symbol=symbol, reason=data.get("reason", ""))
                return False
        except Exception as exc:
            log.error("strategy.order_error", symbol=symbol, error=str(exc))
            return False

    async def _start_health_server(self) -> None:
        app = web.Application()
        app.router.add_get("/healthz", lambda _: web.Response(text="ok"))
        app.router.add_get("/readyz", lambda _: web.Response(text="ready"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self._cfg.health_port)
        await site.start()
        log.info("strategy.health_server_started", port=self._cfg.health_port)

    async def _cleanup(self) -> None:
        if self._nc:
            await self._nc.close()
        if self._http:
            await self._http.aclose()
        log.info("strategy.stopped")
