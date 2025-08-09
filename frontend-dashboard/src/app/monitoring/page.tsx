"use client";

import { useEffect, useState } from 'react';
import TradingChart from '@/components/TradingChart';
import { useWebSocket } from '@/contexts/WebSocketProvider';

export default function MonitoringPage() {
  const [lastUpdateTime, setLastUpdateTime] = useState<string>('');
  const [btcInterval, setBtcInterval] = useState<string>('1h');
  const [ethInterval, setEthInterval] = useState<string>('1h');
  const { data, isConnected: wsConnected, error: wsError, sendMessage } = useWebSocket();
  const { portfolio_stats: portfolioStats, active_strategies: activeStrategies, performance_data: performanceData } = data;

  useEffect(() => {
    if (wsConnected) {
      setLastUpdateTime(new Date().toLocaleTimeString());
    }
  }, [wsConnected, data]); // Update timestamp when connection status or data changes

  const requestManualUpdate = () => {
    if (wsConnected) {
      sendMessage({ type: 'request_update' });
      setLastUpdateTime(new Date().toLocaleTimeString()); // Update timestamp immediately on request
    }
  };

  const getStrategyStatus = (strategy: any) => { // Use 'any' for now, or import types from WebSocketProvider
    // Safe access to performanceData
    if (!performanceData || !strategy?.strategy_id) {
      return { status: 'Loading...', color: 'text-gray-400' };
    }
    
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

  if (wsError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <h2 className="text-h3 text-red-400 mb-4">Error</h2>
          <p className="text-body text-secondary mb-6">{wsError}</p>
          <button 
            onClick={() => window.location.reload()} // Simple reload to attempt reconnect
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
            <div className="flex items-center space-x-3">
              <div className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-red-400'}`}></div>
              <span className="text-small text-secondary">
                {wsConnected ? 'Live Connection' : 'Disconnected'}
              </span>
              {lastUpdateTime && (
                <span className="text-xs text-gray-400">
                  Last: {lastUpdateTime}
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={requestManualUpdate}
                disabled={!wsConnected}
                className="linear-button-secondary py-2 px-4 disabled:opacity-50"
              >
                Refresh Now
              </button>
            </div>
          </div>
        </div>

        {/* Real-time Trading Charts */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8 mb-8">
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-h3">BTC/USDT Chart</h3>
              <div className="flex space-x-1">
                {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setBtcInterval(tf)}
                    className={`px-2 py-1 text-xs rounded transition-colors ${
                      tf === btcInterval
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
            <TradingChart 
              symbol="BTC/USDT"
              exchange="bingx_vst"
              height={400}
              interval={btcInterval}
            />
          </div>
          <div>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-h3">ETH/USDT Chart</h3>
              <div className="flex space-x-1">
                {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setEthInterval(tf)}
                    className={`px-2 py-1 text-xs rounded transition-colors ${
                      tf === ethInterval
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
            <TradingChart 
              symbol="ETH/USDT"
              exchange="bingx_vst"
              height={400}
              interval={ethInterval}
            />
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
                // Safe access to performanceData
                const performance = performanceData && strategy?.strategy_id ? 
                  performanceData[strategy.strategy_id] : null;
                const status = getStrategyStatus(strategy);
                
                // Skip rendering if strategy data is incomplete
                if (!strategy || !strategy.id || !strategy.strategy_id) {
                  return null;
                }
                
                return (
                  <div key={strategy.id} className="glass-medium p-6 rounded-lg">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h3 className="text-body font-medium text-white mb-2">
                          {strategy.exchange_name ? strategy.exchange_name.toUpperCase() : 'Unknown'} - {strategy.symbol || 'Unknown'}
                        </h3>
                        <p className="text-small text-secondary">
                          Strategy ID: {strategy.strategy_id} | Capital: ${strategy.allocated_capital ? strategy.allocated_capital.toLocaleString() : '0'}
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
                          <p className="text-body font-medium text-white">{performance.total_trades ?? 'N/A'}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-small text-secondary mb-1">Winning Trades</p>
                          <p className="text-body font-medium text-green-400">{performance.winning_trades ?? 'N/A'}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-small text-secondary mb-1">Win Rate</p>
                          <p className={`text-body font-medium ${
                            (performance.win_rate ?? 0) >= 50 ? 'text-green-400' : 'text-red-400'
                          }`}>
                            {(performance.win_rate ?? 0).toFixed(1)}%
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-small text-secondary mb-1">Risk Settings</p>
                          <p className="text-small text-secondary">
                            SL: {strategy.stop_loss_percentage ?? 'N/A'}% | TP: {strategy.take_profit_percentage ?? 'N/A'}%
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-4">
                        <p className="text-small text-secondary">Awaiting performance data...</p>
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
              <div className="text-2xl mb-2">{wsConnected ? '🟢' : '🔴'}</div>
              <p className="text-small font-medium text-white">WebSocket</p>
              <p className={`text-xs ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
                {wsConnected ? 'Connected' : 'Disconnected'}
              </p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <div className="text-2xl mb-2">🟢</div>
              <p className="text-small font-medium text-white">API Server</p>
              <p className="text-xs text-green-400">Online</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <div className="text-2xl mb-2">⚡</div>
              <p className="text-small font-medium text-white">Real-time Updates</p>
              <p className={`text-xs ${wsConnected ? 'text-green-400' : 'text-gray-400'}`}>
                {wsConnected ? 'Active (5s interval)' : 'Inactive'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}