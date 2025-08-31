"use client";

import { useEffect, useState } from 'react';
import { useWebSocket } from '@/contexts/WebSocketProvider';

interface PortfolioAnalytics {
  current_value: number;
  total_pnl: number;
  daily_pnl: number;
  weekly_pnl: number;
  monthly_pnl: number;
  total_return_percent: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  avg_trade_duration: number;
  risk_metrics: {
    var_95: number;
    var_99: number;
    cvar_95: number;
    volatility: number;
    beta: number;
  };
  allocation: {
    [symbol: string]: {
      allocation_percent: number;
      current_value: number;
      pnl: number;
      pnl_percent: number;
    };
  };
}

interface RiskMetrics {
  current_risk_score: number;
  position_concentration: number;
  correlation_risk: number;
  volatility_risk: number;
  drawdown_risk: number;
  liquidity_risk: number;
  recommendations: string[];
}

export default function PortfolioPage() {
  const [portfolioData, setPortfolioData] = useState<PortfolioAnalytics | null>(null);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdateTime, setLastUpdateTime] = useState<string>('');

  const { data, isConnected: wsConnected } = useWebSocket();

  const fetchPortfolioAnalytics = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/analytics/portfolio');
      if (response.ok) {
        const data = await response.json();
        setPortfolioData(data.data);
        setError(null);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      setError(`Portfolio API: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const fetchRiskMetrics = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/analytics/risk');
      if (response.ok) {
        const data = await response.json();
        setRiskMetrics(data.data);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      console.error('Risk metrics error:', err);
    }
  };

  const fetchAllData = async () => {
    setLoading(true);
    await Promise.all([
      fetchPortfolioAnalytics(),
      fetchRiskMetrics()
    ]);
    setLoading(false);
    setLastUpdateTime(new Date().toLocaleTimeString());
  };

  useEffect(() => {
    fetchAllData();
    
    // Auto-refresh every 15 seconds
    const interval = setInterval(fetchAllData, 15000);
    return () => clearInterval(interval);
  }, []);

  const getRiskColor = (score: number) => {
    if (score >= 8) return 'text-red-400';
    if (score >= 6) return 'text-yellow-400';
    if (score >= 4) return 'text-blue-400';
    return 'text-green-400';
  };

  const getPerformanceColor = (value: number) => {
    return value >= 0 ? 'text-green-400' : 'text-red-400';
  };

  if (loading && !portfolioData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400 mx-auto mb-4"></div>
          <p className="text-body text-secondary">Loading Portfolio Analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-h1">💼 Portfolio Analytics</h1>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-3">
              <div className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-red-400'}`}></div>
              <span className="text-small text-secondary">
                {wsConnected ? 'Live Updates' : 'Disconnected'}
              </span>
              {lastUpdateTime && (
                <span className="text-xs text-gray-400">
                  Last: {lastUpdateTime}
                </span>
              )}
            </div>
            <button
              onClick={fetchAllData}
              disabled={loading}
              className="linear-button-secondary py-2 px-4 disabled:opacity-50"
            >
              {loading ? 'Updating...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Portfolio Overview */}
        {portfolioData && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Portfolio Value</p>
              <p className="text-h3 font-medium text-white">${portfolioData.current_value.toLocaleString()}</p>
              <p className={`text-small ${getPerformanceColor(portfolioData.total_return_percent)}`}>
                {portfolioData.total_return_percent >= 0 ? '+' : ''}{portfolioData.total_return_percent.toFixed(2)}%
              </p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Daily P&L</p>
              <p className={`text-h3 font-medium ${getPerformanceColor(portfolioData.daily_pnl)}`}>
                ${portfolioData.daily_pnl.toFixed(2)}
              </p>
              <p className="text-small text-secondary">Today</p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Sharpe Ratio</p>
              <p className="text-h3 font-medium text-blue-400">{portfolioData.sharpe_ratio.toFixed(3)}</p>
              <p className="text-small text-secondary">Risk-adjusted</p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Max Drawdown</p>
              <p className="text-h3 font-medium text-red-400">{portfolioData.max_drawdown.toFixed(2)}%</p>
              <p className="text-small text-secondary">Historical</p>
            </div>
          </div>
        )}

        {/* Risk Analysis */}
        {riskMetrics && (
          <div className="linear-card mb-8">
            <h2 className="text-h3 mb-6">🛡️ Risk Analysis</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="glass-light p-6 rounded-lg">
                <h3 className="text-body font-medium text-white mb-4">Risk Metrics</h3>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-small text-secondary">Current Risk Score</span>
                    <span className={`text-body font-medium ${getRiskColor(riskMetrics.current_risk_score)}`}>
                      {riskMetrics.current_risk_score.toFixed(1)}/10
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Position Concentration:</span>
                    <span className="text-small text-white">{riskMetrics.position_concentration.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Correlation Risk:</span>
                    <span className="text-small text-white">{riskMetrics.correlation_risk.toFixed(3)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Volatility Risk:</span>
                    <span className="text-small text-white">{riskMetrics.volatility_risk.toFixed(2)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Liquidity Risk:</span>
                    <span className="text-small text-white">{riskMetrics.liquidity_risk.toFixed(2)}</span>
                  </div>
                </div>
              </div>

              <div className="glass-light p-6 rounded-lg">
                <h3 className="text-body font-medium text-white mb-4">Risk Recommendations</h3>
                <div className="space-y-3">
                  {riskMetrics.recommendations.map((recommendation, index) => (
                    <div key={index} className="flex items-start space-x-3">
                      <span className="text-blue-400 mt-1">•</span>
                      <span className="text-small text-secondary">{recommendation}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Value at Risk (VaR) */}
        {portfolioData?.risk_metrics && (
          <div className="linear-card mb-8">
            <h2 className="text-h3 mb-6">📊 Value at Risk (VaR)</h2>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">VaR 95%</p>
                <p className="text-h4 font-medium text-red-400">
                  {portfolioData.risk_metrics.var_95.toFixed(2)}%
                </p>
                <p className="text-xs text-secondary">1-day horizon</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">VaR 99%</p>
                <p className="text-h4 font-medium text-red-400">
                  {portfolioData.risk_metrics.var_99.toFixed(2)}%
                </p>
                <p className="text-xs text-secondary">1-day horizon</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">CVaR 95%</p>
                <p className="text-h4 font-medium text-red-400">
                  {portfolioData.risk_metrics.cvar_95.toFixed(2)}%
                </p>
                <p className="text-xs text-secondary">Expected shortfall</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Volatility</p>
                <p className="text-h4 font-medium text-yellow-400">
                  {portfolioData.risk_metrics.volatility.toFixed(1)}%
                </p>
                <p className="text-xs text-secondary">Annualized</p>
              </div>
              <div className="glass-light p-4 rounded-lg text-center">
                <p className="text-small text-secondary mb-1">Beta</p>
                <p className="text-h4 font-medium text-blue-400">
                  {portfolioData.risk_metrics.beta.toFixed(3)}
                </p>
                <p className="text-xs text-secondary">vs BTC</p>
              </div>
            </div>
          </div>
        )}

        {/* Asset Allocation */}
        {portfolioData?.allocation && Object.keys(portfolioData.allocation).length > 0 && (
          <div className="linear-card mb-8">
            <h2 className="text-h3 mb-6">🎯 Asset Allocation</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(portfolioData.allocation).map(([symbol, allocation]) => (
                <div key={symbol} className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-body font-medium text-white">{symbol}</h3>
                    <span className="text-small text-secondary">
                      {allocation.allocation_percent.toFixed(1)}%
                    </span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-small text-secondary">Value:</span>
                      <span className="text-small text-white">${allocation.current_value.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-small text-secondary">P&L:</span>
                      <span className={`text-small ${getPerformanceColor(allocation.pnl)}`}>
                        ${allocation.pnl.toFixed(2)} ({allocation.pnl_percent.toFixed(1)}%)
                      </span>
                    </div>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2 mt-3">
                    <div 
                      className="h-2 rounded-full bg-blue-400"
                      style={{ width: `${allocation.allocation_percent}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Performance Summary */}
        {portfolioData && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="linear-card">
              <h2 className="text-h3 mb-6">📈 Performance Summary</h2>
              <div className="space-y-4">
                <div className="glass-light p-4 rounded-lg">
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <p className="text-small text-secondary mb-1">Daily P&L</p>
                      <p className={`text-body font-medium ${getPerformanceColor(portfolioData.daily_pnl)}`}>
                        ${portfolioData.daily_pnl.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-small text-secondary mb-1">Weekly P&L</p>
                      <p className={`text-body font-medium ${getPerformanceColor(portfolioData.weekly_pnl)}`}>
                        ${portfolioData.weekly_pnl.toFixed(2)}
                      </p>
                    </div>
                    <div>
                      <p className="text-small text-secondary mb-1">Monthly P&L</p>
                      <p className={`text-body font-medium ${getPerformanceColor(portfolioData.monthly_pnl)}`}>
                        ${portfolioData.monthly_pnl.toFixed(2)}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="glass-light p-4 rounded-lg">
                  <h4 className="text-small font-medium text-white mb-3">Trading Statistics</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-small text-secondary">Total Trades:</span>
                      <span className="text-small text-white">{portfolioData.total_trades}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-small text-secondary">Win Rate:</span>
                      <span className={`text-small ${portfolioData.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                        {portfolioData.win_rate.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-small text-secondary">Avg Trade Duration:</span>
                      <span className="text-small text-white">{portfolioData.avg_trade_duration.toFixed(1)} hrs</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="linear-card">
              <h2 className="text-h3 mb-6">⚠️ Risk Management</h2>
              <div className="space-y-4">
                {riskMetrics && (
                  <div className="glass-light p-4 rounded-lg">
                    <div className="flex justify-between items-center mb-4">
                      <span className="text-small text-secondary">Current Risk Score</span>
                      <span className={`text-h4 font-medium ${getRiskColor(riskMetrics.current_risk_score)}`}>
                        {riskMetrics.current_risk_score.toFixed(1)}/10
                      </span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-3">
                      <div 
                        className={`h-3 rounded-full ${
                          riskMetrics.current_risk_score >= 8 ? 'bg-red-400' :
                          riskMetrics.current_risk_score >= 6 ? 'bg-yellow-400' :
                          riskMetrics.current_risk_score >= 4 ? 'bg-blue-400' : 'bg-green-400'
                        }`}
                        style={{ width: `${(riskMetrics.current_risk_score / 10) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                )}

                <div className="glass-light p-4 rounded-lg">
                  <h4 className="text-small font-medium text-white mb-3">Risk Breakdown</h4>
                  <div className="space-y-2 text-xs">
                    {riskMetrics && (
                      <>
                        <div className="flex justify-between">
                          <span className="text-secondary">Position Concentration:</span>
                          <span className="text-white">{riskMetrics.position_concentration.toFixed(1)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary">Correlation Risk:</span>
                          <span className="text-white">{riskMetrics.correlation_risk.toFixed(3)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary">Volatility Risk:</span>
                          <span className="text-white">{riskMetrics.volatility_risk.toFixed(2)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-secondary">Liquidity Risk:</span>
                          <span className="text-white">{riskMetrics.liquidity_risk.toFixed(2)}</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {riskMetrics?.recommendations && riskMetrics.recommendations.length > 0 && (
                  <div className="glass-light p-4 rounded-lg">
                    <h4 className="text-small font-medium text-white mb-3">Risk Recommendations</h4>
                    <div className="space-y-2">
                      {riskMetrics.recommendations.slice(0, 3).map((rec, index) => (
                        <div key={index} className="flex items-start space-x-2">
                          <span className="text-blue-400 mt-1 text-xs">•</span>
                          <span className="text-xs text-secondary">{rec}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="linear-card border border-red-500/30 bg-red-500/10">
            <div className="flex items-center space-x-3">
              <div className="text-2xl">🚨</div>
              <div>
                <h3 className="text-body font-medium text-red-400">Portfolio Analytics Error</h3>
                <p className="text-small text-secondary">{error}</p>
                <button 
                  onClick={fetchAllData}
                  className="text-small text-blue-400 hover:text-blue-300 mt-2"
                >
                  Retry Connection
                </button>
              </div>
            </div>
          </div>
        )}

        {/* WebSocket Connection Status */}
        <div className="linear-card mt-8">
          <h2 className="text-h3 mb-6">🔗 Real-time Connection Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="glass-light p-4 rounded-lg text-center">
              <div className="text-2xl mb-2">{wsConnected ? '🟢' : '🔴'}</div>
              <p className="text-small font-medium text-white">WebSocket</p>
              <p className={`text-xs ${wsConnected ? 'text-green-400' : 'text-red-400'}`}>
                {wsConnected ? 'Connected' : 'Disconnected'}
              </p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <div className="text-2xl mb-2">📊</div>
              <p className="text-small font-medium text-white">Portfolio Updates</p>
              <p className="text-xs text-green-400">Live (15s interval)</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <div className="text-2xl mb-2">⚡</div>
              <p className="text-small font-medium text-white">Risk Monitoring</p>
              <p className="text-xs text-green-400">Real-time</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}