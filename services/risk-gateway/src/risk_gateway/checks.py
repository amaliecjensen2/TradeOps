"""Pre trade risikochecks.

CheckEngine kører en pipeline af checks mod en indkommende OrderRequest.
Hvert check rejser RiskRejection ved overtrædelse; ellers passerer det stille.
Pipelinen er fail fast: første afvisning vinder.

Checks (i rækkefølge):
  1. Begrænset symbol
  2. Fat finger prisbånd (limit/stop pris ±20% af sidste kendte pris)
  3. Per strategi max ordrenotional
  4. Per strategi max dagligt tab (læst fra NATS state)
  5. Per strategi max positionsstørrelse
  6. Per strategi rate limit
  7. Global max ordrer pr sekund
  8. Idempotens (duplikatnøgle detektion)
  9. Halt flag (risk monitor har udløst circuit breakeren)
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from risk_gateway.config import Settings
from risk_gateway.logging_setup import get_logger
from risk_gateway.models import OrderRequest

log = get_logger(__name__)

FAT_FINGER_BAND = 0.20   # ±20% fra sidste kendte pris


class RiskRejection(Exception):
    """Rejses når et pre trade check fejler."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class CheckEngine:
    def __init__(self, settings: Settings) -> None:
        self._cfg = settings
        self.strategy_limits = settings.strategy_limits
        self._restricted = settings.restricted_symbols_set

        # State holdt i hukommelsen (tilstrækkelig for single replica eller sticky sessions)
        self._idempotency_cache: dict[str, float] = {}   # nøgle til tidsstempel
        self._idempotency_ttl = 300.0                    # 5 minutter

        # Per strategi ordre rate limiting (sliding window)
        self._strategy_order_times: dict[str, deque] = defaultdict(deque)

        # Global rate limiting (sliding window)
        self._global_order_times: deque = deque()

        # Per strategi dagligt tab tracking (opdateret af NATS listener)
        self.strategy_daily_pnl: dict[str, float] = {}

        # Per strategi nuværende position (opdateret af NATS listener)
        self.strategy_positions: dict[str, dict[str, float]] = {}

        # Sidste kendte priser pr symbol (til fat finger check)
        self.last_prices: dict[str, float] = {}

        # Globalt halt flag (sættes af NATS når risk monitor udløser)
        self.halted: bool = False
        self.halt_reason: str = ""

    def check(self, req: OrderRequest) -> None:
        """Kør alle checks. Rejser RiskRejection ved første fejl."""
        self._check_halt()
        self._check_restricted_symbol(req)
        self._check_fat_finger(req)
        self._check_order_notional(req)
        self._check_daily_loss(req)
        self._check_position_limit(req)
        self._check_strategy_rate(req)
        self._check_global_rate()
        self._check_idempotency(req)

    # Individuelle checks

    def _check_halt(self) -> None:
        if self.halted:
            raise RiskRejection(f"System halted: {self.halt_reason}")

    def _check_restricted_symbol(self, req: OrderRequest) -> None:
        if req.symbol in self._restricted:
            raise RiskRejection(f"Symbol {req.symbol} is restricted")

    def _check_fat_finger(self, req: OrderRequest) -> None:
        if req.limit_price is None:
            return   # markedsordrer, intet fat finger check
        last = self.last_prices.get(req.symbol)
        if last is None or last <= 0:
            return   # ingen referencepris endnu
        deviation = abs(req.limit_price - last) / last
        if deviation > FAT_FINGER_BAND:
            raise RiskRejection(
                f"Fat-finger: limit {req.limit_price} deviates "
                f"{deviation:.1%} from last {last} (max {FAT_FINGER_BAND:.0%})"
            )

    def _check_order_notional(self, req: OrderRequest) -> None:
        limits = self.strategy_limits.get(req.strategy, {})
        max_notional = limits.get("maxOrderNotional")
        if max_notional is None:
            return
        # Brug limit pris hvis tilgængelig, ellers sidste kendte pris som estimat
        ref_price = req.limit_price or self.last_prices.get(req.symbol, 0)
        notional = req.quantity * ref_price
        if notional > max_notional:
            raise RiskRejection(
                f"Order notional ${notional:,.0f} exceeds strategy limit ${max_notional:,.0f}"
            )

    def _check_daily_loss(self, req: OrderRequest) -> None:
        limits = self.strategy_limits.get(req.strategy, {})
        max_daily_loss = limits.get("maxDailyLoss")
        if max_daily_loss is None:
            return
        current_loss = self.strategy_daily_pnl.get(req.strategy, 0.0)
        if current_loss < -abs(max_daily_loss):
            raise RiskRejection(
                f"Strategy {req.strategy} daily P&L ${current_loss:,.2f} "
                f"below limit -${abs(max_daily_loss):,.2f}"
            )

    def _check_position_limit(self, req: OrderRequest) -> None:
        limits = self.strategy_limits.get(req.strategy, {})
        max_position = limits.get("maxPosition")
        if max_position is None:
            return
        pos = self.strategy_positions.get(
            req.strategy, {}).get(req.symbol, 0.0)
        projected = pos + (req.quantity if req.side ==
                           "BUY" else -req.quantity)
        if abs(projected) > max_position:
            raise RiskRejection(
                f"Projected position {projected} in {req.symbol} "
                f"exceeds limit {max_position}"
            )

    def _check_strategy_rate(self, req: OrderRequest) -> None:
        limits = self.strategy_limits.get(req.strategy, {})
        max_rate = limits.get("maxOrdersPerSecond", 10)
        now = time.monotonic()
        window = self._strategy_order_times[req.strategy]
        # Smid entries ud der er ældre end 1 sekund
        while window and now - window[0] > 1.0:
            window.popleft()
        if len(window) >= max_rate:
            raise RiskRejection(
                f"Strategy {req.strategy} rate limit {max_rate} orders/s exceeded"
            )
        window.append(now)

    def _check_global_rate(self) -> None:
        now = time.monotonic()
        while self._global_order_times and now - self._global_order_times[0] > 1.0:
            self._global_order_times.popleft()
        if len(self._global_order_times) >= self._cfg.max_orders_per_second:
            raise RiskRejection(
                f"Global rate limit {self._cfg.max_orders_per_second} orders/s exceeded"
            )
        self._global_order_times.append(now)

    def _check_idempotency(self, req: OrderRequest) -> None:
        now = time.monotonic()
        # Ryd udløbne nøgler
        expired = [k for k, t in self._idempotency_cache.items()
                   if now - t > self._idempotency_ttl]
        for k in expired:
            del self._idempotency_cache[k]

        if req.idempotency_key in self._idempotency_cache:
            raise RiskRejection(
                f"Duplicate order: idempotency_key {req.idempotency_key} already seen"
            )
        self._idempotency_cache[req.idempotency_key] = now
