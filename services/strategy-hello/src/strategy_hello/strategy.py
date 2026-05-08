"""Moving Average Crossover strategy.

Signal logic:
  - Maintain a rolling buffer of closing prices per symbol
  - BUY  when fast MA crosses ABOVE slow MA (golden cross)
  - SELL when fast MA crosses BELOW slow MA (death cross)
  - Only one position per symbol at a time (flat → long → flat)

This is an intentionally simple example to validate the full pipeline.
Replace with your own logic in a new strategy service.
"""

from __future__ import annotations

from collections import defaultdict, deque

from strategy_hello.base import BaseStrategy
from strategy_hello.config import get_settings
from strategy_hello.logging_setup import get_logger

log = get_logger(__name__)


def _simple_moving_average(prices: deque, period: int) -> float | None:
    if len(prices) < period:
        return None
    return sum(list(prices)[-period:]) / period


class HelloStrategy(BaseStrategy):
    def __init__(self, settings) -> None:
        super().__init__(settings)
        # Rolling close-price buffer per symbol (max slow_period + 1 bars)
        buf_size = settings.slow_period + 1
        self._prices: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=buf_size))
        # Track whether we currently hold a position per symbol
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
            # Not enough bars yet
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

        # Golden cross: fast MA crosses above slow MA → BUY if flat
        if fast_ma > slow_ma and current_pos <= 0:
            log.info("strategy.golden_cross", symbol=symbol,
                     fast_ma=fast_ma, slow_ma=slow_ma)
            # Close short first if any
            if current_pos < 0:
                filled = await self.buy(symbol, abs(current_pos))
                if filled:
                    self._position[symbol] = 0.0

            filled = await self.buy(symbol, self._cfg.trade_qty)
            if filled:
                self._position[symbol] = self._cfg.trade_qty

        # Death cross: fast MA crosses below slow MA → SELL if long
        elif fast_ma < slow_ma and current_pos >= 0:
            log.info("strategy.death_cross", symbol=symbol,
                     fast_ma=fast_ma, slow_ma=slow_ma)
            if current_pos > 0:
                filled = await self.sell(symbol, current_pos)
                if filled:
                    self._position[symbol] = 0.0
