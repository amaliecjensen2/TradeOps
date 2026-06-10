"""Buy and hold NVDA strategi.

Signal logik:
  Ved den første bar der modtages, køb trade_qty shares af NVDA (markedsordre).
  Hold for evigt, sælger aldrig.

Dette er et simpelt eksempel der altid holder én NVDA position.
"""

from __future__ import annotations

from strategy_nvidia.base import BaseStrategy
from strategy_nvidia.logging_setup import get_logger

log = get_logger(__name__)


class NvidiaStrategy(BaseStrategy):
    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._bought = False  # kun køb én gang

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
