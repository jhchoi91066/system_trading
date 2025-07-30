"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@clerk/nextjs';

interface FundManagementSettings {
  user_id?: string;
  total_capital: number;
  max_risk_per_trade: number;
  max_daily_loss: number;
  max_portfolio_risk: number;
  position_sizing_method: string;
  rebalance_frequency: string;
  emergency_stop_loss: number;
}

interface RiskMetrics {
  current_risk_exposure: number;
  daily_pnl: number;
  max_drawdown: number;
  sharpe_ratio: number;
  win_rate: number;
  profit_factor: number;
  risk_status: string;
  total_allocated: number;
  available_capital: number;
  active_strategies_count: number;
}

export default function FundManagementPage() {
  const { getToken } = useAuth();
  const [settings, setSettings] = useState<FundManagementSettings>({
    total_capital: 10000,
    max_risk_per_trade: 2.0,
    max_daily_loss: 5.0,
    max_portfolio_risk: 10.0,
    position_sizing_method: "fixed",
    rebalance_frequency: "daily",
    emergency_stop_loss: 20.0
  });
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchWithAuth = async (url: string, options?: RequestInit) => {
    const token = await getToken();
    const headers = {
      ...(options?.headers || {}),
      'Authorization': `Bearer ${token}`,
    };
    return fetch(url, { ...options, headers });
  };

  useEffect(() => {
    fetchSettings();
    fetchRiskMetrics();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/fund-management/settings');
      if (response.ok) {
        const data = await response.json();
        setSettings(data);
      } else {
        setError('Failed to fetch fund management settings');
      }
    } catch (e: any) {
      setError(`Error fetching settings: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchRiskMetrics = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/fund-management/risk-metrics');
      if (response.ok) {
        const data = await response.json();
        setRiskMetrics(data);
      }
    } catch (e: any) {
      console.error('Error fetching risk metrics:', e);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    setError(null);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/fund-management/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });

      if (response.ok) {
        const result = await response.json();
        alert('Settings saved successfully!');
        fetchRiskMetrics(); // Refresh risk metrics after saving
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to save settings');
      }
    } catch (e: any) {
      setError(`Error saving settings: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const rebalancePortfolio = async () => {
    setSaving(true);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/fund-management/rebalance', {
        method: 'POST'
      });

      if (response.ok) {
        const result = await response.json();
        alert(`${result.message}\nChanges: ${result.changes.length} strategies adjusted`);
        fetchRiskMetrics(); // Refresh metrics after rebalancing
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to rebalance portfolio');
      }
    } catch (e: any) {
      setError(`Error rebalancing: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const getRiskStatusColor = (status: string) => {
    switch (status) {
      case 'SAFE': return 'text-green-400';
      case 'MODERATE_RISK': return 'text-yellow-400';
      case 'HIGH_RISK': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card text-center">
          <p className="text-body">Loading fund management settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-h1 text-center mb-12">Fund Management</h1>

        {error && (
          <div className="linear-card bg-red-900/20 border-red-500/20 mb-6">
            <p className="text-red-400">{error}</p>
            <button onClick={() => setError(null)} className="linear-button-secondary mt-2">
              Dismiss
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Risk Metrics Dashboard */}
          <div className="linear-card">
            <h2 className="text-h3 mb-6">Risk Overview</h2>
            
            {riskMetrics ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="glass-light p-4 rounded-lg text-center">
                    <p className="text-small text-secondary mb-1">Risk Status</p>
                    <p className={`text-h4 font-medium ${getRiskStatusColor(riskMetrics.risk_status)}`}>
                      {riskMetrics.risk_status.replace('_', ' ')}
                    </p>
                  </div>
                  <div className="glass-light p-4 rounded-lg text-center">
                    <p className="text-small text-secondary mb-1">Risk Exposure</p>
                    <p className="text-h4 font-medium text-white">{riskMetrics.current_risk_exposure.toFixed(1)}%</p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="glass-light p-4 rounded-lg text-center">
                    <p className="text-small text-secondary mb-1">Win Rate</p>
                    <p className="text-body font-medium text-green-400">{riskMetrics.win_rate.toFixed(1)}%</p>
                  </div>
                  <div className="glass-light p-4 rounded-lg text-center">
                    <p className="text-small text-secondary mb-1">Sharpe Ratio</p>
                    <p className="text-body font-medium text-blue-400">{riskMetrics.sharpe_ratio.toFixed(2)}</p>
                  </div>
                  <div className="glass-light p-4 rounded-lg text-center">
                    <p className="text-small text-secondary mb-1">Profit Factor</p>
                    <p className="text-body font-medium text-yellow-400">{riskMetrics.profit_factor.toFixed(2)}</p>
                  </div>
                </div>

                <div className="glass-medium p-4 rounded-lg">
                  <h4 className="text-small font-medium text-white mb-3">Capital Allocation</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-small text-secondary">Total Allocated</p>
                      <p className="text-body font-medium text-white">${riskMetrics.total_allocated.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-small text-secondary">Available</p>
                      <p className="text-body font-medium text-green-400">${riskMetrics.available_capital.toLocaleString()}</p>
                    </div>
                  </div>
                </div>

                <button
                  onClick={rebalancePortfolio}
                  disabled={saving || riskMetrics.active_strategies_count === 0}
                  className="linear-button-primary w-full py-3 disabled:opacity-50"
                >
                  {saving ? 'Rebalancing...' : 'Rebalance Portfolio'}
                </button>
              </div>
            ) : (
              <p className="text-small text-secondary">Loading risk metrics...</p>
            )}
          </div>

          {/* Fund Management Settings */}
          <div className="linear-card">
            <h2 className="text-h3 mb-6">Settings</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-small mb-2">Total Capital ($)</label>
                <input
                  type="number"
                  value={settings.total_capital}
                  onChange={(e) => setSettings(prev => ({ ...prev, total_capital: parseFloat(e.target.value) }))}
                  className="linear-input w-full"
                  min="1000"
                  step="100"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-small mb-2">Max Risk Per Trade (%)</label>
                  <input
                    type="number"
                    value={settings.max_risk_per_trade}
                    onChange={(e) => setSettings(prev => ({ ...prev, max_risk_per_trade: parseFloat(e.target.value) }))}
                    className="linear-input w-full"
                    min="0.1"
                    max="10"
                    step="0.1"
                  />
                </div>
                <div>
                  <label className="block text-small mb-2">Max Daily Loss (%)</label>
                  <input
                    type="number"
                    value={settings.max_daily_loss}
                    onChange={(e) => setSettings(prev => ({ ...prev, max_daily_loss: parseFloat(e.target.value) }))}
                    className="linear-input w-full"
                    min="1"
                    max="20"
                    step="0.5"
                  />
                </div>
              </div>

              <div>
                <label className="block text-small mb-2">Max Portfolio Risk (%)</label>
                <input
                  type="number"
                  value={settings.max_portfolio_risk}
                  onChange={(e) => setSettings(prev => ({ ...prev, max_portfolio_risk: parseFloat(e.target.value) }))}
                  className="linear-input w-full"
                  min="5"
                  max="50"
                  step="1"
                />
              </div>

              <div>
                <label className="block text-small mb-2">Position Sizing Method</label>
                <select
                  value={settings.position_sizing_method}
                  onChange={(e) => setSettings(prev => ({ ...prev, position_sizing_method: e.target.value }))}
                  className="linear-select w-full"
                >
                  <option value="fixed">Fixed Amount</option>
                  <option value="kelly">Kelly Criterion</option>
                  <option value="optimal_f">Optimal F</option>
                </select>
              </div>

              <div>
                <label className="block text-small mb-2">Rebalance Frequency</label>
                <select
                  value={settings.rebalance_frequency}
                  onChange={(e) => setSettings(prev => ({ ...prev, rebalance_frequency: e.target.value }))}
                  className="linear-select w-full"
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>

              <div>
                <label className="block text-small mb-2">Emergency Stop Loss (%)</label>
                <input
                  type="number"
                  value={settings.emergency_stop_loss}
                  onChange={(e) => setSettings(prev => ({ ...prev, emergency_stop_loss: parseFloat(e.target.value) }))}
                  className="linear-input w-full"
                  min="10"
                  max="50"
                  step="1"
                />
                <p className="text-xs text-secondary mt-1">
                  Automatically liquidate all positions if total loss exceeds this percentage
                </p>
              </div>

              <button
                onClick={saveSettings}
                disabled={saving}
                className="linear-button-primary w-full py-3 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}