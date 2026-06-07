"""IBKR Gateway forbindelsesmanager.

Indpakker ib_insync med:
  Asynkront reconnect loop med eksponentiel back off
  Event callbacks der publicerer strukturerede beskeder til en callback kø
  Heartbeat publicering på et konfigurerbart interval

Gatewayen udsender events ved at kalde det `on_event` callable der er givet ved
konstruktion. IBKRGateway er bevidst fri for NATS imports, så den kan unit testes
med en mock callback.

dette er broen mellem interactive brokers og resten af systemet
"""

from __future__ import annotations

import asyncio
import math
from typing import Awaitable, Callable

import ib_insync as ibi

from ibkr_adapter import metrics, subjects
from ibkr_adapter.config import Settings
from ibkr_adapter.logging_setup import get_logger
from ibkr_adapter.models import (
    AdapterDisconnected,
    AdapterHeartbeat,
    Fill,
    OrderCommand,
    PnLSnapshot,
    PositionSnapshot,
    SecType,
    Side,
    Tick,
)

log = get_logger(__name__)

# Type alias for det callback adapteren bruger til at rute events tilbage til NATS.
EventCallback = Callable[[str, bytes], Awaitable[None]]

_IB_SIDE_MAP = {"BOT": Side.BUY, "SLD": Side.SELL}


def _clean(value) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


class IBKRGateway:
    """Håndterer en enkelt TWS forbindelse og oversætter TWS events til events."""

    HEARTBEAT_INTERVAL_S = 15

    def __init__(self, settings: Settings, on_event: EventCallback) -> None:
        self._cfg = settings
        self._on_event = on_event
        self._ib = ibi.IB()
        self._connected = False
        self._heartbeat_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None

        # Tilkobl TWS callbacks
        self._ib.disconnectedEvent += self._handle_disconnected
        self._ib.execDetailsEvent += self._handle_exec_details
        self._ib.pnlEvent += self._handle_pnl
        self._ib.positionEvent += self._handle_position
        self._ib.pendingTickersEvent += self._handle_pending_tickers

    # Offentligt API

    async def start(self) -> None:
        """Forbind og start heartbeat loopet. Kører for evigt."""
        await self._connect_with_retry()

    async def stop(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._ib.isConnected():
            self._ib.disconnect()
        log.info("ibkr_gateway.stopped")

    async def subscribe_marketdata(self, symbols: list[str]) -> None:
        # Falder tilbage til forsinkede data hvis kontoen ikke har en live abonnement.
        self._ib.reqMarketDataType(3)
        for symbol in symbols:
            contract = ibi.Stock(symbol, "SMART", "USD")
            qualified = await self._ib.qualifyContractsAsync(contract)
            if not qualified:
                log.warning(
                    "ibkr_gateway.marketdata_qualify_failed", symbol=symbol)
                continue
            self._ib.reqMktData(qualified[0], "", False, False)
            log.info("ibkr_gateway.marketdata_subscribed", symbol=symbol)

    async def place_order(self, cmd: OrderCommand) -> int:
        """Indsend en ordre til TWS. Returnerer TWS orderId."""
        contract = self._build_contract(cmd)
        order = self._build_order(cmd)
        trade = self._ib.placeOrder(contract, order)
        log.info(
            "ibkr_gateway.order_placed",
            symbol=cmd.symbol,
            side=cmd.side,
            qty=cmd.quantity,
            order_id=trade.order.orderId,
            strategy=cmd.strategy,
        )
        return trade.order.orderId

    @property
    def is_connected(self) -> bool:
        return self._connected

    # Forbindelseshåndtering

    async def _connect_with_retry(self) -> None:
        attempt = 0
        max_attempts = self._cfg.max_reconnect_attempts  # 0 = uendeligt

        while True:
            attempt += 1
            log.info(
                "ibkr_gateway.connecting",
                host=self._cfg.ibgw_host,
                port=self._cfg.ibgw_port,
                attempt=attempt,
            )
            try:
                await self._ib.connectAsync(
                    self._cfg.ibgw_host,
                    self._cfg.ibgw_port,
                    clientId=self._cfg.ibkr_client_id,
                    timeout=20,
                )
                self._connected = True
                metrics.CONNECTED.set(1)
                log.info("ibkr_gateway.connected")

                await self._on_event(
                    subjects.RECONNECTED if attempt > 1 else subjects.HEARTBEAT,
                    AdapterHeartbeat(
                        status="connected",
                        ibgw_host=self._cfg.ibgw_host,
                        ibgw_port=self._cfg.ibgw_port,
                        client_id=self._cfg.ibkr_client_id,
                    ).model_dump_json().encode(),
                )

                # Abonner på PnL opdateringer
                if self._cfg.ibkr_account:
                    self._ib.reqPnL(self._cfg.ibkr_account)

                # Abonnér på realtime markedsdata for det konfigurerede univers
                if self._cfg.universe_list:
                    await self.subscribe_marketdata(self._cfg.universe_list)

                self._heartbeat_task = asyncio.create_task(
                    self._heartbeat_loop())

                # eventkit.Event er ikke en asyncio.Event; hold tasken i live
                # indtil ib_insync rapporterer at socket er afbrudt.
                while self._ib.isConnected():
                    await asyncio.sleep(1)

            except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as exc:
                self._connected = False
                metrics.CONNECTED.set(0)
                log.warning(
                    "ibkr_gateway.connect_failed",
                    error=str(exc),
                    attempt=attempt,
                )
                if max_attempts and attempt >= max_attempts:
                    log.error("ibkr_gateway.giving_up", attempts=attempt)
                    raise

                await self._emit_disconnected(str(exc))
                interval = min(self._cfg.reconnect_interval_s *
                               (2 ** min(attempt - 1, 5)), 300)
                log.info("ibkr_gateway.reconnecting_in", seconds=interval)
                await asyncio.sleep(interval)

    async def _handle_disconnected(self) -> None:
        self._connected = False
        metrics.CONNECTED.set(0)
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        log.warning("ibkr_gateway.disconnected")
        await self._emit_disconnected("TWS rapporterede afbrydelse")

    async def _emit_disconnected(self, reason: str) -> None:
        await self._on_event(
            subjects.DISCONNECTED,
            AdapterDisconnected(
                ibgw_host=self._cfg.ibgw_host,
                ibgw_port=self._cfg.ibgw_port,
                reason=reason,
            ).model_dump_json().encode(),
        )

    # TWS event handlere, publicerer til NATS via callback

    async def _handle_exec_details(
        self, trade: ibi.Trade, fill: ibi.Fill
    ) -> None:
        account = fill.execution.acctNumber
        symbol = fill.contract.symbol
        side_raw = fill.execution.side  # "BOT" eller "SLD"

        msg = Fill(
            account=account,
            symbol=symbol,
            sec_type=fill.contract.secType,
            exchange=fill.execution.exchange,
            side=_IB_SIDE_MAP.get(side_raw, Side.BUY),
            quantity=fill.execution.shares,
            price=fill.execution.price,
            commission=fill.commissionReport.commission if fill.commissionReport else None,
            perm_id=fill.execution.permId,
            exec_id=fill.execution.execId,
            order_ref=fill.execution.orderRef or "",
        )
        await self._on_event(subjects.fills(account, symbol), msg.model_dump_json().encode())
        metrics.FILLS_PUBLISHED.labels(account=account).inc()
        log.info("ibkr_gateway.fill", symbol=symbol,
                 side=msg.side, qty=msg.quantity, price=msg.price)

    async def _handle_pnl(self, pnl: ibi.PnL) -> None:
        account = pnl.account
        msg = PnLSnapshot(
            account=account,
            daily_pnl=pnl.dailyPnL or 0.0,
            unrealized_pnl=pnl.unrealizedPnL or 0.0,
            realized_pnl=pnl.realizedPnL or 0.0,
        )
        await self._on_event(subjects.pnl(account), msg.model_dump_json().encode())
        metrics.PNL_DAILY.labels(account=account).set(pnl.dailyPnL or 0.0)

    async def _handle_pending_tickers(self, tickers: set[ibi.Ticker]) -> None:
        for t in tickers:
            symbol = t.contract.symbol if t.contract else ""
            if not symbol:
                continue
            last = _clean(t.last)
            bid = _clean(t.bid)
            ask = _clean(t.ask)
            if last is None and bid is None and ask is None:
                continue
            msg = Tick(symbol=symbol, bid=bid, ask=ask, last=last)
            await self._on_event(
                subjects.marketdata("realtime", symbol),
                msg.model_dump_json().encode(),
            )

    async def _handle_position(self, position: ibi.Position) -> None:
        account = position.account
        symbol = position.contract.symbol
        msg = PositionSnapshot(
            account=account,
            symbol=symbol,
            sec_type=position.contract.secType,
            avg_cost=position.avgCost,
            position=position.position,
        )
        await self._on_event(subjects.positions(account, symbol), msg.model_dump_json().encode())

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL_S)
            if not self._ib.isConnected():
                break
            msg = AdapterHeartbeat(
                status="connected",
                ibgw_host=self._cfg.ibgw_host,
                ibgw_port=self._cfg.ibgw_port,
                client_id=self._cfg.ibkr_client_id,
            )
            await self._on_event(subjects.HEARTBEAT, msg.model_dump_json().encode())

    # Hjælpere

    @staticmethod
    def _build_contract(cmd: OrderCommand) -> ibi.Contract:
        return ibi.Contract(
            symbol=cmd.symbol,
            secType=cmd.sec_type.value,
            exchange=cmd.exchange,
            currency=cmd.currency,
        )

    @staticmethod
    def _build_order(cmd: OrderCommand) -> ibi.Order:
        order = ibi.Order(
            action=cmd.side.value,
            totalQuantity=cmd.quantity,
            orderType=cmd.order_type.value,
            orderRef=cmd.idempotency_key,
        )
        if cmd.limit_price is not None:
            order.lmtPrice = cmd.limit_price
        if cmd.stop_price is not None:
            order.auxPrice = cmd.stop_price
        return order
