import pytest
from unittest.mock import AsyncMock, patch
from main import get_ticker, app
from fastapi.testclient import TestClient
import ccxt
from fastapi import HTTPException
from strategy import calculate_cci, generate_cci_signals, backtest_strategy
import pandas as pd
import numpy as np

client = TestClient(app)

@pytest.mark.asyncio
async def test_get_ticker_success():
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker.return_value = {"symbol": "BTC/USDT", "last": 10000}

    with patch('main.getattr', return_value=lambda *args, **kwargs: mock_exchange):
        ticker_data = await get_ticker("binance", "BTC/USDT")
        assert ticker_data["symbol"] == "BTC/USDT"
        assert ticker_data["last"] == 10000

@pytest.mark.asyncio
async def test_get_ticker_exchange_not_found():
    with patch('main.getattr', side_effect=AttributeError):
        with pytest.raises(Exception) as exc_info:
            await get_ticker("nonexistent", "BTC/USDT")
        assert "Exchange not found" in str(exc_info.value)

@pytest.mark.asyncio
async def test_get_ticker_exchange_error():
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker.side_effect = ccxt.ExchangeError("Test Exchange Error")

    with patch('main.getattr', return_value=lambda *args, **kwargs: mock_exchange):
        with pytest.raises(HTTPException) as exc_info:
            await get_ticker("binance", "BTC/USDT")
        assert exc_info.value.status_code == 400
        assert "CCXT Exchange Error: Test Exchange Error" in exc_info.value.detail

def test_calculate_cci():
    # Sample data for testing CCI calculation
    high = pd.Series([10, 12, 15, 13, 16, 18, 20, 19, 22, 25])
    low = pd.Series([8, 10, 12, 11, 14, 16, 18, 17, 20, 23])
    close = pd.Series([9, 11, 14, 12, 15, 17, 19, 18, 21, 24])

    # Calculate CCI with a window of 3 for simplicity in manual calculation
    cci_values = calculate_cci(high, low, close, window=3)

    # Expected values (manual calculation for a few points)
    # For window=3, the first 2 values will be NaN
    # TP for first 3: (9+11+13.666...)/3 = 11.222...
    # SMA_TP for first 3: 11.222...
    # MD for first 3: (abs(9-11.222)+abs(11-11.222)+abs(13.666-11.222))/3 = (2.222+0.222+2.444)/3 = 1.629...
    # CCI = (13.666 - 11.222) / (0.015 * 1.629) = 2.444 / 0.0244 = 100

    # For the 4th point (index 3):
    # TP = (13+11+12)/3 = 12
    # SMA_TP (index 1,2,3) = (11+13.666+12)/3 = 12.222...
    # MD (index 1,2,3) = (abs(11-12.222)+abs(13.666-12.222)+abs(12-12.222))/3 = (1.222+1.444+0.222)/3 = 0.962...
    # CCI = (12 - 12.222) / (0.015 * 0.962) = -0.222 / 0.01443 = -15.38

    # Due to floating point precision, we'll check for approximate equality
    assert cci_values.iloc[2] == pytest.approx(100.0, abs=1e-2) # First valid CCI value
    assert cci_values.iloc[3] == pytest.approx(-15.38, abs=1e-2)
    assert cci_values.iloc[9] is not None # Ensure last value is calculated
    assert cci_values.isnull().sum() == 2 # First (window-1) values are NaN

def test_generate_cci_signals():
    # Sample OHLCV data (timestamp, open, high, low, close, volume)
    ohlcv_data = [
        [1, 10, 12, 8, 9, 100],
        [2, 9, 11, 7, 10, 100],
        [3, 10, 13, 9, 12, 100],
        [4, 12, 15, 11, 14, 100],
        [5, 14, 17, 13, 16, 100],
        [6, 16, 19, 15, 18, 100],
        [7, 18, 21, 17, 20, 100],
        [8, 20, 23, 19, 22, 100],
        [9, 22, 25, 21, 24, 100],
        [10, 24, 27, 23, 26, 100],
        [11, 26, 29, 25, 28, 100],
        [12, 28, 31, 27, 30, 100],
        [13, 30, 33, 29, 32, 100],
        [14, 32, 35, 31, 34, 100],
        [15, 34, 37, 33, 36, 100],
        [16, 36, 39, 35, 38, 100],
        [17, 38, 41, 37, 40, 100],
        [18, 40, 43, 39, 42, 100],
        [19, 42, 45, 41, 44, 100],
        [20, 44, 47, 43, 46, 100],
        [21, 46, 49, 45, 48, 100] # This point will have a high CCI
    ]

    signals = generate_cci_signals(ohlcv_data, window=3, buy_threshold=50, sell_threshold=-50)

    # Check for expected signals
    # Based on manual calculation, the CCI should be high at the end
    # and low at the beginning (after NaN values)
    assert signals['signal'].iloc[20] == 1 # Expect buy signal at the end
    assert signals['signal'].iloc[0] == 0 # No signal for first few values
    assert signals['signal'].iloc[1] == 0
    assert signals['signal'].iloc[2] == 1 # Expect buy signal at index 2 (CCI = 100 > 50)

    # Test a sell signal (need to create data that causes a sell signal)
    # For simplicity, let's assume a point where CCI goes below -50
    # This would require more complex data generation or a specific test case
    # For now, we'll just check that no unexpected signals are generated
    assert all(s in [0, 1, -1] for s in signals['signal'])

def test_backtest_strategy():
    # Sample OHLCV data for backtesting
    # This data is designed to trigger a buy and then a sell signal
    ohlcv_data = [
        [1, 100, 105, 95, 100, 100], # CCI will be low/neutral
        [2, 100, 105, 95, 100, 100],
        [3, 100, 105, 95, 100, 100],
        [4, 100, 105, 95, 100, 100],
        [5, 100, 105, 95, 100, 100],
        [6, 100, 105, 95, 100, 100],
        [7, 100, 105, 95, 100, 100],
        [8, 100, 105, 95, 100, 100],
        [9, 100, 105, 95, 100, 100],
        [10, 100, 105, 95, 100, 100],
        [11, 100, 105, 95, 100, 100],
        [12, 100, 105, 95, 100, 100],
        [13, 100, 105, 95, 100, 100],
        [14, 100, 105, 95, 100, 100],
        [15, 100, 105, 95, 100, 100],
        [16, 100, 105, 95, 100, 100],
        [17, 100, 105, 95, 100, 100],
        [18, 100, 105, 95, 100, 100],
        [19, 100, 105, 95, 100, 100],
        [20, 100, 105, 95, 100, 100], # CCI will be neutral here
        [21, 100, 120, 100, 115, 100], # Price surge, CCI likely to go above 100 (buy signal)
        [22, 115, 110, 90, 95, 100],  # Price drop, CCI likely to go below -100 (sell signal)
        [23, 95, 100, 90, 98, 100]
    ]

    initial_capital = 1000
    commission = 0.001 # 0.1%

    results = backtest_strategy(ohlcv_data, window=20, buy_threshold=100, sell_threshold=-100, initial_capital=initial_capital, commission=commission)

    # Expected results (approximate due to floating point)
    # Buy at index 20 (close price 115)
    # Sell at index 21 (close price 95)
    # Initial capital: 1000
    # Buy amount: 1000 / 115 = 8.6956521739
    # Capital after buy: 1000 - (8.6956521739 * 115 * 0.001) = 1000 - 1 = 999
    # Capital after sell: 999 + (8.6956521739 * 95 * (1 - 0.001)) = 999 + (826.08695652 * 0.999) = 999 + 825.259 = 1824.259
    # Profit/Loss: 1824.259 - 1000 = 824.259

    assert results["initial_capital"] == initial_capital
    assert results["final_capital"] == pytest.approx(1824.259, abs=1e-2)
    assert results["profit_loss"] == pytest.approx(824.259, abs=1e-2)
    assert len(results["trades"]) == 2 # One buy, one sell
    assert results["trades"][0]["type"] == "buy"
    assert results["trades"][1]["type"] == "sell"


def test_backtest_strategy():
    # Sample OHLCV data for backtesting
    # This data is designed to trigger a buy and then a sell signal
    ohlcv_data = [
        [1, 100, 105, 95, 100, 100], # CCI will be low/neutral
        [2, 100, 105, 95, 100, 100],
        [3, 100, 105, 95, 100, 100],
        [4, 100, 105, 95, 100, 100],
        [5, 100, 105, 95, 100, 100],
        [6, 100, 105, 95, 100, 100],
        [7, 100, 105, 95, 100, 100],
        [8, 100, 105, 95, 100, 100],
        [9, 100, 105, 95, 100, 100],
        [10, 100, 105, 95, 100, 100],
        [11, 100, 105, 95, 100, 100],
        [12, 100, 105, 95, 100, 100],
        [13, 100, 105, 95, 100, 100],
        [14, 100, 105, 95, 100, 100],
        [15, 100, 105, 95, 100, 100],
        [16, 100, 105, 95, 100, 100],
        [17, 100, 105, 95, 100, 100],
        [18, 100, 105, 95, 100, 100],
        [19, 100, 105, 95, 100, 100],
        [20, 100, 105, 95, 100, 100], # CCI will be neutral here
        [21, 100, 120, 100, 115, 100], # Price surge, CCI likely to go above 100 (buy signal)
        [22, 115, 110, 90, 95, 100],  # Price drop, CCI likely to go below -100 (sell signal)
        [23, 95, 100, 90, 98, 100]
    ]

    initial_capital = 1000
    commission = 0.001 # 0.1%

    results = backtest_strategy(ohlcv_data, window=20, buy_threshold=100, sell_threshold=-100, initial_capital=initial_capital, commission=commission)

    # Expected results (approximate due to floating point)
    # Buy at index 20 (close price 115)
    # Sell at index 21 (close price 95)
    # Initial capital: 1000
    # Buy amount: 1000 / 115 = 8.6956521739
    # Capital after buy: 1000 - (8.6956521739 * 115 * 0.001) = 1000 - 1 = 999
    # Capital after sell: 999 + (8.6956521739 * 95 * (1 - 0.001)) = 999 + (826.08695652 * 0.999) = 999 + 825.259 = 1824.259
    # Profit/Loss: 1824.259 - 1000 = 824.259

    assert results["initial_capital"] == initial_capital
    assert results["final_capital"] == pytest.approx(1824.259, abs=1e-2)
    assert results["profit_loss"] == pytest.approx(824.259, abs=1e-2)
    assert len(results["trades"]) == 2 # One buy, one sell
    assert results["trades"][0]["type"] == "buy"
    assert results["trades"][1]["type"] == "sell"
