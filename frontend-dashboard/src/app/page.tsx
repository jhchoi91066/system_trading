"use client";

import { useState, useEffect } from 'react';

export default function Home() {
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [ticker, setTicker] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [loadingSymbols, setLoadingSymbols] = useState(false);

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

    fetchExchanges();
  }, []);

  useEffect(() => {
    const fetchSymbols = async () => {
      if (!backtestParams.exchange_id) return;
      setLoadingSymbols(true);
      setError(null);
      try {
        const response = await fetch(`http://127.0.0.1:8000/symbols/${backtestParams.exchange_id}`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setSymbols(data);
        // Set default symbol if available
        if (data.length > 0 && !data.includes(backtestParams.symbol)) {
          setBacktestParams(prevParams => ({ ...prevParams, symbol: data[0] }));
        }
      } catch (e: any) {
        setError(`Failed to fetch symbols for ${backtestParams.exchange_id}: ${e.message}`);
      } finally {
        setLoadingSymbols(false);
      }
    };

    fetchSymbols();
  }, [backtestParams.exchange_id]);

  useEffect(() => {
    const fetchTicker = async () => {
      if (!backtestParams.exchange_id || !backtestParams.symbol) return;
      try {
        const response = await fetch(`http://127.0.0.1:8000/ticker/${backtestParams.exchange_id}/${backtestParams.symbol}`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setTicker(data);
      } catch (e: any) {
        setError(`Failed to fetch ticker for ${backtestParams.exchange_id}/${backtestParams.symbol}: ${e.message}`);
      }
    };
    fetchTicker();
  }, [backtestParams.exchange_id, backtestParams.symbol]);


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
        if (key !== 'exchange_id' && key !== 'symbol') { // Exclude path params
          params.append(key, (backtestParams as any)[key].toString());
        }
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
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <h2 className="text-h3 text-red-400 mb-4">Error</h2>
          <p className="text-body text-secondary">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-h1 text-center mb-12">Trading Dashboard</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Exchanges List */}
        <div className="linear-card">
          <h2 className="text-h3 mb-6">Available Exchanges</h2>
          {exchanges.length > 0 ? (
            <ul className="list-disc list-inside max-h-60 overflow-y-auto text-body space-y-1">
              {exchanges.map((exchange) => (
                <li key={exchange} className="text-small text-secondary">{exchange}</li>
              ))}
            </ul>
          ) : (
            <p className="text-small text-secondary">Loading exchanges...</p>
          )}
        </div>

        {/* Real-time Ticker */}
        <div className="linear-card col-span-2">
          <h2 className="text-h3 mb-6">Real-time Ticker</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <label className="block text-small mb-2">Exchange:</label>
              <select
                name="exchange_id"
                value={backtestParams.exchange_id}
                onChange={handleBacktestChange}
                className="linear-select w-full"
              >
                {exchanges.map((exchange) => (
                  <option key={exchange} value={exchange}>{exchange}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-small mb-2">Symbol:</label>
              <select
                name="symbol"
                value={backtestParams.symbol}
                onChange={handleBacktestChange}
                className="linear-select w-full"
                disabled={loadingSymbols}
              >
                {loadingSymbols ? (
                  <option>Loading symbols...</option>
                ) : (
                  symbols.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))
                )}
              </select>
            </div>
          </div>
          {ticker ? (
            <div className="glass-light p-4 rounded-lg">
              <p className="text-body mb-2"><span className="text-secondary">Symbol:</span> <span className="text-white font-medium">{ticker.symbol}</span></p>
              <p className="text-body mb-2"><span className="text-secondary">Last Price:</span> <span className="text-white font-medium">${ticker.last?.toFixed(2)}</span></p>
              <p className="text-body mb-2"><span className="text-secondary">Bid Price:</span> <span className="text-white font-medium">${ticker.bid?.toFixed(2)}</span></p>
              <p className="text-body mb-2"><span className="text-secondary">Ask Price:</span> <span className="text-white font-medium">${ticker.ask?.toFixed(2)}</span></p>
              <p className="text-body mb-2"><span className="text-secondary">Volume:</span> <span className="text-white font-medium">{ticker.volume?.toFixed(2)}</span></p>
              <p className="text-body"><span className="text-secondary">Timestamp:</span> <span className="text-white font-medium">{new Date(ticker.timestamp).toLocaleString()}</span></p>
            </div>
          ) : (
            <p className="text-small text-secondary">Loading ticker data...</p>
          )}
        </div>
      </div>

        {/* Backtest Strategy */}
        <div className="linear-card mt-8">
          <h2 className="text-h3 mb-6">Backtest Strategy (CCI)</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-small mb-2">Exchange ID:</label>
            <select
              name="exchange_id"
              value={backtestParams.exchange_id}
              onChange={handleBacktestChange}
              className="linear-select w-full"
            >
              {exchanges.map((exchange) => (
                <option key={exchange} value={exchange}>{exchange}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-small mb-2">Symbol:</label>
            <select
              name="symbol"
              value={backtestParams.symbol}
              onChange={handleBacktestChange}
              className="linear-select w-full"
              disabled={loadingSymbols}
            >
              {loadingSymbols ? (
                <option>Loading symbols...</option>
              ) : (
                symbols.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))
              )}
            </select>
          </div>
          <div>
            <label className="block text-small mb-2">Timeframe:</label>
            <input
              type="text"
              name="timeframe"
              value={backtestParams.timeframe}
              onChange={handleBacktestChange}
              className="linear-input w-full"
            />
          </div>
          <div>
            <label className="block text-small mb-2">Limit (OHLCV data points):</label>
            <input
              type="number"
              name="limit"
              value={backtestParams.limit}
              onChange={handleBacktestChange}
              className="linear-input w-full"
            />
          </div>
          <div>
            <label className="block text-small mb-2">CCI Window:</label>
            <input
              type="number"
              name="window"
              value={backtestParams.window}
              onChange={handleBacktestChange}
              className="linear-input w-full"
            />
          </div>
          <div>
            <label className="block text-small mb-2">Buy Threshold:</label>
            <input
              type="number"
              name="buy_threshold"
              value={backtestParams.buy_threshold}
              onChange={handleBacktestChange}
              className="linear-input w-full"
            />
          </div>
          <div>
            <label className="block text-small mb-2">Sell Threshold:</label>
            <input
              type="number"
              name="sell_threshold"
              value={backtestParams.sell_threshold}
              onChange={handleBacktestChange}
              className="linear-input w-full"
            />
          </div>
          <div>
            <label className="block text-small mb-2">Initial Capital:</label>
            <input
              type="number"
              name="initial_capital"
              value={backtestParams.initial_capital}
              onChange={handleBacktestChange}
              className="linear-input w-full"
            />
          </div>
          <div>
            <label className="block text-small mb-2">Commission Rate:</label>
            <input
              type="number"
              name="commission"
              value={backtestParams.commission}
              onChange={handleBacktestChange}
              step="0.0001"
              className="linear-input w-full"
            />
          </div>
        </div>
          <button
            onClick={runBacktest}
            disabled={loadingBacktest}
            className="linear-button-primary py-3 px-8 disabled:opacity-50 disabled:cursor-not-allowed"
          >
          {loadingBacktest ? 'Running Backtest...' : 'Run Backtest'}
        </button>

        {backtestResults && (
            <div className="mt-8 glass-medium p-6 rounded-lg">
              <h3 className="text-h3 mb-6">Backtest Results</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <p className="text-body"><span className="text-secondary">Initial Capital:</span> <span className="text-white font-medium">${backtestResults.initial_capital?.toFixed(2)}</span></p>
                <p className="text-body"><span className="text-secondary">Final Capital:</span> <span className="text-white font-medium">${backtestResults.final_capital?.toFixed(2)}</span></p>
                <p className="text-body"><span className="text-secondary">Profit/Loss:</span> <span className={`font-medium ${backtestResults.profit_loss >= 0 ? 'text-green-400' : 'text-red-400'}`}>${backtestResults.profit_loss?.toFixed(2)}</span></p>
            </div>

              <h4 className="text-h3 mb-4">Trades</h4>
            {backtestResults.trades.length > 0 ? (
                <div className="max-h-60 overflow-y-auto glass-light rounded-lg">
                  <table className="min-w-full divide-y divide-white divide-opacity-10">
                    <thead className="glass-medium">
                    <tr>
                        <th scope="col" className="px-6 py-3 text-left text-caption text-secondary uppercase tracking-wider">Timestamp</th>
                        <th scope="col" className="px-6 py-3 text-left text-caption text-secondary uppercase tracking-wider">Type</th>
                        <th scope="col" className="px-6 py-3 text-left text-caption text-secondary uppercase tracking-wider">Amount</th>
                        <th scope="col" className="px-6 py-3 text-left text-caption text-secondary uppercase tracking-wider">Price</th>
                        <th scope="col" className="px-6 py-3 text-left text-caption text-secondary uppercase tracking-wider">Capital</th>
                    </tr>
                  </thead>
                    <tbody className="divide-y divide-white divide-opacity-5">
                    {backtestResults.trades.map((trade: any, index: number) => (
                      <tr key={index}>
                          <td className="px-6 py-4 whitespace-nowrap text-small text-white">{new Date(trade.timestamp).toLocaleString()}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-small font-medium text-white">{trade.type.toUpperCase()}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-small text-white">{trade.amount?.toFixed(5)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-small text-white">${trade.price?.toFixed(2)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-small text-white">${trade.capital?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
                <p className="text-small text-secondary">No trades executed.</p>
            )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}