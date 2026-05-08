"""Database access layer — asyncpg against TimescaleDB.

All queries use parameterised statements ($1, $2, ...) — never string
interpolation — to prevent SQL injection.
"""

from __future__ import annotations

import asyncpg

from trader_api.config import Settings
from trader_api.logging_setup import get_logger

log = get_logger(__name__)


class Database:
    def __init__(self, settings: Settings) -> None:
        self._dsn = settings.pg_dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        log.info("db.connected", host=self._dsn.split("@")[-1])

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    # ------------------------------------------------------------------ #
    # Positions                                                            #
    # ------------------------------------------------------------------ #

    async def get_positions(self, account: str) -> list[dict]:
        assert self._pool
        rows = await self._pool.fetch(
            """
            SELECT DISTINCT ON (symbol)
                account, symbol, sec_type, avg_cost, position,
                market_price, market_value, timestamp
            FROM positions_snapshot
            WHERE account = $1
            ORDER BY symbol, timestamp DESC
            """,
            account,
        )
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # PnL                                                                  #
    # ------------------------------------------------------------------ #

    async def get_pnl_history(self, account: str, limit: int = 200) -> list[dict]:
        assert self._pool
        rows = await self._pool.fetch(
            """
            SELECT timestamp, daily_pnl, unrealized_pnl, realized_pnl, net_liquidation
            FROM pnl_ticks
            WHERE account = $1
            ORDER BY timestamp DESC
            LIMIT $2
            """,
            account,
            limit,
        )
        return [dict(r) for r in rows]

    async def get_latest_pnl(self, account: str) -> dict | None:
        assert self._pool
        row = await self._pool.fetchrow(
            """
            SELECT timestamp, daily_pnl, unrealized_pnl, realized_pnl, net_liquidation
            FROM pnl_ticks
            WHERE account = $1
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            account,
        )
        return dict(row) if row else None

    # ------------------------------------------------------------------ #
    # Orders / fills                                                       #
    # ------------------------------------------------------------------ #

    async def get_fills(self, account: str, limit: int = 100) -> list[dict]:
        assert self._pool
        rows = await self._pool.fetch(
            """
            SELECT timestamp, account, symbol, sec_type, side,
                   quantity, price, commission, exec_id, order_ref
            FROM fills
            WHERE account = $1
            ORDER BY timestamp DESC
            LIMIT $2
            """,
            account,
            limit,
        )
        return [dict(r) for r in rows]

    async def get_order_events(self, limit: int = 100) -> list[dict]:
        assert self._pool
        rows = await self._pool.fetch(
            """
            SELECT timestamp, strategy, symbol, side, quantity,
                   order_type, status, reject_reason
            FROM order_events
            ORDER BY timestamp DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]
