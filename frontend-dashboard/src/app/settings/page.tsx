"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@clerk/nextjs';
import { useTranslation } from 'react-i18next';

interface UserSettings {
  user_id?: string;
  language: string;
  theme: string;
  currency: string;
  timezone: string;
  notifications: {
    email_enabled: boolean;
    push_enabled: boolean;
    trade_alerts: boolean;
    risk_alerts: boolean;
    system_alerts: boolean;
  };
  trading: {
    default_exchange: string;
    auto_execute_trades: boolean;
    max_concurrent_trades: number;
    default_stop_loss: number;
    default_take_profit: number;
    slippage_tolerance: number;
  };
  dashboard: {
    auto_refresh_interval: number;
    show_advanced_metrics: boolean;
    chart_theme: string;
    default_timeframe: string;
  };
}

export default function SettingsPage() {
  const { getToken } = useAuth();
  const { t, i18n } = useTranslation();
  
  const [settings, setSettings] = useState<UserSettings>({
    language: 'en',
    theme: 'dark',
    currency: 'USD',
    timezone: 'UTC',
    notifications: {
      email_enabled: true,
      push_enabled: true,
      trade_alerts: true,
      risk_alerts: true,
      system_alerts: false,
    },
    trading: {
      default_exchange: 'binance',
      auto_execute_trades: false,
      max_concurrent_trades: 5,
      default_stop_loss: 2.0,
      default_take_profit: 5.0,
      slippage_tolerance: 0.5,
    },
    dashboard: {
      auto_refresh_interval: 30,
      show_advanced_metrics: true,
      chart_theme: 'dark',
      default_timeframe: '1h',
    },
  });
  
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [exchanges, setExchanges] = useState<string[]>([]);

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
    fetchExchanges();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      // For now, we'll use mock data since there's no backend endpoint yet
      // In production, this would fetch from /api/user/settings
      
      // Apply the current language from i18n
      setSettings(prev => ({
        ...prev,
        language: i18n.language
      }));
    } catch (e: any) {
      setError(`Error fetching settings: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchExchanges = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/exchanges');
      if (response.ok) {
        const data = await response.json();
        setExchanges(data);
      }
    } catch (e: any) {
      console.error('Error fetching exchanges:', e);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    
    try {
      // Apply language change immediately
      if (settings.language !== i18n.language) {
        await i18n.changeLanguage(settings.language);
      }
      
      // For now, we'll just simulate saving to localStorage
      // In production, this would POST to /api/user/settings
      localStorage.setItem('user_settings', JSON.stringify(settings));
      
      setSuccess('Settings saved successfully!');
      setTimeout(() => setSuccess(null), 3000);
    } catch (e: any) {
      setError(`Error saving settings: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const resetToDefaults = () => {
    setSettings({
      language: 'en',
      theme: 'dark',
      currency: 'USD',
      timezone: 'UTC',
      notifications: {
        email_enabled: true,
        push_enabled: true,
        trade_alerts: true,
        risk_alerts: true,
        system_alerts: false,
      },
      trading: {
        default_exchange: 'binance',
        auto_execute_trades: false,
        max_concurrent_trades: 5,
        default_stop_loss: 2.0,
        default_take_profit: 5.0,
        slippage_tolerance: 0.5,
      },
      dashboard: {
        auto_refresh_interval: 30,
        show_advanced_metrics: true,
        chart_theme: 'dark',
        default_timeframe: '1h',
      },
    });
  };

  const handleInputChange = (section: keyof UserSettings, field: string, value: any) => {
    setSettings(prev => ({
      ...prev,
      [section]: typeof prev[section] === 'object' && prev[section] !== null
        ? { ...prev[section], [field]: value }
        : value
    }));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card text-center">
          <p className="text-body">Loading settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-h1 text-center mb-12">User Settings</h1>

        {error && (
          <div className="linear-card bg-red-900/20 border-red-500/20 mb-6">
            <p className="text-red-400">{error}</p>
            <button onClick={() => setError(null)} className="linear-button-secondary mt-2">
              Dismiss
            </button>
          </div>
        )}

        {success && (
          <div className="linear-card bg-green-900/20 border-green-500/20 mb-6">
            <p className="text-green-400">{success}</p>
          </div>
        )}

        <div className="space-y-8">
          {/* General Settings */}
          <div className="linear-card">
            <h2 className="text-h3 mb-6">General Settings</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-small mb-2">Language</label>
                <select
                  value={settings.language}
                  onChange={(e) => handleInputChange('language', '', e.target.value)}
                  className="linear-select w-full"
                >
                  <option value="en">English</option>
                </select>
              </div>
              
              <div>
                <label className="block text-small mb-2">Theme</label>
                <select
                  value={settings.theme}
                  onChange={(e) => handleInputChange('theme', '', e.target.value)}
                  className="linear-select w-full"
                >
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                  <option value="auto">System</option>
                </select>
              </div>

              <div>
                <label className="block text-small mb-2">Currency</label>
                <select
                  value={settings.currency}
                  onChange={(e) => handleInputChange('currency', '', e.target.value)}
                  className="linear-select w-full"
                >
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                  <option value="KRW">KRW</option>
                  <option value="JPY">JPY</option>
                </select>
              </div>

              <div>
                <label className="block text-small mb-2">Timezone</label>
                <select
                  value={settings.timezone}
                  onChange={(e) => handleInputChange('timezone', '', e.target.value)}
                  className="linear-select w-full"
                >
                  <option value="UTC">UTC</option>
                  <option value="America/New_York">New York</option>
                  <option value="Europe/London">London</option>
                  <option value="Asia/Tokyo">Tokyo</option>
                  <option value="Asia/Seoul">Seoul</option>
                </select>
              </div>
            </div>
          </div>

          {/* Notification Settings */}
          <div className="linear-card">
            <h2 className="text-h3 mb-6">Notification Settings</h2>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-body">Email Notifications</p>
                  <p className="text-small text-secondary">Receive notifications via email</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifications.email_enabled}
                    onChange={(e) => handleInputChange('notifications', 'email_enabled', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-body">Push Notifications</p>
                  <p className="text-small text-secondary">Receive browser push notifications</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifications.push_enabled}
                    onChange={(e) => handleInputChange('notifications', 'push_enabled', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-body">Trade Alerts</p>
                  <p className="text-small text-secondary">Notifications for completed trades</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifications.trade_alerts}
                    onChange={(e) => handleInputChange('notifications', 'trade_alerts', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-body">Risk Alerts</p>
                  <p className="text-small text-secondary">Notifications for high-risk situations</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifications.risk_alerts}
                    onChange={(e) => handleInputChange('notifications', 'risk_alerts', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-body">System Alerts</p>
                  <p className="text-small text-secondary">Notifications for system updates and maintenance</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.notifications.system_alerts}
                    onChange={(e) => handleInputChange('notifications', 'system_alerts', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
            </div>
          </div>

          {/* Trading Settings */}
          <div className="linear-card">
            <h2 className="text-h3 mb-6">Trading Settings</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-small mb-2">Default Exchange</label>
                <select
                  value={settings.trading.default_exchange}
                  onChange={(e) => handleInputChange('trading', 'default_exchange', e.target.value)}
                  className="linear-select w-full"
                >
                  {exchanges.map(exchange => (
                    <option key={exchange} value={exchange}>{exchange}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-small mb-2">Max Concurrent Trades</label>
                <input
                  type="number"
                  value={settings.trading.max_concurrent_trades}
                  onChange={(e) => handleInputChange('trading', 'max_concurrent_trades', parseInt(e.target.value))}
                  className="linear-input w-full"
                  min="1"
                  max="20"
                />
              </div>

              <div>
                <label className="block text-small mb-2">Default Stop Loss (%)</label>
                <input
                  type="number"
                  value={settings.trading.default_stop_loss}
                  onChange={(e) => handleInputChange('trading', 'default_stop_loss', parseFloat(e.target.value))}
                  className="linear-input w-full"
                  min="0.1"
                  max="10"
                  step="0.1"
                />
              </div>

              <div>
                <label className="block text-small mb-2">Default Take Profit (%)</label>
                <input
                  type="number"
                  value={settings.trading.default_take_profit}
                  onChange={(e) => handleInputChange('trading', 'default_take_profit', parseFloat(e.target.value))}
                  className="linear-input w-full"
                  min="1"
                  max="50"
                  step="0.1"
                />
              </div>

              <div>
                <label className="block text-small mb-2">Slippage Tolerance (%)</label>
                <input
                  type="number"
                  value={settings.trading.slippage_tolerance}
                  onChange={(e) => handleInputChange('trading', 'slippage_tolerance', parseFloat(e.target.value))}
                  className="linear-input w-full"
                  min="0.1"
                  max="5"
                  step="0.1"
                />
              </div>

              <div className="flex items-center justify-between md:col-span-2">
                <div>
                  <p className="text-body">Auto Execute Trades</p>
                  <p className="text-small text-secondary">Automatically execute trades based on strategy signals</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.trading.auto_execute_trades}
                    onChange={(e) => handleInputChange('trading', 'auto_execute_trades', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
            </div>
          </div>

          {/* Dashboard Settings */}
          <div className="linear-card">
            <h2 className="text-h3 mb-6">Dashboard Settings</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-small mb-2">Auto Refresh Interval (seconds)</label>
                <select
                  value={settings.dashboard.auto_refresh_interval}
                  onChange={(e) => handleInputChange('dashboard', 'auto_refresh_interval', parseInt(e.target.value))}
                  className="linear-select w-full"
                >
                  <option value={10}>10 seconds</option>
                  <option value={30}>30 seconds</option>
                  <option value={60}>1 minute</option>
                  <option value={300}>5 minutes</option>
                </select>
              </div>

              <div>
                <label className="block text-small mb-2">Default Chart Timeframe</label>
                <select
                  value={settings.dashboard.default_timeframe}
                  onChange={(e) => handleInputChange('dashboard', 'default_timeframe', e.target.value)}
                  className="linear-select w-full"
                >
                  <option value="1m">1 minute</option>
                  <option value="5m">5 minutes</option>
                  <option value="15m">15 minutes</option>
                  <option value="1h">1 hour</option>
                  <option value="4h">4 hours</option>
                  <option value="1d">1 day</option>
                </select>
              </div>

              <div>
                <label className="block text-small mb-2">Chart Theme</label>
                <select
                  value={settings.dashboard.chart_theme}
                  onChange={(e) => handleInputChange('dashboard', 'chart_theme', e.target.value)}
                  className="linear-select w-full"
                >
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                </select>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-body">Show Advanced Metrics</p>
                  <p className="text-small text-secondary">Display advanced trading metrics in dashboard</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.dashboard.show_advanced_metrics}
                    onChange={(e) => handleInputChange('dashboard', 'show_advanced_metrics', e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col sm:flex-row gap-4 justify-between">
            <button
              onClick={resetToDefaults}
              className="linear-button-secondary py-3 px-6"
            >
              Reset to Defaults
            </button>
            
            <div className="flex gap-4">
              <button
                onClick={saveSettings}
                disabled={saving}
                className="linear-button-primary py-3 px-8 disabled:opacity-50"
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