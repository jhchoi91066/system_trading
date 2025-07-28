# Bitcoin Trading Bot

This project is a cryptocurrency trading bot that uses real-time data to make trading decisions.

## Features Implemented

### Backend (FastAPI)
- **List available exchanges:** `/exchanges` endpoint to list all supported cryptocurrency exchanges.
- **Fetch real-time data:** `/ticker/{exchange_id}/{symbol}` endpoint to fetch real-time ticker data.
- **Fetch historical OHLCV data:** `/ohlcv/{exchange_id}/{symbol}` endpoint to fetch historical candlestick data.
- **CCI Calculation:** Implemented CCI (Commodity Channel Index) calculation.
- **CCI Signal Generation:** Implemented logic to generate buy/sell signals based on CCI thresholds.
- **Backtesting Strategy:** `/backtest/{exchange_id}/{symbol}` endpoint to run backtests on historical data using the CCI strategy.

### Frontend (Next.js Dashboard)
- Displays a list of available exchanges.
- Displays real-time ticker data for a selected symbol (e.g., BTC/USDT).
- Provides a UI to configure and run backtests with various parameters (exchange, symbol, timeframe, CCI window, buy/sell thresholds, initial capital, commission).
- Displays detailed backtest results including initial/final capital, profit/loss, and a list of executed trades.

## How to Run the Application

To run this application, you will need two separate terminal windows.

### 1. Start the Backend Server

In the first terminal, navigate to the `backend` directory and start the FastAPI server:

```bash
cd /Users/jinhochoi/Desktop/개발/bitcoin-trading-bot/backend
source ../venv/bin/activate
uvicorn main:app --reload
```

Leave this terminal running. The server will be accessible at `http://127.0.0.1:8000`.

### 2. Start the Frontend Dashboard

In the second terminal, navigate to the `frontend-dashboard` directory and start the Next.js development server:

```bash
cd /Users/jinhochoi/Desktop/개발/bitcoin-trading-bot/frontend-dashboard
npm install # Run this only once to install dependencies
npm run dev
```

Leave this terminal running. The frontend will be accessible at `http://localhost:3000`.

### 3. Access the Application

Open your web browser and go to `http://localhost:3000`. You should see the Crypto Data Dashboard with real-time data and the backtesting interface.

## CCI Trading Strategy

The implemented strategy is based on the Commodity Channel Index (CCI). It generates:
- **Buy Signal:** When CCI crosses above the `buy_threshold` (default +100).
- **Sell Signal:** When CCI crosses below the `sell_threshold` (default -100).

Backtesting parameters can be adjusted directly from the frontend dashboard.
