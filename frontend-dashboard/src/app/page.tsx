"use client";

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@clerk/nextjs';
import TradingChart from '@/components/TradingChart';
import { useWebSocket } from '@/contexts/WebSocketProvider';
import { LocalizedPageTitle, LocalizedSectionTitle, LocalizedSelectLabel, LocalizedButton, LocalizedTableHeader } from '@/components/LocalizedPage';
import { MobileContainer, MobileCard, MobileStatsGrid } from '@/components/MobileOptimized';
import NoSSR from '@/components/NoSSR';

export default function Home() {
  const { t } = useTranslation();
  const { getToken } = useAuth();
  const { data: websocketData } = useWebSocket();
  const { portfolio_stats: portfolioStats } = websocketData;
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [ticker, setTicker] = useState<any>(null);
  const [fetchError, setFetchError] = useState<string | null>(null); // Renamed to avoid conflict
  const [symbols, setSymbols] = useState<string[]>([]);
  const [loadingSymbols, setLoadingSymbols] = useState(false);
  const [loadingExchanges, setLoadingExchanges] = useState(false); // New loading state
  const [loadingTicker, setLoadingTicker] = useState(false); // New loading state

  const fetchWithAuth = async (url: string, options?: RequestInit) => {
    const token = await getToken();
    const headers = {
      ...(options?.headers || {}),
      'Authorization': `Bearer ${token}`,
    };
    return fetch(url, { ...options, headers });
  };

  // Backtesting state
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [backtestParams, setBacktestParams] = useState({
    exchange_id: 'bingx_vst',
    symbol: 'BTC/USDT',
    timeframe: '1d',
    limit: 100,
    window: 20,
    buy_threshold: 100,
    sell_threshold: -100,
    initial_capital: 10000,
    commission: 0.001,
  });
  const [chartTimeframe, setChartTimeframe] = useState('1h');
  const [loadingBacktest, setLoadingBacktest] = useState(false);
  
  // 전략 상태 관리
  const [activeStrategies, setActiveStrategies] = useState<any[]>([]);
  const [loadingStrategies, setLoadingStrategies] = useState(false);

  useEffect(() => {
    const fetchExchanges = async () => {
      setLoadingExchanges(true);
      setFetchError(null);
      try {
        const response = await fetchWithAuth('http://127.0.0.1:8000/exchanges');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setExchanges(data);
      } catch (e: any) {
        setFetchError(`Failed to fetch exchanges: ${e.message}`);
      } finally {
        setLoadingExchanges(false);
      }
    };

    fetchExchanges();
  }, []);

  useEffect(() => {
    const fetchSymbols = async () => {
      if (!backtestParams.exchange_id) return;
      setLoadingSymbols(true);
      setFetchError(null);
      try {
        const response = await fetchWithAuth(`http://127.0.0.1:8000/symbols/${backtestParams.exchange_id}`);
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
        setFetchError(`Failed to fetch symbols for ${backtestParams.exchange_id}: ${e.message}`);
      } finally {
        setLoadingSymbols(false);
      }
    };

    fetchSymbols();
  }, [backtestParams.exchange_id]);

  useEffect(() => {
    const fetchTicker = async () => {
      if (!backtestParams.exchange_id || !backtestParams.symbol) return;
      setLoadingTicker(true);
      setFetchError(null);
      try {
        const response = await fetchWithAuth(`http://127.0.0.1:8000/ticker/${backtestParams.exchange_id}/${backtestParams.symbol}`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setTicker(data);
      } catch (e: any) {
        setFetchError(`Failed to fetch ticker for ${backtestParams.exchange_id}/${backtestParams.symbol}: ${e.message}`);
      } finally {
        setLoadingTicker(false);
      }
    };
    fetchTicker();
  }, [backtestParams.exchange_id, backtestParams.symbol]);

  // 전략 목록 가져오기
  const fetchStrategies = async () => {
    setLoadingStrategies(true);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/strategies');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setActiveStrategies(data.filter((s: any) => s.status === 'active'));
    } catch (e: any) {
      console.error('Failed to fetch strategies:', e);
    } finally {
      setLoadingStrategies(false);
    }
  };

  useEffect(() => {
    fetchStrategies();
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
    setFetchError(null);
    try {
      const params = new URLSearchParams();
      for (const key in backtestParams) {
        if (key !== 'exchange_id' && key !== 'symbol') { // Exclude path params
          params.append(key, (backtestParams as any)[key].toString());
        }
      }
      const response = await fetchWithAuth(`http://127.0.0.1:8000/backtest/${backtestParams.exchange_id}/${backtestParams.symbol}?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setBacktestResults(data);
    } catch (e: any) {
      setFetchError(`Failed to run backtest: ${e.message}`);
    } finally {
      setLoadingBacktest(false);
    }
  };

  if (fetchError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <h2 className="text-h3 text-red-400 mb-4">Error</h2>
          <p className="text-body text-secondary mb-6">{fetchError}</p>
          <button 
            onClick={() => setFetchError(null)}
            className="linear-button-primary py-2 px-4"
          >
            Dismiss
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <NoSSR fallback={<h1 className="text-h1 text-center mb-12">Trading Dashboard</h1>}>
          <LocalizedPageTitle />
        </NoSSR>

        {/* Trading Chart */}
        <div className="mb-8">
          <NoSSR fallback={<div className="linear-card p-4 text-center">Loading chart...</div>}>
            <TradingChart 
              symbol={backtestParams.symbol}
              exchange={backtestParams.exchange_id}
              height={600}
              interval={chartTimeframe}
              onIntervalChange={setChartTimeframe}
            />
          </NoSSR>
        </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Exchanges List */}
        <div className="linear-card">
          <NoSSR fallback={<h2 className="text-h3 mb-6">Available Exchanges</h2>}>
            <LocalizedSectionTitle sectionKey="dashboard.selectExchange" />
          </NoSSR>
          {exchanges.length > 0 ? (
            <ul className="list-disc list-inside max-h-60 overflow-y-auto text-body space-y-1">
              {exchanges.map((exchange) => (
                <li key={exchange} className="text-small text-secondary">{exchange}</li>
              ))}
            </ul>
          ) : (
            <p className="text-small text-secondary">{loadingExchanges ? 'Loading exchanges...' : 'No exchanges found.'}</p>
          )}
        </div>

        {/* Real-time Ticker */}
        <div className="linear-card col-span-2">
          <NoSSR fallback={<h2 className="text-h3 mb-6">Real-time Ticker</h2>}>
            <LocalizedSectionTitle sectionKey="dashboard.currentPrice" />
          </NoSSR>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div>
              <NoSSR fallback={<label className="block text-small mb-2">Exchange:</label>}>
                <LocalizedSelectLabel labelKey="dashboard.selectExchange" />
              </NoSSR>
              <select
                name="exchange_id"
                value={backtestParams.exchange_id}
                onChange={handleBacktestChange}
                className="linear-select w-full"
                disabled={loadingExchanges || loadingTicker}
              >
                {exchanges.map((exchange) => (
                  <option key={exchange} value={exchange}>{exchange}</option>
                ))}
              </select>
            </div>
            <div>
              <NoSSR fallback={<label className="block text-small mb-2">Symbol:</label>}>
                <LocalizedSelectLabel labelKey="dashboard.selectSymbol" />
              </NoSSR>
              <NoSSR fallback={<select className="linear-select w-full"><option>Loading...</option></select>}>
                <select
                  name="symbol"
                  value={backtestParams.symbol}
                  onChange={handleBacktestChange}
                  className="linear-select w-full"
                  disabled={loadingSymbols || loadingTicker}
                >
                  {loadingSymbols ? (
                    <option>{t('common.loading')}</option>
                  ) : (
                    symbols.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))
                  )}
                </select>
              </NoSSR>
            </div>
          </div>
          {loadingTicker ? (
            <p className="text-small text-secondary">Loading ticker data...</p>
          ) : ticker ? (
            <div className="glass-light p-4 rounded-lg">
              <p className="text-body mb-2"><span className="text-secondary">Symbol:</span> <span className="text-white font-medium">{ticker.symbol}</span></p>
              <p className="text-body mb-2"><span className="text-secondary">Last Price:</span> <span className="text-white font-medium">${ticker.last?.toFixed(2)}</span></p>
              <p className="text-body mb-2"><span className="text-secondary">Bid Price:</span> <span className="text-white font-medium">${ticker.bid?.toFixed(2)}</span></p>
              <p className="text-body mb-2"><span className="text-secondary">Ask Price:</span> <span className="text-white font-medium">${ticker.ask?.toFixed(2)}</span></p>
              <p className="text-body mb-2"><span className="text-secondary">Volume:</span> <span className="text-white font-medium">{ticker.volume?.toFixed(2)}</span></p>
              <p className="text-body"><span className="text-secondary">Timestamp:</span> <span className="text-white font-medium">{new Date(ticker.timestamp).toLocaleString()}</span></p>
            </div>
          ) : (
            <p className="text-small text-secondary">No ticker data available.</p>
          )}
        </div>
      </div>

        {/* Portfolio Overview */}
        {portfolioStats && (
          <div className="linear-card mt-8">
            <LocalizedSectionTitle sectionKey="dashboard.portfolioOverview" />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Total Capital</p>
                <p className="text-h4 font-medium text-white">${portfolioStats.total_capital?.toLocaleString()}</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Allocated</p>
                <p className="text-h4 font-medium text-green-400">${portfolioStats.total_allocated?.toLocaleString()}</p>
                <p className="text-xs text-secondary">{portfolioStats.allocation_percentage?.toFixed(1)}%</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Available</p>
                <p className="text-h4 font-medium text-blue-400">${portfolioStats.available_capital?.toLocaleString()}</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Active Strategies</p>
                <p className="text-h4 font-medium text-white">{portfolioStats.active_strategies}</p>
              </div>
            </div>
          </div>
        )}

        {/* Demo Trading Controls */}
        <div className="linear-card mt-8">
          <NoSSR fallback={<h2 className="text-h3 mb-6">Demo Trading</h2>}>
            <LocalizedSectionTitle sectionKey="trading.demoTrading" />
          </NoSSR>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <button
              onClick={async () => {
                setLoadingStrategies(true);
                try {
                  const response = await fetchWithAuth('http://127.0.0.1:8000/trading/activate', { method: 'POST' });
                  const data = await response.json();
                  
                  if (data.success) {
                    alert(`Trading strategy activated successfully!\nStrategy ID: ${data.strategy_id}\nStatus: ${data.status}`);
                    // 전략 목록 새로고침
                    await fetchStrategies();
                  } else {
                    alert('Failed to activate strategy: ' + data.error);
                  }
                } catch (err: any) {
                  alert('Error: ' + err.message);
                } finally {
                  setLoadingStrategies(false);
                }
              }}
              className="linear-button-primary py-3 px-6"
              disabled={loadingStrategies}
            >
              {loadingStrategies ? '⏳ Activating...' : '🚀 Start Demo Trading'}
            </button>
            
            <button
              onClick={async () => {
                try {
                  const response = await fetchWithAuth('http://127.0.0.1:8000/trading/order', { method: 'POST' });
                  const data = await response.json();
                  
                  if (data.success) {
                    alert(`Test order placed successfully!\nDetails: ${JSON.stringify(data.order, null, 2)}`);
                  } else {
                    alert('Failed to place order: ' + data.error);
                  }
                } catch (err: any) {
                  alert('Error: ' + err.message);
                }
              }}
              className="linear-button-secondary py-3 px-6"
            >
              📈 Place Test Order
            </button>
            
            <button
              onClick={async () => {
                try {
                  const response = await fetchWithAuth('http://127.0.0.1:8000/vst/status');
                  const data = await response.json();
                  
                  if (data.status === 'connected') {
                    alert(`VST Connected! ✅\nBalance: $${data.vst_balance}\nEquity: $${data.equity}\nPositions: ${data.open_positions}/${data.total_positions}\nUnrealized PnL: $${data.unrealized_pnl}`);
                  } else {
                    alert('VST Status: ' + data.status + '\nError: ' + (data.error || 'Unknown'));
                  }
                } catch (err: any) {
                  alert('Error: ' + err.message);
                }
              }}
              className="linear-button-ghost py-3 px-6"
            >
              ⚙️ Check VST Status
            </button>
            
            <button
              onClick={async () => {
                try {
                  const response = await fetchWithAuth('http://127.0.0.1:8000/trading/history');
                  const data = await response.json();
                  
                  if (Array.isArray(data) && data.length > 0) {
                    const historyText = data.slice(0, 5).map((trade: any) => 
                      `${trade.side} ${trade.amount} ${trade.symbol} @ $${parseFloat(trade.price).toFixed(2)} | PnL: $${trade.pnl?.toFixed(2) || 'N/A'}`
                    ).join('\n');
                    alert('Recent Trades (Last 5):\n' + historyText);
                  } else {
                    alert('No recent trades found.');
                  }
                } catch (err: any) {
                  alert('Error: ' + err.message);
                }
              }}
              className="linear-button-ghost py-3 px-6"
            >
              📊 View History
            </button>
          </div>
          
          <div className="bg-blue-900 bg-opacity-20 border border-blue-500 rounded-lg p-4 text-sm">
            <p className="text-blue-300 mb-2">
              <strong>🧪 Demo Trading Mode</strong>
            </p>
            <p className="text-blue-200">
              Using BingX VST (Virtual Simulated Trading) with virtual funds. Activated strategies run automatically every minute and analyze real market data for trading signals.
            </p>
          </div>
        </div>

        {/* Active Strategies */}
        <div className="linear-card mt-8">
          <h2 className="text-h3 mb-6">Active Trading Strategies</h2>
          {loadingStrategies ? (
            <div className="text-center py-4">
              <div className="animate-spin text-2xl mb-2">⏳</div>
              <div className="text-secondary">Loading strategies...</div>
            </div>
          ) : activeStrategies.length > 0 ? (
            <div className="space-y-4">
              {activeStrategies.map((strategy: any) => (
                <div key={strategy.id} className="glass-medium p-4 rounded-lg">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-body font-medium text-white mb-2">{strategy.name}</h3>
                      <p className="text-small text-secondary">{strategy.description}</p>
                      <div className="flex space-x-4 mt-2 text-xs text-secondary">
                        <span>Executions: {strategy.execution_count || 0}</span>
                        <span>Trades: {strategy.total_trades || 0}</span>
                        <span>Created: {new Date(strategy.created_at * 1000).toLocaleString()}</span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        strategy.status === 'active' ? 'bg-green-600 text-white' : 'bg-gray-600 text-gray-300'
                      }`}>
                        {strategy.status.toUpperCase()}
                      </span>
                      <button
                        onClick={async () => {
                          try {
                            const response = await fetchWithAuth(`http://127.0.0.1:8000/strategies/stop/${strategy.id}`, { method: 'POST' });
                            const data = await response.json();
                            if (data.success) {
                              alert('Strategy stopped successfully!');
                              await fetchStrategies();
                            } else {
                              alert('Failed to stop strategy: ' + data.error);
                            }
                          } catch (err: any) {
                            alert('Error: ' + err.message);
                          }
                        }}
                        className="linear-button-ghost py-1 px-2 text-xs"
                      >
                        Stop
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="glass-light p-6 rounded-lg text-center">
              <div className="text-4xl mb-4">🤖</div>
              <p className="text-body text-secondary mb-2">No Active Strategies</p>
              <p className="text-small text-secondary">
                Click "Start Demo Trading" to activate your first strategy.
              </p>
            </div>
          )}
          <div className="mt-4 flex justify-between items-center">
            <div className="flex space-x-2">
              <button
                onClick={fetchStrategies}
                className="linear-button-secondary py-2 px-4 text-sm"
                disabled={loadingStrategies}
              >
                {loadingStrategies ? 'Refreshing...' : '🔄 Refresh'}
              </button>
              <button
                onClick={async () => {
                  try {
                    const response = await fetchWithAuth('http://127.0.0.1:8000/strategies/signals');
                    const data = await response.json();
                    
                    if (data.signals && data.signals.length > 0) {
                      const signalsText = data.signals.slice(0, 5).map((signal: any) => 
                        `${signal.signal} ${signal.quantity} BTC @ $${signal.price.toFixed(2)}\n${new Date(signal.timestamp * 1000).toLocaleString()}`
                      ).join('\n\n');
                      alert(`Trading Signals (Last 5):\n\n${signalsText}\n\nTotal Signals: ${data.total_signals}`);
                    } else {
                      alert('No trading signals found yet.\nSignals will appear when strategies detect buy/sell opportunities.');
                    }
                  } catch (err: any) {
                    alert('Error: ' + err.message);
                  }
                }}
                className="linear-button-ghost py-2 px-4 text-sm"
              >
                📊 View Signals
              </button>
            </div>
            <p className="text-xs text-secondary">
              Strategies execute automatically every minute when active
            </p>
          </div>
        </div>

        {/* Backtest Strategy */}
        <div className="linear-card mt-8">
          <LocalizedSectionTitle sectionKey="strategies.backtest" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <div>
            <LocalizedSelectLabel labelKey="dashboard.selectExchange" />
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
                <option>{t('common.loading')}</option>
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
          <NoSSR fallback={
            <button
              disabled={loadingBacktest}
              className="linear-button-primary py-3 px-8 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loadingBacktest ? 'Loading...' : 'Backtest'}
            </button>
          }>
            <button
              onClick={runBacktest}
              disabled={loadingBacktest}
              className="linear-button-primary py-3 px-8 disabled:opacity-50 disabled:cursor-not-allowed"
            >
            {loadingBacktest ? t('common.loading') : t('strategies.backtest')}
          </button>
          </NoSSR>

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