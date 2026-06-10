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

from ibkr_adapter import subjects
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
    SnapshotComplete,
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
    # Hvor længe vi venter på det første streaming pnl event efter
    # reqAccountUpdatesAsync er færdig, før vi syntetiserer et nul-snapshot
    # og frigiver risk-gateway. TWS leverer normalt pnl inden for et sekund;
    # 5s er rigeligt og holder også cold-start latency lav.
    SNAPSHOT_PNL_TIMEOUT_S = 5.0

    def __init__(self, settings: Settings, on_event: EventCallback) -> None:
        self._cfg = settings
        self._on_event = on_event
        self._ib = ibi.IB()
        self._connected = False
        self._heartbeat_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        # Seneste NetLiquidation set fra accountValueEvent. Cachet så vi kan
        # rige PnLSnapshot med kontoens nettoværdi (risk-monitor bruger den
        # til HWM/drawdown beregning).
        self._latest_net_liquidation: float | None = None
        # Sættes ved første pnlEvent efter (re)connect. Bruges af snapshot
        # flowet til at vide hvornår initial state er komplet.
        self._pnl_received: asyncio.Event = asyncio.Event()

        # Tilkobl TWS callbacks
        self._ib.disconnectedEvent += self._handle_disconnected
        self._ib.execDetailsEvent += self._handle_exec_details
        self._ib.pnlEvent += self._handle_pnl
        # updatePortfolioEvent giver marketPrice/marketValue pr position.
        # positionEvent (uden market data) bruges ikke længere; reqAccountUpdates
        # leverer PortfolioItem snapshots der dækker samme felter plus mere.
        self._ib.updatePortfolioEvent += self._handle_portfolio_item
        self._ib.accountValueEvent += self._handle_account_value
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
                self._pnl_received.clear()
                if self._cfg.ibkr_account:
                    self._ib.reqPnL(self._cfg.ibkr_account)
                    # ib_insync auto-subscriber til account updates ved connect,
                    # men vi filtrerer eksplicit til vores konto her så
                    # updatePortfolio + updateAccountValue events kun kommer
                    # for den ene konto vi følger. Synkrone reqAccountUpdates
                    # forsøger run_until_complete på den allerede kørende
                    # event loop, brug Async-varianten fra async kontekst.
                    await self._ib.reqAccountUpdatesAsync(self._cfg.ibkr_account)

                # Markér at initial pnl + positions snapshot er publiceret
                # så risk-gateway kan åbne for ordrer. Kører bevidst FØR
                # marketdata subscribe så cold-start latency ikke afhænger
                # af antal symboler i universet.
                await self._emit_snapshot_complete()

                # Abonnér på realtime markedsdata for det konfigurerede univers
                if self._cfg.universe_list:
                    await self.subscribe_marketdata(self._cfg.universe_list)

                # Subscribe to realtime market data for the configured universe
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
        log.info("ibkr_gateway.fill", symbol=symbol,
                 side=msg.side, qty=msg.quantity, price=msg.price)

    async def _handle_pnl(self, pnl: ibi.PnL) -> None:
        account = pnl.account
        msg = PnLSnapshot(
            account=account,
            daily_pnl=pnl.dailyPnL or 0.0,
            unrealized_pnl=pnl.unrealizedPnL or 0.0,
            realized_pnl=pnl.realizedPnL or 0.0,
            net_liquidation=self._latest_net_liquidation,
        )
        await self._on_event(subjects.pnl(account), msg.model_dump_json().encode())
        self._pnl_received.set()

    async def _emit_snapshot_complete(self) -> None:
        """Vent kort på første streaming pnl, syntetisér ellers et nul-snapshot,
        og publicér så SNAPSHOT_COMPLETE.

        Risk-gateway gater /orders indtil denne besked ses, så pre-trade checks
        (daily loss, position limit) aldrig kører mod tom state efter cold start
        eller adapter reconnect.
        """
        account = self._cfg.ibkr_account or ""
        if account:
            try:
                await asyncio.wait_for(
                    self._pnl_received.wait(),
                    timeout=self.SNAPSHOT_PNL_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                # TWS leverede ikke pnl i tide. Publicér et syntetisk nul-snapshot
                # så downstream konsumere kan initialisere; den næste rigtige
                # pnlEvent overskriver det.
                log.warning(
                    "ibkr_gateway.snapshot_pnl_timeout",
                    account=account,
                    timeout_s=self.SNAPSHOT_PNL_TIMEOUT_S,
                )
                synthetic = PnLSnapshot(
                    account=account,
                    daily_pnl=0.0,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0,
                    net_liquidation=self._latest_net_liquidation,
                )
                await self._on_event(
                    subjects.pnl(account),
                    synthetic.model_dump_json().encode(),
                )

        positions_count = (
            len(self._ib.portfolio(account)) if account else 0
        )
        msg = SnapshotComplete(account=account, positions_count=positions_count)
        await self._on_event(
            subjects.SNAPSHOT_COMPLETE, msg.model_dump_json().encode()
        )
        log.info(
            "ibkr_gateway.snapshot_complete",
            account=account,
            positions=positions_count,
        )

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

    async def _handle_portfolio_item(self, item: ibi.PortfolioItem) -> None:
        # PortfolioItem leverer både position og market data i samme event,
        # så risk-monitor kan beregne gross exposure korrekt. Kun konto vi har
        # konfigureret accepteres, ib_insync videresender også events for
        # andre konti hvis forbindelsen abonnerer på flere.
        account = item.account
        if self._cfg.ibkr_account and account != self._cfg.ibkr_account:
            return
        symbol = item.contract.symbol
        msg = PositionSnapshot(
            account=account,
            symbol=symbol,
            sec_type=item.contract.secType,
            avg_cost=item.averageCost,
            position=item.position,
            market_price=_clean(item.marketPrice),
            market_value=_clean(item.marketValue),
        )
        await self._on_event(subjects.positions(account, symbol), msg.model_dump_json().encode())

    async def _handle_account_value(self, value: ibi.AccountValue) -> None:
        # NetLiquidation rapporteres pr currency; tag den i kontoens base
        # currency (BASE) eller den eneste tilgængelige. Værdien cachet og
        # tilføjes næste PnLSnapshot, så risk-monitor får HWM input uden at
        # ændre on the wire subject layout.
        if value.tag != "NetLiquidation":
            return
        if self._cfg.ibkr_account and value.account != self._cfg.ibkr_account:
            return
        nl = _clean(value.value)
        if nl is None:
            return
        self._latest_net_liquidation = nl

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
