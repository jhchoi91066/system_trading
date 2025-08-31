"use client";

import { useEffect, useState } from 'react';
import { useWebSocket } from '@/contexts/WebSocketProvider';

interface Alert {
  id: string;
  type: string;
  level: string;
  message: string;
  timestamp: string;
  resolved: boolean;
  acknowledged: boolean;
  metadata?: Record<string, any>;
}

interface AlertStats {
  total_alerts: number;
  active_alerts: number;
  critical_alerts: number;
  warning_alerts: number;
  resolved_today: number;
  avg_resolution_time: number;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertStats, setAlertStats] = useState<AlertStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'active' | 'critical' | 'resolved'>('active');
  const [lastUpdateTime, setLastUpdateTime] = useState<string>('');

  const { isConnected: wsConnected } = useWebSocket();

  const fetchAlerts = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/operations/alerts/active');
      if (response.ok) {
        const data = await response.json();
        setAlerts(data.alerts || []);
        setAlertStats(data.stats || null);
        setError(null);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (err) {
      setError(`Alerts API: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const acknowledgeAlert = async (alertId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/operations/alerts/${alertId}/acknowledge`, {
        method: 'POST'
      });
      if (response.ok) {
        await fetchAlerts(); // Refresh alerts
      }
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  const resolveAlert = async (alertId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/operations/alerts/${alertId}/resolve`, {
        method: 'POST'
      });
      if (response.ok) {
        await fetchAlerts(); // Refresh alerts
      }
    } catch (err) {
      console.error('Failed to resolve alert:', err);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchAlerts();
      setLoading(false);
      setLastUpdateTime(new Date().toLocaleTimeString());
    };

    loadData();

    // Auto-refresh every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const getAlertLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'critical': return 'text-red-400 bg-red-500/20';
      case 'warning': return 'text-yellow-400 bg-yellow-500/20';
      case 'info': return 'text-blue-400 bg-blue-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const getAlertIcon = (level: string) => {
    switch (level.toLowerCase()) {
      case 'critical': return '🚨';
      case 'warning': return '⚠️';
      case 'info': return 'ℹ️';
      default: return '📊';
    }
  };

  const filteredAlerts = alerts.filter(alert => {
    switch (filter) {
      case 'active': return !alert.resolved;
      case 'critical': return alert.level.toLowerCase() === 'critical' && !alert.resolved;
      case 'resolved': return alert.resolved;
      default: return true;
    }
  });

  if (loading && alerts.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400 mx-auto mb-4"></div>
          <p className="text-body text-secondary">Loading Alert System...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-h1">🚨 Alert Management</h1>
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-3">
              <div className={`w-3 h-3 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-red-400'}`}></div>
              <span className="text-small text-secondary">
                {wsConnected ? 'Live Monitoring' : 'Disconnected'}
              </span>
              {lastUpdateTime && (
                <span className="text-xs text-gray-400">
                  Last: {lastUpdateTime}
                </span>
              )}
            </div>
            <button
              onClick={fetchAlerts}
              disabled={loading}
              className="linear-button-secondary py-2 px-4 disabled:opacity-50"
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Alert Statistics */}
        {alertStats && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-8">
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Total Alerts</p>
              <p className="text-h4 font-medium text-white">{alertStats.total_alerts}</p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Active</p>
              <p className="text-h4 font-medium text-blue-400">{alertStats.active_alerts}</p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Critical</p>
              <p className="text-h4 font-medium text-red-400">{alertStats.critical_alerts}</p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Warnings</p>
              <p className="text-h4 font-medium text-yellow-400">{alertStats.warning_alerts}</p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Resolved Today</p>
              <p className="text-h4 font-medium text-green-400">{alertStats.resolved_today}</p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Avg Resolution</p>
              <p className="text-h4 font-medium text-white">{alertStats.avg_resolution_time.toFixed(0)}min</p>
            </div>
          </div>
        )}

        {/* Alert Filters */}
        <div className="flex space-x-4 mb-6">
          {[
            { key: 'all', label: 'All Alerts', count: alerts.length },
            { key: 'active', label: 'Active', count: alerts.filter(a => !a.resolved).length },
            { key: 'critical', label: 'Critical', count: alerts.filter(a => a.level.toLowerCase() === 'critical' && !a.resolved).length },
            { key: 'resolved', label: 'Resolved', count: alerts.filter(a => a.resolved).length }
          ].map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setFilter(key as any)}
              className={`px-4 py-2 rounded-lg text-small transition-colors ${
                filter === key
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {label} ({count})
            </button>
          ))}
        </div>

        {/* Alerts List */}
        <div className="space-y-4">
          {filteredAlerts.length > 0 ? (
            filteredAlerts.map((alert) => (
              <div
                key={alert.id}
                className={`linear-card border-l-4 ${
                  alert.level.toLowerCase() === 'critical' ? 'border-red-400' :
                  alert.level.toLowerCase() === 'warning' ? 'border-yellow-400' :
                  'border-blue-400'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-3">
                      <span className="text-xl">{getAlertIcon(alert.level)}</span>
                      <div>
                        <h3 className="text-body font-medium text-white">{alert.type}</h3>
                        <div className="flex items-center space-x-3">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getAlertLevelColor(alert.level)}`}>
                            {alert.level.toUpperCase()}
                          </span>
                          <span className="text-xs text-secondary">
                            {new Date(alert.timestamp).toLocaleString()}
                          </span>
                          {alert.acknowledged && (
                            <span className="text-xs text-green-400">Acknowledged</span>
                          )}
                          {alert.resolved && (
                            <span className="text-xs text-blue-400">Resolved</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <p className="text-small text-secondary mb-3">{alert.message}</p>
                    
                    {alert.metadata && Object.keys(alert.metadata).length > 0 && (
                      <div className="glass-light p-3 rounded-lg">
                        <h4 className="text-xs font-medium text-white mb-2">Additional Details:</h4>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          {Object.entries(alert.metadata).map(([key, value]) => (
                            <div key={key} className="flex justify-between">
                              <span className="text-secondary">{key}:</span>
                              <span className="text-white">{String(value)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {!alert.resolved && (
                    <div className="flex flex-col space-y-2 ml-4">
                      {!alert.acknowledged && (
                        <button
                          onClick={() => acknowledgeAlert(alert.id)}
                          className="linear-button-secondary text-xs py-1 px-3"
                        >
                          Acknowledge
                        </button>
                      )}
                      <button
                        onClick={() => resolveAlert(alert.id)}
                        className="linear-button-primary text-xs py-1 px-3"
                      >
                        Resolve
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          ) : (
            <div className="linear-card text-center py-12">
              <div className="text-4xl mb-4">
                {filter === 'active' ? '✅' : filter === 'critical' ? '🎉' : '📊'}
              </div>
              <h3 className="text-body font-medium text-white mb-2">
                {filter === 'active' ? 'No Active Alerts' :
                 filter === 'critical' ? 'No Critical Alerts' :
                 filter === 'resolved' ? 'No Resolved Alerts' :
                 'No Alerts Found'}
              </h3>
              <p className="text-small text-secondary">
                {filter === 'active' ? 'All systems are running smoothly!' :
                 filter === 'critical' ? 'No critical issues detected.' :
                 'No alerts match the current filter.'}
              </p>
            </div>
          )}
        </div>

        {/* Error State */}
        {error && (
          <div className="linear-card border border-red-500/30 bg-red-500/10 mt-8">
            <div className="flex items-center space-x-3">
              <div className="text-2xl">🚨</div>
              <div>
                <h3 className="text-body font-medium text-red-400">Alert System Error</h3>
                <p className="text-small text-secondary">{error}</p>
                <button 
                  onClick={fetchAlerts}
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