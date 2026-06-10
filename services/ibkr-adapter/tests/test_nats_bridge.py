"""Tests for NATSBridge ordrebeskedhåndtering."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ibkr_adapter.nats_bridge import NATSBridge
from ibkr_adapter.config import Settings


@pytest.fixture
def settings():
    return Settings(
        IBGW_HOST="localhost",
        IBGW_PORT=4002,
        IBKR_CLIENT_ID=1,
        NATS_URL="nats://localhost:4222",
        IBKR_ACCOUNT="U12345",
    )


@pytest.fixture
def bridge(settings):
    return NATSBridge(settings)


class TestNATSBridgeOrderHandling:
    async def test_drops_order_when_not_connected(self, bridge):
        mock_gateway = MagicMock()
        mock_gateway.is_connected = False
        bridge.set_gateway(mock_gateway)

        msg = MagicMock()
        msg.data = json.dumps({
            "strategy": "hello",
            "client_id": 11,
            "idempotency_key": "key-1",
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 1.0,
        }).encode()

        await bridge._handle_order_msg(msg)
        mock_gateway.place_order.assert_not_called()

    async def test_rejects_invalid_json(self, bridge):
        mock_gateway = MagicMock()
        mock_gateway.is_connected = True
        bridge.set_gateway(mock_gateway)

        msg = MagicMock()
        msg.data = b"not-json"

        # Skal ikke kaste, bare logge og tælle
        await bridge._handle_order_msg(msg)
        mock_gateway.place_order.assert_not_called()

    async def test_places_order_when_connected(self, bridge):
        mock_gateway = MagicMock()
        mock_gateway.is_connected = True
        mock_gateway.place_order = AsyncMock(return_value=42)
        bridge.set_gateway(mock_gateway)

        msg = MagicMock()
        msg.data = json.dumps({
            "strategy": "hello",
            "client_id": 11,
            "idempotency_key": "key-2",
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 5.0,
        }).encode()

        await bridge._handle_order_msg(msg)
        mock_gateway.place_order.assert_called_once()
