"""Moving Average Crossover strategi.

Signal logik:
  Vedligehold en rullende buffer af lukkepriser pr symbol
  BUY  når hurtig MA krydser OVER langsom MA (golden cross)
  SELL når hurtig MA krydser UNDER langsom MA (death cross)
  Kun én position pr symbol ad gangen (flat til long til flat)

Dette er et bevidst simpelt eksempel til at validere hele pipelinen.
Erstat med din egen logik i en ny strategi service.
"""

from __future__ import annotations

from collections import defaultdict, deque

from strategy_hello.base import BaseStrategy
from strategy_hello.logging_setup import get_logger

log = get_logger(__name__)


def _simple_moving_average(prices: deque, period: int) -> float | None:
    if len(prices) < period:
        return None
    return sum(list(prices)[-period:]) / period


class HelloStrategy(BaseStrategy):
    def __init__(self, settings) -> None:
        super().__init__(settings)
        # Rullende lukkepris buffer pr symbol (max slow_period + 1 bars)
        buf_size = settings.slow_period + 1
        self._prices: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=buf_size))
        # Spor om vi pt holder en position pr symbol
        self._position: dict[str, float] = {}

    async def on_bar(self, bar: dict) -> None:
        symbol = bar.get("symbol", "")
        close = bar.get("close") or bar.get("last")
        if not symbol or close is None:
            return

        self._prices[symbol].append(float(close))

        fast_ma = _simple_moving_average(
            self._prices[symbol], self._cfg.fast_period)
        slow_ma = _simple_moving_average(
            self._prices[symbol], self._cfg.slow_period)

        if fast_ma is None or slow_ma is None:
            # Ikke nok bars endnu
            log.debug("strategy.warming_up",
                      symbol=symbol,
                      bars=len(self._prices[symbol]),
                      need=self._cfg.slow_period)
            return

        log.debug("strategy.signal",
                  symbol=symbol,
                  fast_ma=round(fast_ma, 4),
                  slow_ma=round(slow_ma, 4),
                  position=self._position.get(symbol, 0))

        current_pos = self._position.get(symbol, 0.0)

        # Golden cross: hurtig MA krydser over langsom MA, BUY hvis flat
        if fast_ma > slow_ma and current_pos <= 0:
            log.info("strategy.golden_cross", symbol=symbol,
                     fast_ma=fast_ma, slow_ma=slow_ma)
            # Luk short først hvis nogen
            if current_pos < 0:
                filled = await self.buy(symbol, abs(current_pos))
                if filled:
                    self._position[symbol] = 0.0

            filled = await self.buy(symbol, self._cfg.trade_qty)
            if filled:
                self._position[symbol] = self._cfg.trade_qty

        # Death cross: hurtig MA krydser under langsom MA, SELL hvis long
        elif fast_ma < slow_ma and current_pos >= 0:
            log.info("strategy.death_cross", symbol=symbol,
                     fast_ma=fast_ma, slow_ma=slow_ma)
            if current_pos > 0:
                filled = await self.sell(symbol, current_pos)
                if filled:
                    self._position[symbol] = 0.0
