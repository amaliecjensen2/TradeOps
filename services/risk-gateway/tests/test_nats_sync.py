"""Tests for NATSStateSync, fokuseret på at position-snapshots fra
positions.<account>.<symbol> faktisk lander under strategi-navn i
CheckEngine.strategy_positions, så _check_position_limit håndhæver maxPosition.
"""

import json
from types import SimpleNamespace

import pytest

from risk_gateway.checks import CheckEngine
from risk_gateway.config import Settings
from risk_gateway.nats_sync import NATSStateSync


@pytest.fixture
def settings():
    return Settings(
        STRATEGY_LIMITS_JSON='{"hello": {"maxPosition": 10}, "nvidia": {"maxPosition": 4}}',
    )


@pytest.fixture
def engine(settings):
    return CheckEngine(settings)


@pytest.fixture
def sync(settings, engine):
    return NATSStateSync(settings, engine)


@pytest.mark.asyncio
async def test_position_snapshot_mirrored_to_all_strategies(sync, engine):
    msg = SimpleNamespace(data=json.dumps({
        "account": "DUQ568769", "symbol": "NVDA", "position": 19.0,
    }).encode())

    await sync._on_position(msg)

    assert engine.strategy_positions["nvidia"]["NVDA"] == 19.0
    assert engine.strategy_positions["hello"]["NVDA"] == 19.0


@pytest.mark.asyncio
async def test_position_snapshot_overwrites_previous(sync, engine):
    engine.strategy_positions["nvidia"] = {"NVDA": 0.0}
    msg = SimpleNamespace(data=json.dumps({
        "account": "DUQ568769", "symbol": "NVDA", "position": 19.0,
    }).encode())

    await sync._on_position(msg)

    assert engine.strategy_positions["nvidia"]["NVDA"] == 19.0
