"use client";

import { useState, useEffect } from 'react';

interface PortfolioStats {
  total_capital: number;
  total_allocated: number;
  available_capital: number;
  active_strategies: number;
  recent_trades_count: number;
  allocation_percentage: number;
}

interface StrategyPerformance {
  strategy_id: number;
  total_trades: number;
  winning_trades: number;
  win_rate: number;
  recent_trades: any[];
}

interface ActiveStrategy {
  id: number;
  strategy_id: number;
  exchange_name: string;
  symbol: string;
  allocated_capital: number;
  stop_loss_percentage: number;
  take_profit_percentage: number;
  is_active: boolean;
  created_at: string;
}

export default function MonitoringPage() {
  const [portfolioStats, setPortfolioStats] = useState<PortfolioStats | null>(null);
  const [activeStrategies, setActiveStrategies] = useState<ActiveStrategy[]>([]);
  const [performanceData, setPerformanceData] = useState<{ [key: number]: StrategyPerformance }>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    fetchAllData();
  }, []);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(fetchAllData, 10000); // Refresh every 10 seconds
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchPortfolioStats(),
        fetchActiveStrategies(),
      ]);
    } catch (e: any) {
      setError(`Failed to fetch monitoring data: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchPortfolioStats = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/portfolio/stats');
      if (!response.ok) throw new Error('Failed to fetch portfolio stats');
      const data = await response.json();
      setPortfolioStats(data);
    } catch (e: any) {
      console.error('Failed to fetch portfolio stats:', e.message);
    }
  };

  const fetchActiveStrategies = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/trading/active');
      if (!response.ok) throw new Error('Failed to fetch active strategies');
      const data = await response.json();
      setActiveStrategies(data);
      
      // Fetch performance for each active strategy
      for (const strategy of data) {
        fetchStrategyPerformance(strategy.strategy_id);
      }
    } catch (e: any) {
      console.error('Failed to fetch active strategies:', e.message);
    }
  };

  const fetchStrategyPerformance = async (strategyId: number) => {
    try {
      const response = await fetch(`http://127.0.0.1:8000/strategies/performance/${strategyId}`);
      if (!response.ok) throw new Error('Failed to fetch strategy performance');
      const data = await response.json();
      setPerformanceData(prev => ({ ...prev, [strategyId]: data }));
    } catch (e: any) {
      console.error(`Failed to fetch performance for strategy ${strategyId}:`, e.message);
    }
  };

  const getStrategyStatus = (strategy: ActiveStrategy) => {
    const performance = performanceData[strategy.strategy_id];
    if (!performance) return { status: 'Loading...', color: 'text-gray-400' };
    
    if (performance.total_trades === 0) {
      return { status: 'No Trades', color: 'text-gray-400' };
    }
    
    if (performance.win_rate >= 70) {
      return { status: 'Excellent', color: 'text-green-400' };
    } else if (performance.win_rate >= 50) {
      return { status: 'Good', color: 'text-blue-400' };
    } else if (performance.win_rate >= 30) {
      return { status: 'Average', color: 'text-yellow-400' };
    } else {
      return { status: 'Poor', color: 'text-red-400' };
    }
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <h2 className="text-h3 text-red-400 mb-4">Error</h2>
          <p className="text-body text-secondary mb-6">{error}</p>
          <button 
            onClick={() => {
              setError(null);
              fetchAllData();
            }}
            className="linear-button-primary py-2 px-4"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-h1">Performance Monitoring</h1>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="autoRefresh"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              <label htmlFor="autoRefresh" className="text-small text-secondary">
                Auto Refresh (10s)
              </label>
            </div>
            <button
              onClick={fetchAllData}
              disabled={loading}
              className="linear-button-primary py-2 px-4 disabled:opacity-50"
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Portfolio Overview */}
        {portfolioStats && (
          <div className="linear-card mb-8">
            <h2 className="text-h3 mb-6">Portfolio Overview</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Total Capital</p>
                <p className="text-h4 font-medium text-white">${portfolioStats.total_capital.toLocaleString()}</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Allocated</p>
                <p className="text-h4 font-medium text-green-400">${portfolioStats.total_allocated.toLocaleString()}</p>
                <p className="text-xs text-secondary">{portfolioStats.allocation_percentage.toFixed(1)}%</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Available</p>
                <p className="text-h4 font-medium text-blue-400">${portfolioStats.available_capital.toLocaleString()}</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Active Strategies</p>
                <p className="text-h4 font-medium text-white">{portfolioStats.active_strategies}</p>
              </div>
            </div>
          </div>
        )}

        {/* Active Strategies Performance */}
        <div className="linear-card">
          <h2 className="text-h3 mb-6">Active Strategies Performance</h2>
          {activeStrategies.length > 0 ? (
            <div className="space-y-4">
              {activeStrategies.map((strategy) => {
                const performance = performanceData[strategy.strategy_id];
                const status = getStrategyStatus(strategy);
                
                return (
                  <div key={strategy.id} className="glass-medium p-6 rounded-lg">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h3 className="text-body font-medium text-white mb-2">
                          {strategy.exchange_name.toUpperCase()} - {strategy.symbol}
                        </h3>
                        <p className="text-small text-secondary">
                          Strategy ID: {strategy.strategy_id} | Capital: ${strategy.allocated_capital.toLocaleString()}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className={`px-3 py-1 rounded-full text-xs font-medium ${status.color} bg-opacity-20`}>
                          {status.status}
                        </div>
                      </div>
                    </div>
                    
                    {performance ? (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="text-center">
                          <p className="text-small text-secondary mb-1">Total Trades</p>
                          <p className="text-body font-medium text-white">{performance.total_trades}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-small text-secondary mb-1">Winning Trades</p>
                          <p className="text-body font-medium text-green-400">{performance.winning_trades}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-small text-secondary mb-1">Win Rate</p>
                          <p className={`text-body font-medium ${
                            performance.win_rate >= 50 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {performance.win_rate.toFixed(1)}%
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-small text-secondary mb-1">Risk Settings</p>
                          <p className="text-small text-secondary">
                            SL: {strategy.stop_loss_percentage}% | TP: {strategy.take_profit_percentage}%
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-4">
                        <p className="text-small text-secondary">Loading performance data...</p>
                      </div>
                    )}
                    
                    {/* Recent Trades */}
                    {performance && performance.recent_trades && performance.recent_trades.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-gray-700">
                        <h4 className="text-small font-medium text-white mb-2">Recent Trades</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {performance.recent_trades.slice(0, 4).map((trade, index) => (
                            <div key={index} className="glass-light p-2 rounded text-xs">
                              <div className="flex justify-between">
                                <span className={trade.order_type === 'buy' ? 'text-green-400' : 'text-red-400'}>
                                  {trade.order_type?.toUpperCase()}
                                </span>
                                <span className="text-secondary">
                                  {new Date(trade.created_at).toLocaleString()}
                                </span>
                              </div>
                              <div className="text-secondary">
                                {trade.amount} @ ${trade.price}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="glass-light p-6 rounded-lg text-center">
              <div className="text-4xl mb-4">📊</div>
              <p className="text-body text-secondary mb-2">No Active Strategies</p>
              <p className="text-small text-secondary">
                Activate some strategies to start monitoring their performance.
              </p>
            </div>
          )}
        </div>

        {/* System Status */}
        <div className="linear-card mt-8">
          <h2 className="text-h3 mb-6">System Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="glass-light p-4 rounded-lg text-center">
              <div className="text-2xl mb-2">🟢</div>
              <p className="text-small font-medium text-white">API Connection</p>
              <p className="text-xs text-green-400">Online</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <div className="text-2xl mb-2">🟢</div>
              <p className="text-small font-medium text-white">Database</p>
              <p className="text-xs text-green-400">Connected</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <div className="text-2xl mb-2">{autoRefresh ? '🔄' : '⏸️'}</div>
              <p className="text-small font-medium text-white">Auto Refresh</p>
              <p className={`text-xs ${autoRefresh ? 'text-green-400' : 'text-gray-400'}`}>
                {autoRefresh ? 'Active' : 'Paused'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}