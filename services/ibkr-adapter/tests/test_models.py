"""Unit tests for IBKRGateway subject hjælpere og model validering."""

import pytest

from ibkr_adapter import subjects
from ibkr_adapter.models import OrderCommand, Side, OrderType, SecType


class TestSubjects:
    def test_fills_subject(self):
        assert subjects.fills("U12345", "AAPL") == "fills.U12345.AAPL"

    def test_pnl_subject(self):
        assert subjects.pnl("U12345") == "pnl.U12345"

    def test_positions_subject(self):
        assert subjects.positions("U12345", "MSFT") == "positions.U12345.MSFT"

    def test_marketdata_subject(self):
        assert subjects.marketdata(
            "realtime", "SPY") == "marketdata.realtime.SPY"

    def test_snapshot_complete_subject(self):
        assert subjects.SNAPSHOT_COMPLETE == "risk.adapter.snapshot_complete"


class TestOrderCommand:
    def test_valid_order(self):
        cmd = OrderCommand(
            strategy="hello",
            client_id=11,
            idempotency_key="abc-123",
            symbol="aapl",  # skal gøres til store bogstaver
            side=Side.BUY,
            quantity=1.0,
        )
        assert cmd.symbol == "AAPL"
        assert cmd.order_type == OrderType.MKT
        assert cmd.sec_type == SecType.STK

    def test_symbol_uppercased(self):
        cmd = OrderCommand(
            strategy="s",
            client_id=1,
            idempotency_key="x",
            symbol="tsla",
            side=Side.SELL,
            quantity=10,
        )
        assert cmd.symbol == "TSLA"

    def test_invalid_quantity(self):
        with pytest.raises(Exception):
            OrderCommand(
                strategy="s",
                client_id=1,
                idempotency_key="x",
                symbol="AAPL",
                side=Side.BUY,
                quantity=0,  # skal være > 0
            )

    def test_invalid_client_id(self):
        from ibkr_adapter.config import Settings
        with pytest.raises(Exception):
            Settings(IBKR_CLIENT_ID=0)
