"use client";

import { useEffect, useState } from 'react';
import TradingChart from '@/components/TradingChart';
import { useWebSocket } from '@/contexts/WebSocketProvider';

export default function MonitoringPage() {
  const [lastUpdateTime, setLastUpdateTime] = useState<string>('');
  const [btcInterval, setBtcInterval] = useState<string>('1h');
  const [ethInterval, setEthInterval] = useState<string>('1h');
  const [vstPortfolioStats, setVstPortfolioStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  
  // 고급 기능 상태
  const [advancedAnalytics, setAdvancedAnalytics] = useState<any>(null);
  const [advancedFeaturesEnabled, setAdvancedFeaturesEnabled] = useState(false);
  const [realTimeIndicators, setRealTimeIndicators] = useState<any>(null);
  
  const { data, isConnected: wsConnected, error: wsError, sendMessage } = useWebSocket();
  const { portfolio_stats: portfolioStats, active_strategies: activeStrategies, performance_data: performanceData } = data;

  // VST 포트폴리오 데이터 가져오기
  const fetchVSTPortfolioData = async () => {
    try {
      setLoading(true);
      
      // VST 잔고 및 계정 정보 가져오기
      const balanceResponse = await fetch('http://127.0.0.1:8000/vst/balance');
      const balanceData = await balanceResponse.json();
      
      // VST 포지션 정보 가져오기
      const positionsResponse = await fetch('http://127.0.0.1:8000/vst/positions');
      const positionsData = await positionsResponse.json();
      
      // VST 거래 기록 가져오기
      const tradesResponse = await fetch('http://127.0.0.1:8000/vst/trades?limit=100');
      const tradesData = await tradesResponse.json();
      
      if (balanceResponse.ok && positionsResponse.ok && tradesResponse.ok) {
        const vstBalance = balanceData.account_info?.vst_balance || 0;
        const openPositions = positionsData.positions?.filter((p: any) => 
          parseFloat(p.positionAmt || 0) !== 0
        ) || [];
        
        // 할당된 자본 계산 (열린 포지션들의 가치 합계)
        const allocatedCapital = openPositions.reduce((total: number, position: any) => {
          const positionValue = Math.abs(parseFloat(position.positionAmt || 0)) * parseFloat(position.markPrice || 0);
          return total + positionValue;
        }, 0);
        
        // 포트폴리오 통계 생성
        const portfolioStats = {
          total_capital: vstBalance,
          total_allocated: allocatedCapital,
          available_capital: vstBalance - allocatedCapital,
          allocation_percentage: vstBalance > 0 ? (allocatedCapital / vstBalance) * 100 : 0,
          active_strategies: openPositions.length,
          total_trades: tradesData.trades?.length || 0,
          open_positions: openPositions.length
        };
        
        setVstPortfolioStats(portfolioStats);
        console.log('VST Portfolio Stats:', portfolioStats);
      }
      
    } catch (error) {
      console.error('Error fetching VST portfolio data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (wsConnected) {
      setLastUpdateTime(new Date().toLocaleTimeString());
    }
    
    // VST 데이터 초기 로드
    fetchVSTPortfolioData();
    checkAdvancedFeatures();
  }, [wsConnected, data]); // Update timestamp when connection status or data changes

  // 5초마다 VST 데이터 업데이트
  useEffect(() => {
    const interval = setInterval(() => {
      fetchVSTPortfolioData();
      if (advancedFeaturesEnabled) {
        fetchAdvancedAnalytics();
        fetchRealTimeIndicators();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [advancedFeaturesEnabled]);

  const checkAdvancedFeatures = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/advanced/status');
      if (response.ok) {
        const data = await response.json();
        setAdvancedFeaturesEnabled(data.enabled);
        if (data.enabled) {
          fetchAdvancedAnalytics();
          fetchRealTimeIndicators();
        }
      }
    } catch (e) {
      console.log('Advanced features not available');
    }
  };

  const fetchAdvancedAnalytics = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/analytics/advanced');
      if (response.ok) {
        const data = await response.json();
        setAdvancedAnalytics(data.data);
      }
    } catch (e) {
      console.error('Failed to fetch advanced analytics:', e);
    }
  };

  const fetchRealTimeIndicators = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/market/indicators/BTCUSDT');
      if (response.ok) {
        const data = await response.json();
        setRealTimeIndicators(data.data);
      }
    } catch (e) {
      console.error('Failed to fetch real-time indicators:', e);
    }
  };

  const requestManualUpdate = () => {
    if (wsConnected) {
      sendMessage({ type: 'request_update' });
      setLastUpdateTime(new Date().toLocaleTimeString()); // Update timestamp immediately on request
    }
    // VST 데이터도 수동으로 새로고침
    fetchVSTPortfolioData();
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
              {advancedFeaturesEnabled && (
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 rounded-full bg-blue-400"></div>
                  <span className="text-small text-blue-400">Advanced Analytics</span>
                </div>
              )}
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
                        ? 'bg-blue-600 text-black'
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
              exchange="bingx"
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
                        ? 'bg-blue-600 text-black'
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
              exchange="bingx"
              height={400}
              interval={ethInterval}
            />
          </div>
        </div>

        {/* Portfolio Overview - BingX VST Data */}
        {vstPortfolioStats && (
          <div className="linear-card mb-8">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-h3">Portfolio Overview (BingX VST)</h2>
              {loading && <div className="text-sm text-secondary">Updating...</div>}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Total Capital</p>
                <p className="text-h4 font-medium text-white">${vstPortfolioStats.total_capital.toLocaleString()}</p>
                <p className="text-xs text-green-400">BingX VST Account</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Allocated</p>
                <p className="text-h4 font-medium text-green-400">${vstPortfolioStats.total_allocated.toLocaleString()}</p>
                <p className="text-xs text-secondary">{vstPortfolioStats.allocation_percentage.toFixed(1)}%</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Available</p>
                <p className="text-h4 font-medium text-blue-400">${vstPortfolioStats.available_capital.toLocaleString()}</p>
                <p className="text-xs text-secondary">Free Margin</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Open Positions</p>
                <p className="text-h4 font-medium text-white">{vstPortfolioStats.open_positions}</p>
                <p className="text-xs text-secondary">{vstPortfolioStats.total_trades} Total Trades</p>
              </div>
            </div>
          </div>
        )}

        {/* Fallback Portfolio Overview */}
        {!vstPortfolioStats && portfolioStats && (
          <div className="linear-card mb-8">
            <h2 className="text-h3 mb-6">Portfolio Overview (Demo)</h2>
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

        {/* Advanced Analytics Dashboard */}
        {advancedFeaturesEnabled && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            {/* Real-time Indicators */}
            {realTimeIndicators && (
              <div className="linear-card">
                <h2 className="text-h3 mb-6">🔬 Advanced Technical Indicators</h2>
                <div className="space-y-4">
                  <div className="glass-light p-4 rounded-lg">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-small text-secondary">Composite Signal</span>
                      <span className={`text-sm font-medium px-2 py-1 rounded ${
                        realTimeIndicators.composite_signal?.signal === 'BUY' ? 'bg-green-500/20 text-green-400' :
                        realTimeIndicators.composite_signal?.signal === 'SELL' ? 'bg-red-500/20 text-red-400' :
                        'bg-gray-500/20 text-gray-400'
                      }`}>
                        {realTimeIndicators.composite_signal?.signal || 'NEUTRAL'}
                      </span>
                    </div>
                    <div className="text-xs text-secondary">
                      Confidence: {(realTimeIndicators.composite_signal?.confidence * 100)?.toFixed(1)}% 
                      | Strength: {realTimeIndicators.composite_signal?.strength}
                      | Trend: {realTimeIndicators.composite_signal?.trend}
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-3">
                    <div className="glass-light p-3 rounded text-center">
                      <p className="text-xs text-secondary mb-1">CCI</p>
                      <p className="text-sm font-medium text-white">
                        {realTimeIndicators.indicators?.cci?.current?.toFixed(1) || 'N/A'}
                      </p>
                      <p className={`text-xs ${
                        realTimeIndicators.indicators?.cci?.signal === 'BUY' ? 'text-green-400' :
                        realTimeIndicators.indicators?.cci?.signal === 'SELL' ? 'text-red-400' :
                        'text-gray-400'
                      }`}>
                        {realTimeIndicators.indicators?.cci?.signal || 'NEUTRAL'}
                      </p>
                    </div>
                    
                    <div className="glass-light p-3 rounded text-center">
                      <p className="text-xs text-secondary mb-1">RSI</p>
                      <p className="text-sm font-medium text-white">
                        {realTimeIndicators.indicators?.rsi?.current?.toFixed(1) || 'N/A'}
                      </p>
                      <p className={`text-xs ${
                        realTimeIndicators.indicators?.rsi?.signal === 'BUY' ? 'text-green-400' :
                        realTimeIndicators.indicators?.rsi?.signal === 'SELL' ? 'text-red-400' :
                        'text-gray-400'
                      }`}>
                        {realTimeIndicators.indicators?.rsi?.signal || 'NEUTRAL'}
                      </p>
                    </div>
                    
                    <div className="glass-light p-3 rounded text-center">
                      <p className="text-xs text-secondary mb-1">MACD</p>
                      <p className="text-sm font-medium text-white">
                        {realTimeIndicators.indicators?.macd?.current?.toFixed(1) || 'N/A'}
                      </p>
                      <p className={`text-xs ${
                        realTimeIndicators.indicators?.macd?.signal === 'BUY' ? 'text-green-400' :
                        realTimeIndicators.indicators?.macd?.signal === 'SELL' ? 'text-red-400' :
                        'text-gray-400'
                      }`}>
                        {realTimeIndicators.indicators?.macd?.signal || 'NEUTRAL'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Advanced Risk Analytics */}
            {advancedAnalytics && (
              <div className="linear-card">
                <h2 className="text-h3 mb-6">📊 Risk Analytics</h2>
                <div className="space-y-4">
                  {advancedAnalytics.risk_metrics && (
                    <div className="glass-light p-4 rounded-lg">
                      <h4 className="text-small font-medium text-white mb-3">Value at Risk (VaR)</h4>
                      <div className="grid grid-cols-3 gap-3 text-center">
                        <div>
                          <p className="text-xs text-secondary mb-1">VaR 95%</p>
                          <p className="text-sm font-medium text-red-400">
                            {advancedAnalytics.risk_metrics.var_95?.toFixed(2)}%
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-secondary mb-1">VaR 99%</p>
                          <p className="text-sm font-medium text-red-400">
                            {advancedAnalytics.risk_metrics.var_99?.toFixed(2)}%
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-secondary mb-1">CVaR 95%</p>
                          <p className="text-sm font-medium text-red-400">
                            {advancedAnalytics.risk_metrics.cvar_95?.toFixed(2)}%
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {advancedAnalytics.portfolio_performance && (
                    <div className="glass-light p-4 rounded-lg">
                      <h4 className="text-small font-medium text-white mb-3">Portfolio Performance</h4>
                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between">
                          <span className="text-secondary">Total Return:</span>
                          <span className="text-green-400">
                            {advancedAnalytics.portfolio_performance.total_return?.toFixed(2)}%
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary">Sharpe Ratio:</span>
                          <span className="text-blue-400">
                            {advancedAnalytics.portfolio_performance.sharpe_ratio?.toFixed(3)}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary">Max Drawdown:</span>
                          <span className="text-red-400">
                            {advancedAnalytics.portfolio_performance.max_drawdown?.toFixed(2)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
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