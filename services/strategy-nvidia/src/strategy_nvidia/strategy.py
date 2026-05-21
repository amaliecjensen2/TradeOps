"""Buy-and-hold NVDA strategy.

Signal logic:
  - On the first bar received, buy trade_qty shares of NVDA (market order).
  - Hold forever — never sells.

This is a simple example that always holds one NVDA position.
"""

from __future__ import annotations

from strategy_nvidia.base import BaseStrategy
from strategy_nvidia.logging_setup import get_logger

log = get_logger(__name__)


class NvidiaStrategy(BaseStrategy):
    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._bought = False  # only buy once

    async def on_bar(self, bar: dict) -> None:
        if self._bought:
            return

        symbol = bar.get("symbol", "")
        if not symbol:
            return

        log.info("strategy.first_bar", symbol=symbol,
                 qty=self._cfg.trade_qty)

        filled = await self.buy(symbol, self._cfg.trade_qty)
        if filled:
            self._bought = True
            log.info("strategy.position_opened",
                     symbol=symbol, qty=self._cfg.trade_qty)
