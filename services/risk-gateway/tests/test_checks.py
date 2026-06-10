"""Tests for CheckEngine."""

import pytest
from risk_gateway.checks import CheckEngine, RiskRejection
from risk_gateway.config import Settings
from risk_gateway.models import OrderRequest, Side


@pytest.fixture
def settings():
    return Settings(
        STRATEGY_LIMITS_JSON='{"hello": {"maxOrderNotional": 1000, "maxDailyLoss": 200, "maxPosition": 10, "maxOrdersPerSecond": 5}}',
        RESTRICTED_SYMBOLS="GME,AMC",
        MAX_ORDERS_PER_SECOND=100,
    )


@pytest.fixture
def engine(settings):
    return CheckEngine(settings)


def make_order(**kwargs):
    defaults = dict(
        strategy="hello", client_id=11,
        idempotency_key="key-1",
        symbol="AAPL", side=Side.BUY, quantity=1.0,
    )
    defaults.update(kwargs)
    return OrderRequest(**defaults)


class TestCheckEngine:
    def test_clean_order_passes(self, engine):
        engine.check(make_order())  # should not raise

    def test_restricted_symbol(self, engine):
        with pytest.raises(RiskRejection, match="restricted"):
            engine.check(make_order(symbol="GME"))

    def test_fat_finger(self, engine):
        engine.last_prices["MSFT"] = 100.0
        with pytest.raises(RiskRejection, match="Fat-finger"):
            engine.check(make_order(
                symbol="MSFT", limit_price=200.0, idempotency_key="k2"))

    def test_fat_finger_no_reference_passes(self, engine):
        # No last price → skip fat-finger check
        engine.check(make_order(
            symbol="NVDA", limit_price=999.0, idempotency_key="k3"))

    def test_notional_breach(self, engine):
        engine.last_prices["AAPL"] = 200.0
        with pytest.raises(RiskRejection, match="notional"):
            engine.check(make_order(
                quantity=10, limit_price=200.0, idempotency_key="k4"))

    def test_daily_loss_breach(self, engine):
        engine.strategy_daily_pnl["hello"] = -300.0
        with pytest.raises(RiskRejection, match="daily"):
            engine.check(make_order(idempotency_key="k5"))

    def test_duplicate_idempotency_key(self, engine):
        engine.check(make_order(idempotency_key="dup-1"))
        with pytest.raises(RiskRejection, match="Duplicate"):
            engine.check(make_order(idempotency_key="dup-1"))

    def test_halt_blocks_all_orders(self, engine):
        engine.halted = True
        engine.halt_reason = "test halt"
        with pytest.raises(RiskRejection, match="halted"):
            engine.check(make_order(idempotency_key="k6"))

    def test_position_limit_breach(self, engine):
        engine.strategy_positions["hello"] = {"AAPL": 10.0}
        with pytest.raises(RiskRejection, match="exceeds limit"):
            engine.check(make_order(quantity=1, idempotency_key="k7"))

    def test_position_limit_allows_within_cap(self, engine):
        engine.strategy_positions["hello"] = {"AAPL": 9.0}
        engine.check(make_order(quantity=1, idempotency_key="k8"))
