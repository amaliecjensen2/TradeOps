"""Pydantic modeller for risk gateway HTTP APIet."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderRequest(BaseModel):
    """POST /orders, sendt af en strategi pod."""
    strategy: str
    client_id: int = Field(..., ge=1, le=32767)
    idempotency_key: str
    symbol: str
    exchange: str = "SMART"
    currency: str = "USD"
    sec_type: str = "STK"
    side: Side
    order_type: str = "MKT"
    quantity: float = Field(..., gt=0)
    limit_price: float | None = None
    stop_price: float | None = None
    timestamp: datetime = Field(default_factory=_utcnow)

    @field_validator("symbol")
    @classmethod
    def upper_symbol(cls, v: str) -> str:
        return v.upper()


class OrderAccepted(BaseModel):
    status: Literal["accepted"] = "accepted"
    idempotency_key: str
    timestamp: datetime = Field(default_factory=_utcnow)


class OrderRejected(BaseModel):
    status: Literal["rejected"] = "rejected"
    reason: str
    idempotency_key: str
    timestamp: datetime = Field(default_factory=_utcnow)
