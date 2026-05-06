"""Wire-format message models (JSON over NATS).

All models use Pydantic v2. Strategies, the risk-monitor, and the
dashboard must use the same schemas — this file is the single source of
truth.  In a multi-language environment, generate schemas with:

    python -c "from ibkr_adapter.models import *; import json; \
        print(json.dumps(OrderCommand.model_json_schema(), indent=2))"
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Shared                                                                       #
# --------------------------------------------------------------------------- #

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MKT = "MKT"
    LMT = "LMT"
    STP = "STP"
    STP_LMT = "STP LMT"


class SecType(str, Enum):
    STK = "STK"
    FUT = "FUT"
    OPT = "OPT"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"


# --------------------------------------------------------------------------- #
# Inbound: orders.<strategy>.<symbol>                                          #
# --------------------------------------------------------------------------- #

class OrderCommand(BaseModel):
    """Published by a strategy pod to request a new order."""

    strategy: str = Field(..., description="Strategy name (kebab-case)")
    client_id: int = Field(..., ge=1, le=32767)
    idempotency_key: str = Field(...,
                                 description="UUID; duplicate detection in Risk Gateway")

    symbol: str
    sec_type: SecType = SecType.STK
    exchange: str = "SMART"
    currency: str = "USD"
    side: Side
    order_type: OrderType = OrderType.MKT
    quantity: float = Field(..., gt=0)
    limit_price: float | None = None
    stop_price: float | None = None

    timestamp: datetime = Field(default_factory=_utcnow)

    @field_validator("symbol")
    @classmethod
    def symbol_upper(cls, v: str) -> str:
        return v.upper()


# --------------------------------------------------------------------------- #
# Outbound: fills.<account>.<symbol>                                           #
# --------------------------------------------------------------------------- #

class Fill(BaseModel):
    """Published when TWS reports an execution (execDetails callback)."""

    account: str
    symbol: str
    sec_type: str
    exchange: str
    side: Side
    quantity: float
    price: float
    commission: float | None = None
    perm_id: int
    exec_id: str
    order_ref: str = ""
    timestamp: datetime = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Outbound: pnl.<account>                                                      #
# --------------------------------------------------------------------------- #

class PnLSnapshot(BaseModel):
    """Published on every PnL update from TWS (pnlSingle / pnl callbacks)."""

    account: str
    daily_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    net_liquidation: float | None = None
    timestamp: datetime = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Outbound: positions.<account>.<symbol>                                       #
# --------------------------------------------------------------------------- #

class PositionSnapshot(BaseModel):
    account: str
    symbol: str
    sec_type: str
    avg_cost: float
    position: float
    market_price: float | None = None
    market_value: float | None = None
    timestamp: datetime = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Outbound: marketdata.<feed>.<symbol>                                         #
# --------------------------------------------------------------------------- #

class Bar(BaseModel):
    feed: Literal["realtime", "historical"]
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    bar_time: datetime
    timestamp: datetime = Field(default_factory=_utcnow)


class Tick(BaseModel):
    feed: Literal["top"] = "top"
    symbol: str
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    timestamp: datetime = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Outbound: risk.adapter.*                                                     #
# --------------------------------------------------------------------------- #

class AdapterHeartbeat(BaseModel):
    status: Literal["connected", "connecting"] = "connected"
    ibgw_host: str
    ibgw_port: int
    client_id: int
    timestamp: datetime = Field(default_factory=_utcnow)


class AdapterDisconnected(BaseModel):
    ibgw_host: str
    ibgw_port: int
    reason: str = ""
    timestamp: datetime = Field(default_factory=_utcnow)
