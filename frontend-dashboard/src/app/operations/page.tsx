"use client";

import { useEffect, useState } from 'react';
import { useWebSocket } from '@/contexts/WebSocketProvider';

interface PerformanceData {
  timestamp: string;
  system: {
    cpu_percent: number;
    memory_percent: number;
    memory_used_mb: number;
    disk_percent: number;
    network_sent_mb: number;
    network_recv_mb: number;
    process_count: number;
    load_average: number[];
  };
  application: {
    active_connections: number;
    api_requests_per_minute: number;
    response_time_avg_ms: number;
    error_rate_percent: number;
    database_connections: number;
    cache_hit_rate: number;
    queue_size: number;
    memory_usage_mb: number;
  };
  trading: {
    active_positions: number;
    orders_per_minute: number;
    latency_ms: number;
    success_rate: number;
    pnl_last_hour: number;
    volume_traded: number;
    strategy_count: number;
    risk_score: number;
  };
  active_alerts: number;
}

interface SystemOverview {
  timestamp: string;
  system_status: string;
  uptime: string;
  environment: string;
  services: {
    [key: string]: boolean;
  };
  performance_summary: {
    cpu_usage: number;
    memory_usage: number;
    response_time: number;
    error_rate: number;
  };
  alerts_summary: {
    active_alerts: number;
    critical_alerts: number;
    warning_alerts: number;
  };
}

export default function OperationsPage() {
  const [performanceData, setPerformanceData] = useState<PerformanceData | null>(null);
  const [systemOverview, setSystemOverview] = useState<SystemOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdateTime, setLastUpdateTime] = useState<string>('');
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { isConnected: wsConnected } = useWebSocket();

  const fetchPerformanceData = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/operations/performance/current');
      if (response.ok) {
        const data = await response.json();
        setPerformanceData(data.data);
        setError(null);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      setError(`Performance API: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const fetchSystemOverview = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/operations/system/overview');
      if (response.ok) {
        const data = await response.json();
        setSystemOverview(data.data);
        setError(null);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      setError(`System API: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const fetchAllData = async () => {
    setLoading(true);
    await Promise.all([
      fetchPerformanceData(),
      fetchSystemOverview()
    ]);
    setLoading(false);
    setLastUpdateTime(new Date().toLocaleTimeString());
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchAllData, 10000); // 10초마다 업데이트
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy': return 'text-green-400';
      case 'warning': return 'text-yellow-400';
      case 'critical': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getServiceStatusIcon = (status: boolean) => {
    return status ? '🟢' : '🔴';
  };

  if (loading && !performanceData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400 mx-auto mb-4"></div>
          <p className="text-body text-secondary">Loading Operations Dashboard...</p>
        </div>
      </div>
    );
  }

  if (error && !performanceData) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <h2 className="text-h3 text-red-400 mb-4">Operations System Error</h2>
          <p className="text-body text-secondary mb-6">{error}</p>
          <button 
            onClick={fetchAllData}
            className="linear-button-primary py-2 px-4"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-h1">🚀 Operations & Monitoring</h1>
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
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-small text-secondary">Auto Refresh</span>
              </label>
              <button
                onClick={fetchAllData}
                disabled={loading}
                className="linear-button-secondary py-2 px-4 disabled:opacity-50"
              >
                {loading ? 'Updating...' : 'Refresh Now'}
              </button>
            </div>
          </div>
        </div>

        {/* System Overview */}
        {systemOverview && (
          <div className="linear-card mb-8">
            <h2 className="text-h3 mb-6">🏥 System Health Overview</h2>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="glass-light p-6 rounded-lg">
                <h3 className="text-body font-medium text-white mb-4">System Status</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Overall Status:</span>
                    <span className={`text-small font-medium ${getStatusColor(systemOverview.system_status)}`}>
                      {systemOverview.system_status?.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Uptime:</span>
                    <span className="text-small text-white">{systemOverview.uptime}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Environment:</span>
                    <span className="text-small text-blue-400">{systemOverview.environment}</span>
                  </div>
                </div>
              </div>

              <div className="glass-light p-6 rounded-lg">
                <h3 className="text-body font-medium text-white mb-4">Services Status</h3>
                <div className="space-y-2">
                  {Object.entries(systemOverview.services).map(([service, status]) => (
                    <div key={service} className="flex justify-between items-center">
                      <span className="text-small text-secondary">{service}:</span>
                      <div className="flex items-center space-x-2">
                        <span className="text-lg">{getServiceStatusIcon(status)}</span>
                        <span className={`text-small ${status ? 'text-green-400' : 'text-red-400'}`}>
                          {status ? 'Online' : 'Offline'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="glass-light p-6 rounded-lg">
                <h3 className="text-body font-medium text-white mb-4">Active Alerts</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Total Alerts:</span>
                    <span className="text-small text-white">{systemOverview.alerts_summary.active_alerts}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Critical:</span>
                    <span className="text-small text-red-400">{systemOverview.alerts_summary.critical_alerts}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-small text-secondary">Warnings:</span>
                    <span className="text-small text-yellow-400">{systemOverview.alerts_summary.warning_alerts}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Performance Metrics */}
        {performanceData && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
            {/* System Performance */}
            <div className="linear-card">
              <h2 className="text-h3 mb-6">💻 System Performance</h2>
              <div className="space-y-4">
                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">CPU Usage</span>
                    <span className="text-small text-white">{performanceData.system.cpu_percent.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        performanceData.system.cpu_percent > 80 ? 'bg-red-400' :
                        performanceData.system.cpu_percent > 60 ? 'bg-yellow-400' : 'bg-green-400'
                      }`}
                      style={{ width: `${Math.min(performanceData.system.cpu_percent, 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Memory Usage</span>
                    <span className="text-small text-white">{performanceData.system.memory_percent.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        performanceData.system.memory_percent > 85 ? 'bg-red-400' :
                        performanceData.system.memory_percent > 70 ? 'bg-yellow-400' : 'bg-green-400'
                      }`}
                      style={{ width: `${Math.min(performanceData.system.memory_percent, 100)}%` }}
                    ></div>
                  </div>
                  <div className="text-xs text-secondary mt-1">
                    {(performanceData.system.memory_used_mb / 1024).toFixed(1)} GB used
                  </div>
                </div>

                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Disk Usage</span>
                    <span className="text-small text-white">{performanceData.system.disk_percent.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        performanceData.system.disk_percent > 90 ? 'bg-red-400' :
                        performanceData.system.disk_percent > 75 ? 'bg-yellow-400' : 'bg-green-400'
                      }`}
                      style={{ width: `${Math.min(performanceData.system.disk_percent, 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">Processes</p>
                    <p className="text-sm font-medium text-white">{performanceData.system.process_count}</p>
                  </div>
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">Load Avg</p>
                    <p className="text-sm font-medium text-white">
                      {performanceData.system.load_average[0]?.toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Application Performance */}
            <div className="linear-card">
              <h2 className="text-h3 mb-6">⚡ Application Performance</h2>
              <div className="space-y-4">
                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Response Time</span>
                    <span className="text-small text-white">{performanceData.application.response_time_avg_ms.toFixed(0)}ms</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        performanceData.application.response_time_avg_ms > 1000 ? 'bg-red-400' :
                        performanceData.application.response_time_avg_ms > 500 ? 'bg-yellow-400' : 'bg-green-400'
                      }`}
                      style={{ width: `${Math.min(performanceData.application.response_time_avg_ms / 10, 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Error Rate</span>
                    <span className="text-small text-white">{performanceData.application.error_rate_percent.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        performanceData.application.error_rate_percent > 5 ? 'bg-red-400' :
                        performanceData.application.error_rate_percent > 1 ? 'bg-yellow-400' : 'bg-green-400'
                      }`}
                      style={{ width: `${Math.min(performanceData.application.error_rate_percent * 20, 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">Connections</p>
                    <p className="text-sm font-medium text-white">{performanceData.application.active_connections}</p>
                  </div>
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">Cache Hit</p>
                    <p className="text-sm font-medium text-white">{(performanceData.application.cache_hit_rate * 100).toFixed(1)}%</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">Requests/min</p>
                    <p className="text-sm font-medium text-white">{performanceData.application.api_requests_per_minute}</p>
                  </div>
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">Queue Size</p>
                    <p className="text-sm font-medium text-white">{performanceData.application.queue_size}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Trading Performance */}
            <div className="linear-card">
              <h2 className="text-h3 mb-6">📈 Trading Performance</h2>
              <div className="space-y-4">
                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Trading Latency</span>
                    <span className="text-small text-white">{performanceData.trading.latency_ms.toFixed(0)}ms</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        performanceData.trading.latency_ms > 500 ? 'bg-red-400' :
                        performanceData.trading.latency_ms > 200 ? 'bg-yellow-400' : 'bg-green-400'
                      }`}
                      style={{ width: `${Math.min(performanceData.trading.latency_ms / 5, 100)}%` }}
                    ></div>
                  </div>
                </div>

                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Success Rate</span>
                    <span className="text-small text-white">{(performanceData.trading.success_rate * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        performanceData.trading.success_rate < 0.5 ? 'bg-red-400' :
                        performanceData.trading.success_rate < 0.8 ? 'bg-yellow-400' : 'bg-green-400'
                      }`}
                      style={{ width: `${performanceData.trading.success_rate * 100}%` }}
                    ></div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">Active Positions</p>
                    <p className="text-sm font-medium text-white">{performanceData.trading.active_positions}</p>
                  </div>
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">Strategies</p>
                    <p className="text-sm font-medium text-white">{performanceData.trading.strategy_count}</p>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">P&L (1h)</p>
                    <p className={`text-sm font-medium ${
                      performanceData.trading.pnl_last_hour >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      ${performanceData.trading.pnl_last_hour.toFixed(2)}
                    </p>
                  </div>
                  <div className="glass-light p-3 rounded text-center">
                    <p className="text-xs text-secondary mb-1">Risk Score</p>
                    <p className={`text-sm font-medium ${
                      performanceData.trading.risk_score > 7 ? 'text-red-400' :
                      performanceData.trading.risk_score > 5 ? 'text-yellow-400' : 'text-green-400'
                    }`}>
                      {performanceData.trading.risk_score.toFixed(1)}/10
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Network & Database Metrics */}
        {performanceData && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            <div className="linear-card">
              <h2 className="text-h3 mb-6">🌐 Network Metrics</h2>
              <div className="space-y-4">
                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Network Sent</span>
                    <span className="text-small text-white">{performanceData.system.network_sent_mb.toFixed(2)} MB</span>
                  </div>
                </div>
                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Network Received</span>
                    <span className="text-small text-white">{performanceData.system.network_recv_mb.toFixed(2)} MB</span>
                  </div>
                </div>
                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Active Connections</span>
                    <span className="text-small text-white">{performanceData.application.active_connections}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="linear-card">
              <h2 className="text-h3 mb-6">🗄️ Database Metrics</h2>
              <div className="space-y-4">
                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">DB Connections</span>
                    <span className="text-small text-white">{performanceData.application.database_connections}</span>
                  </div>
                </div>
                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">App Memory</span>
                    <span className="text-small text-white">{performanceData.application.memory_usage_mb.toFixed(1)} MB</span>
                  </div>
                </div>
                <div className="glass-light p-4 rounded-lg">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-small text-secondary">Trading Volume</span>
                    <span className="text-small text-white">${performanceData.trading.volume_traded.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Recent Trading Activity */}
        <div className="linear-card">
          <h2 className="text-h3 mb-6">⚡ Real-time Trading Activity</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="glass-light p-4 rounded-lg text-center">
              <p className="text-small text-secondary mb-1">Orders/minute</p>
              <p className="text-h4 font-medium text-white">
                {performanceData?.trading.orders_per_minute || 0}
              </p>
              <p className="text-xs text-green-400">Real-time</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <p className="text-small text-secondary mb-1">Success Rate</p>
              <p className="text-h4 font-medium text-green-400">
                {((performanceData?.trading.success_rate || 0) * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-secondary">Last hour</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <p className="text-small text-secondary mb-1">Avg Latency</p>
              <p className="text-h4 font-medium text-blue-400">
                {performanceData?.trading.latency_ms.toFixed(0)}ms
              </p>
              <p className="text-xs text-secondary">BingX API</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <p className="text-small text-secondary mb-1">Active Alerts</p>
              <p className="text-h4 font-medium text-yellow-400">
                {performanceData?.active_alerts || 0}
              </p>
              <p className="text-xs text-secondary">Monitoring</p>
            </div>
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="linear-card border border-red-500/30 bg-red-500/10">
            <div className="flex items-center space-x-3">
              <div className="text-2xl">🚨</div>
              <div>
                <h3 className="text-body font-medium text-red-400">System Error</h3>
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
      </div>
    </div>
  );
}