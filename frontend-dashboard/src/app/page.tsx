"use client";

"use client";

import { useState, useEffect } from 'react';

export default function Home() {
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [ticker, setTicker] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Backtesting state
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [backtestParams, setBacktestParams] = useState({
    exchange_id: 'binance',
    symbol: 'BTC/USDT',
    timeframe: '1d',
    limit: 100,
    window: 20,
    buy_threshold: 100,
    sell_threshold: -100,
    initial_capital: 10000,
    commission: 0.001,
  });
  const [loadingBacktest, setLoadingBacktest] = useState(false);

  useEffect(() => {
    const fetchExchanges = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/exchanges');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setExchanges(data);
      } catch (e: any) {
        setError(`Failed to fetch exchanges: ${e.message}`);
      }
    };

    const fetchTicker = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/ticker/binance/BTC/USDT');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setTicker(data);
      } catch (e: any) {
        setError(`Failed to fetch ticker: ${e.message}`);
      }
    };

    fetchExchanges();
    fetchTicker();
  }, []);

  const handleBacktestChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setBacktestParams((prevParams) => ({
      ...prevParams,
      [name]: name === 'limit' || name === 'window' || name === 'buy_threshold' || name === 'sell_threshold' || name === 'initial_capital' || name === 'commission' ? parseFloat(value) : value,
    }));
  };

  const runBacktest = async () => {
    setLoadingBacktest(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      for (const key in backtestParams) {
        params.append(key, (backtestParams as any)[key].toString());
      }
      const response = await fetch(`http://127.0.0.1:8000/backtest/${backtestParams.exchange_id}/${backtestParams.symbol}?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setBacktestResults(data);
    } catch (e: any) {
      setError(`Failed to run backtest: ${e.message}`);
    } finally {
      setLoadingBacktest(false);
    }
  };

  if (error) {
    return <div className="text-red-500">Error: {error}</div>;
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Crypto Data Dashboard</h1>

      <h2 className="text-xl font-semibold mb-2">Available Exchanges</h2>
      {exchanges.length > 0 ? (
        <ul className="list-disc list-inside mb-4">
          {exchanges.map((exchange) => (
            <li key={exchange}>{exchange}</li>
          ))}
        </ul>
      ) : (
        <p>Loading exchanges...</p>
      )}

      <h2 className="text-xl font-semibold mb-2">Binance BTC/USDT Ticker</h2>
      {ticker ? (
        <div className="bg-gray-100 p-4 rounded-lg mb-8">
          <p><strong>Symbol:</strong> {ticker.symbol}</p>
          <p><strong>Last Price:</strong> {ticker.last}</p>
          <p><strong>Bid Price:</strong> {ticker.bid}</p>
          <p><strong>Ask Price:</strong> {ticker.ask}</p>
          <p><strong>Volume:</strong> {ticker.volume}</p>
          <p><strong>Timestamp:</strong> {new Date(ticker.timestamp).toLocaleString()}</p>
        </div>
      ) : (
        <p>Loading ticker data...</p>
      )}

      <h2 className="text-xl font-semibold mb-4">Backtest Strategy (CCI)</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <div>
          <label className="block text-sm font-medium text-gray-700">Exchange ID:</label>
          <input
            type="text"
            name="exchange_id"
            value={backtestParams.exchange_id}
            onChange={handleBacktestChange}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Symbol:</label>
          <input
            type="text"
            name="symbol"
            value={backtestParams.symbol}
            onChange={handleBacktestChange}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Timeframe:</label>
          <input
            type="text"
            name="timeframe"
            value={backtestParams.timeframe}
            onChange={handleBacktestChange}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Limit (OHLCV data points):</label>
          <input
            type="number"
            name="limit"
            value={backtestParams.limit}
            onChange={handleBacktestChange}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">CCI Window:</label>
          <input
            type="number"
            name="window"
            value={backtestParams.window}
            onChange={handleBacktestChange}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Buy Threshold:</label>
          <input
            type="number"
            name="buy_threshold"
            value={backtestParams.buy_threshold}
            onChange={handleBacktestChange}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Sell Threshold:</label>
          <input
            type="number"
            name="sell_threshold"
            value={backtestParams.sell_threshold}
            onChange={handleBacktestChange}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Initial Capital:</label>
          <input
            type="number"
            name="initial_capital"
            value={backtestParams.initial_capital}
            onChange={handleBacktestChange}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Commission Rate:</label>
          <input
            type="number"
            name="commission"
            value={backtestParams.commission}
            onChange={handleBacktestChange}
            step="0.0001"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50"
          />
        </div>
      </div>
      <button
        onClick={runBacktest}
        disabled={loadingBacktest}
        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded disabled:opacity-50"
      >
        {loadingBacktest ? 'Running Backtest...' : 'Run Backtest'}
      </button>

      {backtestResults && (
        <div className="mt-8 p-4 bg-green-100 rounded-lg">
          <h3 className="text-xl font-semibold mb-2">Backtest Results</h3>
          <p><strong>Initial Capital:</strong> {backtestResults.initial_capital.toFixed(2)}</p>
          <p><strong>Final Capital:</strong> {backtestResults.final_capital.toFixed(2)}</p>
          <p><strong>Profit/Loss:</strong> {backtestResults.profit_loss.toFixed(2)}</p>

          <h4 className="text-lg font-semibold mt-4 mb-2">Trades</h4>
          {backtestResults.trades.length > 0 ? (
            <ul className="list-disc list-inside">
              {backtestResults.trades.map((trade: any, index: number) => (
                <li key={index}>
                  {new Date(trade.timestamp).toLocaleString()}: {trade.type.toUpperCase()} {trade.amount.toFixed(5)} at {trade.price.toFixed(2)} (Capital: {trade.capital.toFixed(2)})
                </li>
              ))}
            </ul>
          ) : (
            <p>No trades executed.</p>
          )}
        </div>
      )}
    </div>
  );
}
