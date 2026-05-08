"""Tests for MA crossover signal logic."""
from collections import deque
import pytest
from strategy_hello.strategy import _simple_moving_average, HelloStrategy
from strategy_hello.config import Settings


def test_sma_needs_enough_bars():
    prices = deque([1.0, 2.0, 3.0], maxlen=10)
    assert _simple_moving_average(prices, 5) is None


def test_sma_correct():
    prices = deque([10.0, 20.0, 30.0, 40.0, 50.0], maxlen=10)
    result = _simple_moving_average(prices, 5)
    assert result == 30.0


def test_sma_uses_last_n():
    prices = deque([1.0, 2.0, 3.0, 100.0, 200.0], maxlen=10)
    result = _simple_moving_average(prices, 3)
    assert result == pytest.approx((3.0 + 100.0 + 200.0) / 3)


class TestHelloStrategy:
    @pytest.fixture
    def strategy(self):
        settings = Settings(
            STRATEGY_NAME="hello",
            IBKR_CLIENT_ID=11,
            FAST_PERIOD=2,
            SLOW_PERIOD=3,
            TRADE_QTY=1.0,
            UNIVERSE=["AAPL"],
        )
        return HelloStrategy(settings)

    async def test_no_signal_during_warmup(self, strategy, mocker):
        mock_buy = mocker.patch.object(strategy, "buy")
        mock_sell = mocker.patch.object(strategy, "sell")
        await strategy.on_bar({"symbol": "AAPL", "close": 100.0})
        mock_buy.assert_not_called()
        mock_sell.assert_not_called()

    async def test_golden_cross_triggers_buy(self, strategy, mocker):
        mock_buy = mocker.patch.object(strategy, "buy", return_value=True)
        # Feed bars: slow (3 bars needed), fast (2 bars)
        # Prices trending up → fast MA > slow MA
        for price in [90.0, 95.0, 110.0]:
            await strategy.on_bar({"symbol": "AAPL", "close": price})
        mock_buy.assert_called()

    async def test_death_cross_triggers_sell(self, strategy, mocker):
        mock_buy = mocker.patch.object(strategy, "buy", return_value=True)
        mock_sell = mocker.patch.object(strategy, "sell", return_value=True)

        # First create a long position via golden cross
        for price in [90.0, 95.0, 110.0]:
            await strategy.on_bar({"symbol": "AAPL", "close": price})

        # Now prices trend down → death cross
        for price in [105.0, 95.0, 80.0]:
            await strategy.on_bar({"symbol": "AAPL", "close": price})

        mock_sell.assert_called()
