"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@clerk/nextjs';

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<any[]>([]);
  const [activeStrategies, setActiveStrategies] = useState<any[]>([]);
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [loadingFetch, setLoadingFetch] = useState(false); // For initial fetches
  const [loadingAction, setLoadingAction] = useState(false); // For create/activate/deactivate actions
  const [error, setError] = useState<string | null>(null);
  
  // 고급 기능 상태
  const [advancedFeaturesEnabled, setAdvancedFeaturesEnabled] = useState(false);
  const [portfolioOverview, setPortfolioOverview] = useState<any>(null);
  const [optimizationResults, setOptimizationResults] = useState<any>(null);
  const [showOptimizeModal, setShowOptimizeModal] = useState(false);
  const [selectedStrategyForOptimization, setSelectedStrategyForOptimization] = useState<any>(null);
  
  const { getToken } = useAuth();

  const strategyParameterConfigs: { [key: string]: { name: string; label: string; type: string; defaultValue: any; options?: string[]; }[] } = {
    CCI: [
      { name: 'window', label: 'Window Period', type: 'number', defaultValue: 20 },
      { name: 'buy_threshold', label: 'Buy Threshold', type: 'number', defaultValue: -100 },
      { name: 'sell_threshold', label: 'Sell Threshold', type: 'number', defaultValue: 100 },
      { name: 'timeframe', label: 'Timeframe', type: 'select', options: ['1m', '5m', '15m', '1h', '4h', '1d'], defaultValue: '1h' },
    ],
    MACD: [
      { name: 'fast_period', label: 'Fast Period', type: 'number', defaultValue: 12 },
      { name: 'slow_period', label: 'Slow Period', type: 'number', defaultValue: 26 },
      { name: 'signal_period', label: 'Signal Period', type: 'number', defaultValue: 9 },
      { name: 'timeframe', label: 'Timeframe', type: 'select', options: ['1m', '5m', '15m', '1h', '4h', '1d'], defaultValue: '1h' },
    ],
    RSI: [
      { name: 'window', label: 'Window Period', type: 'number', defaultValue: 14 },
      { name: 'buy_threshold', label: 'Buy Threshold', type: 'number', defaultValue: 30 },
      { name: 'sell_threshold', label: 'Sell Threshold', type: 'number', defaultValue: 70 },
      { name: 'timeframe', label: 'Timeframe', type: 'select', options: ['1m', '5m', '15m', '1h', '4h', '1d'], defaultValue: '1h' },
    ],
    SMA: [
      { name: 'short_window', label: 'Short Window', type: 'number', defaultValue: 10 },
      { name: 'long_window', label: 'Long Window', type: 'number', defaultValue: 50 },
      { name: 'timeframe', label: 'Timeframe', type: 'select', options: ['1m', '5m', '15m', '1h', '4h', '1d'], defaultValue: '1h' },
    ],
    Bollinger: [
      { name: 'window', label: 'Window Period', type: 'number', defaultValue: 20 },
      { name: 'std_dev', label: 'Standard Deviations', type: 'number', defaultValue: 2 },
      { name: 'timeframe', label: 'Timeframe', type: 'select', options: ['1m', '5m', '15m', '1h', '4h', '1d'], defaultValue: '1h' },
    ],
    custom: [], // No specific parameters for custom
  };

  const fetchWithAuth = async (url: string, options?: RequestInit) => {
    const token = await getToken();
    const headers = {
      ...(options?.headers || {}),
      'Authorization': `Bearer ${token}`,
    };
    return fetch(url, { ...options, headers });
  };

  // Form states
  const [showActivateForm, setShowActivateForm] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedStrategy, setSelectedStrategy] = useState<any>(null);
  const [activateForm, setActivateForm] = useState({
    exchange_name: 'binance',
    symbol: 'BTC/USDT',
    allocated_capital: 1000,
    stop_loss_percentage: 5.0,
    take_profit_percentage: 10.0,
    max_position_size: 0.1, // Maximum position size as percentage of capital
    risk_per_trade: 2.0, // Risk per trade as percentage
    daily_loss_limit: 5.0 // Daily loss limit as percentage
  });
  
  // Create strategy form
  const [createForm, setCreateForm] = useState({
    name: '',
    description: '',
    strategy_type: 'CCI', // Default to CCI
    parameters: strategyParameterConfigs.CCI.reduce((acc, param) => ({ ...acc, [param.name]: param.defaultValue }), {}),
    script: ''
  });
  
  // Portfolio allocation tracking
  const [portfolioStats, setPortfolioStats] = useState({
    total_allocated: 0,
    available_capital: 10000, // This would come from user settings
    active_positions: 0,
    daily_pnl: 0
  });

  useEffect(() => {
    fetchStrategies();
    fetchActiveStrategies();
    fetchExchanges();
    fetchPortfolioStats();
    checkAdvancedFeatures();
    fetchDashboardOverview();
  }, []);

  const checkAdvancedFeatures = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/advanced/status');
      if (response.ok) {
        const data = await response.json();
        setAdvancedFeaturesEnabled(data.enabled);
      }
    } catch (e) {
      console.log('Advanced features not available');
    }
  };

  const fetchDashboardOverview = async () => {
    if (!advancedFeaturesEnabled) return;
    
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/api/dashboard/overview');
      if (response.ok) {
        const data = await response.json();
        setPortfolioOverview(data.data);
      }
    } catch (e) {
      console.error('Failed to fetch dashboard overview:', e);
    }
  };

  const optimizeStrategy = async (strategyName: string) => {
    setLoadingAction(true);
    try {
      const parameterRanges = {
        cci_period: [10, 30],
        overbought: [80, 150], 
        oversold: [-150, -80]
      };

      const response = await fetchWithAuth('http://127.0.0.1:8000/api/strategies/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: strategyName,
          parameter_ranges: parameterRanges,
          optimization_method: 'genetic'
        })
      });

      if (response.ok) {
        const data = await response.json();
        setOptimizationResults(data.optimization_result);
        alert(`Optimization completed! Best score: ${data.optimization_result.best_score.toFixed(3)}`);
      }
    } catch (e: any) {
      setError(`Optimization failed: ${e.message}`);
    } finally {
      setLoadingAction(false);
    }
  };
  
  const fetchPortfolioStats = async () => {
    setLoadingFetch(true);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/portfolio/stats');
      if (!response.ok) throw new Error('Failed to fetch portfolio stats');
      const data = await response.json();
      setPortfolioStats(prev => ({
        ...prev,
        total_allocated: data.total_allocated,
        available_capital: data.available_capital,
        active_positions: data.active_strategies
      }));
    } catch (e: any) {
      console.error('Failed to fetch portfolio stats:', e.message);
      setError(`Failed to fetch portfolio stats: ${e.message}`);
    } finally {
      setLoadingFetch(false);
    }
  };

  useEffect(() => {
    if (activateForm.exchange_name) {
      fetchSymbols(activateForm.exchange_name);
    }
  }, [activateForm.exchange_name]);

  const fetchStrategies = async () => {
    setLoadingFetch(true);
    setError(null);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/strategies');
      if (!response.ok) throw new Error('Failed to fetch strategies');
      const data = await response.json();
      setStrategies(data);
    } catch (e: any) {
      setError(`Failed to fetch strategies: ${e.message}`);
    } finally {
      setLoadingFetch(false);
    }
  };
  
  const createStrategy = async () => {
    if (!createForm.name || !createForm.description) {
      setError('Please fill in all required fields');
      return;
    }
    
    setLoadingAction(true);
    try {
      // Generate strategy script based on parameters
      const strategyScript = generateStrategyScript(createForm.strategy_type, createForm.parameters);
      
      const response = await fetchWithAuth('http://127.0.0.1:8000/strategies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: createForm.name,
          script: createForm.script || strategyScript,
          description: createForm.description,
          strategy_type: createForm.strategy_type,
          parameters: createForm.parameters
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create strategy');
      }
      
      const data = await response.json();
      alert(`Strategy "${createForm.name}" created successfully!`);
      setShowCreateForm(false);
      setCreateForm({
        name: '',
        description: '',
        strategy_type: 'CCI',
        parameters: strategyParameterConfigs.CCI.reduce((acc, param) => ({ ...acc, [param.name]: param.defaultValue }), {}),
        script: ''
      });
      fetchStrategies();
    } catch (e: any) {
      setError(`Failed to create strategy: ${e.message}`);
    } finally {
      setLoadingAction(false);
    }
  };
  
  const generateStrategyScript = (strategyType: string, params: any) => {
    let scriptContent = `# Auto-generated ${strategyType} Strategy\ndef strategy_logic(data, params):\n    \"\"\"${strategyType} based trading strategy\"\"\"\n    import pandas as pd\n    import numpy as np\n\n`;

    switch (strategyType) {
      case 'CCI':
        scriptContent += `    # CCI Parameters\n    window = params.get('window', ${params.window})\n    buy_threshold = params.get('buy_threshold', ${params.buy_threshold})\n    sell_threshold = params.get('sell_threshold', ${params.sell_threshold})\n\n    # CCI Calculation (simplified)\n    tp = (data['high'] + data['low'] + data['close']) / 3\n    sma_tp = tp.rolling(window=window).mean()\n    mad_tp = tp.rolling(window=window).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)\n    cci = (tp - sma_tp) / (0.015 * mad_tp)\n\n    signals = []\n    for i in range(len(cci)):\n        if cci.iloc[i] > sell_threshold: # Sell signal\n            signals.append(-1)\n        elif cci.iloc[i] < buy_threshold: # Buy signal\n            signals.append(1)\n        else:\n            signals.append(0)\n    return signals\n`;
        break;
      case 'MACD':
        scriptContent += `    # MACD Parameters\n    fast_period = params.get('fast_period', ${params.fast_period})\n    slow_period = params.get('slow_period', ${params.slow_period})\n    signal_period = params.get('signal_period', ${params.signal_period})\n\n    # MACD Calculation (simplified)\n    ema_fast = data['close'].ewm(span=fast_period, adjust=False).mean()\n    ema_slow = data['close'].ewm(span=slow_period, adjust=False).mean()\n    macd = ema_fast - ema_slow\n    signal_line = macd.ewm(span=signal_period, adjust=False).mean()\n\n    signals = []\n    # Add MACD trading logic\n    return signals\n`;
        break;
      case 'RSI':
        scriptContent += `    # RSI Parameters\n    window = params.get('window', ${params.window})\n    buy_threshold = params.get('buy_threshold', ${params.buy_threshold})\n    sell_threshold = params.get('sell_threshold', ${params.sell_threshold})\n\n    # RSI Calculation (simplified)\n    delta = data['close'].diff()\n    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()\n    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()\n    rs = gain / loss\n    rsi = 100 - (100 / (1 + rs))\n\n    signals = []\n    # Add RSI trading logic\n    return signals\n`;
        break;
      case 'SMA':
        scriptContent += `    # SMA Parameters\n    short_window = params.get('short_window', ${params.short_window})\n    long_window = params.get('long_window', ${params.long_window})\n\n    # SMA Calculation (simplified)\n    sma_short = data['close'].rolling(window=short_window).mean()\n    sma_long = data['close'].rolling(window=long_window).mean()\n\n    signals = []\n    # Add SMA trading logic\n    return signals\n`;
        break;
      case 'Bollinger':
        scriptContent += `    # Bollinger Bands Parameters\n    window = params.get('window', ${params.window})\n    std_dev = params.get('std_dev', ${params.std_dev})\n\n    # Bollinger Bands Calculation (simplified)\n    sma = data['close'].rolling(window=window).mean()\n    std = data['close'].rolling(window=window).std()\n    upper_band = sma + (std * std_dev)\n    lower_band = sma - (std * std_dev)\n\n    signals = []\n    # Add Bollinger Bands trading logic\n    return signals\n`;
        break;
      case 'custom':
      default:
        scriptContent += `    # Custom strategy logic goes here\n    signals = []\n    # Add your trading logic\n    return signals\n`;
        break;
    }

    return scriptContent;
  };
  
  const calculatePortfolioStats = () => {
    const totalAllocated = activeStrategies.reduce((sum, strategy) => sum + strategy.allocated_capital, 0);
    const availableCapital = portfolioStats.available_capital - totalAllocated;
    
    setPortfolioStats(prev => ({
      ...prev,
      total_allocated: totalAllocated,
      available_capital: availableCapital,
      active_positions: activeStrategies.length
    }));
  };
  
  useEffect(() => {
    calculatePortfolioStats();
  }, [activeStrategies]);

  const fetchActiveStrategies = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/trading/active');
      if (!response.ok) throw new Error('Failed to fetch active strategies');
      const data = await response.json();
      setActiveStrategies(data);
    } catch (e: any) {
      console.error('Failed to fetch active strategies:', e.message);
    }
  };

  const fetchExchanges = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/exchanges');
      if (!response.ok) throw new Error('Failed to fetch exchanges');
      const data = await response.json();
      setExchanges(data);
    } catch (e: any) {
      setError(`Failed to fetch exchanges: ${e.message}`);
    }
  };

  const fetchSymbols = async (exchangeId: string) => {
    try {
      const response = await fetchWithAuth(`http://127.0.0.1:8000/symbols/${exchangeId}`);
      if (!response.ok) throw new Error('Failed to fetch symbols');
      const data = await response.json();
      setSymbols(data);
      if (data.length > 0 && !data.includes(activateForm.symbol)) {
        setActivateForm(prev => ({ ...prev, symbol: data[0] }));
      }
    } catch (e: any) {
      console.error('Failed to fetch symbols:', e.message);
    }
  };

  const activateStrategy = async () => {
    if (!selectedStrategy) return;
    
    setLoadingAction(true);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/trading/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: selectedStrategy.id,
          ...activateForm
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to activate strategy');
      }
      
      const data = await response.json();
      alert(data.message);
      setShowActivateForm(false);
      fetchActiveStrategies();
      fetchPortfolioStats();
    } catch (e: any) {
      setError(`Failed to activate strategy: ${e.message}`);
    } finally {
      setLoadingAction(false);
    }
  };

  const deactivateStrategy = async (activeStrategyId: number) => {
    setLoadingAction(true);
    try {
      const response = await fetchWithAuth(`http://127.0.0.1:8000/trading/deactivate/${activeStrategyId}`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to deactivate strategy');
      }
      
      const data = await response.json();
      alert(data.message);
      fetchActiveStrategies();
      fetchPortfolioStats();
    } catch (e: any) {
      setError(`Failed to deactivate strategy: ${e.message}`);
    } finally {
      setLoadingAction(false);
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
        <h1 className="text-h1 text-center mb-12">Trading Strategies</h1>
        
        {/* Advanced Features Status */}
        {advancedFeaturesEnabled && (
          <div className="linear-card mb-4 bg-gradient-to-r from-green-500/10 to-blue-500/10 border-green-500/20">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <span className="text-2xl">🚀</span>
                <div>
                  <h3 className="text-body font-medium text-green-400">Advanced Features Enabled</h3>
                  <p className="text-small text-secondary">AI-powered optimization, multi-strategy engine, and advanced analytics available</p>
                </div>
              </div>
              {optimizationResults && (
                <div className="text-right">
                  <p className="text-small text-green-400">Last Optimization Score: {optimizationResults.best_score?.toFixed(3)}</p>
                  <p className="text-xs text-secondary">{optimizationResults.method_used}</p>
                </div>
              )}
            </div>
          </div>
        )}
        
        {/* Portfolio Overview */}
        <div className="linear-card mb-8">
          <h2 className="text-h3 mb-6">Portfolio Overview</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="glass-light p-4 rounded-lg text-center">
              <p className="text-small text-secondary mb-1">Total Capital</p>
              <p className="text-body font-medium text-white">${portfolioStats.available_capital + portfolioStats.total_allocated}</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <p className="text-small text-secondary mb-1">Allocated</p>
              <p className="text-body font-medium text-green-400">${portfolioStats.total_allocated}</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <p className="text-small text-secondary mb-1">Available</p>
              <p className="text-body font-medium text-blue-400">${portfolioStats.available_capital - portfolioStats.total_allocated}</p>
            </div>
            <div className="glass-light p-4 rounded-lg text-center">
              <p className="text-small text-secondary mb-1">Active Strategies</p>
              <p className="text-body font-medium text-white">{portfolioStats.active_positions}</p>
            </div>
          </div>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Available Strategies */}
          <div className="linear-card">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-h3">Available Strategies</h2>
              <button
                onClick={() => setShowCreateForm(true)}
                className="linear-button-primary py-2 px-4"
                disabled={loadingAction || loadingFetch}
              >
                Create Strategy
              </button>
            </div>
            {strategies.length > 0 ? (
              <div className="space-y-4">
                {strategies.map((strategy) => (
                  <div key={strategy.id} className="glass-light p-4 rounded-lg">
                    <h3 className="text-body font-medium text-white mb-2">{strategy.name}</h3>
                    <p className="text-small text-secondary mb-2">{strategy.description || 'No description provided'}</p>
                    <p className="text-small text-secondary mb-4">Created: {new Date(strategy.created_at).toLocaleDateString()}</p>
                    {strategy.strategy_type !== 'custom' && strategy.parameters && (
                      <div className="text-xs text-gray-400 mb-2">
                        Parameters: {Object.entries(strategy.parameters).map(([key, value]) => `${key}: ${value}`).join(', ')}
                      </div>
                    )}
                    <div className="flex space-x-2">
                      <button 
                        className="linear-button-primary py-2 px-4 flex-1"
                        onClick={() => {
                          setSelectedStrategy(strategy);
                          setShowActivateForm(true);
                        }}
                        disabled={loadingAction}
                      >
                        Activate for Trading
                      </button>
                      {advancedFeaturesEnabled && (
                        <button
                          className="linear-button-secondary py-2 px-3 text-blue-400 hover:text-blue-300"
                          onClick={() => {
                            setSelectedStrategyForOptimization(strategy);
                            setShowOptimizeModal(true);
                          }}
                          disabled={loadingAction}
                          title="AI Parameter Optimization"
                        >
                          🧠 Optimize
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="glass-light p-4 rounded-lg">
                <p className="text-small text-secondary">No strategies found. Create one first from the dashboard.</p>
              </div>
            )}
          </div>
          
          {/* Active Strategies */}
          <div className="linear-card">
            <h2 className="text-h3 mb-6">Active Strategies</h2>
            {activeStrategies.length > 0 ? (
              <div className="space-y-4">
                {activeStrategies.map((activeStrategy) => (
                  <div key={activeStrategy.id} className="glass-medium p-4 rounded-lg">
                    <h3 className="text-body font-medium text-white mb-2">
                      {activeStrategy.strategies?.name || `Strategy ${activeStrategy.strategy_id}`}
                    </h3>
                    <div className="text-small text-secondary space-y-1 mb-4">
                      <p>Exchange: {activeStrategy.exchange_name}</p>
                      <p>Symbol: {activeStrategy.symbol}</p>
                      <p>Capital: ${activeStrategy.allocated_capital}</p>
                      <p>SL: {activeStrategy.stop_loss_percentage}% | TP: {activeStrategy.take_profit_percentage}%</p>
                      {activeStrategy.strategies?.parameters && (
                        <p>Parameters: {Object.entries(activeStrategy.strategies.parameters).map(([key, value]) => `${key}: ${value}`).join(', ')}</p>
                      )}
                    </div>
                    <button 
                      className="linear-button-secondary py-2 px-4 text-red-400 hover:text-red-300"
                      onClick={() => deactivateStrategy(activeStrategy.id)}
                      disabled={loadingAction}
                    >
                      Deactivate
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="glass-light p-4 rounded-lg">
                <p className="text-small text-secondary">No active strategies found.</p>
              </div>
            )}
          </div>
        </div>

        {/* Activate Strategy Modal */}
        {showActivateForm && selectedStrategy && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="linear-card max-w-md w-full mx-4">
              <h2 className="text-h3 mb-6">Activate {selectedStrategy.name}</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-small mb-2">Exchange:</label>
                  <select
                    value={activateForm.exchange_name}
                    onChange={(e) => setActivateForm(prev => ({ ...prev, exchange_name: e.target.value }))}
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
                    value={activateForm.symbol}
                    onChange={(e) => setActivateForm(prev => ({ ...prev, symbol: e.target.value }))}
                    className="linear-select w-full"
                  >
                    {symbols.map((symbol) => (
                      <option key={symbol} value={symbol}>{symbol}</option>
                    ))}
                  </select>
                </div>
                
                <div>
                  <label className="block text-small mb-2">Allocated Capital ($):</label>
                  <input
                    type="number"
                    value={activateForm.allocated_capital || ''}
                    onChange={(e) => {
                      const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0;
                      setActivateForm(prev => ({ ...prev, allocated_capital: value }));
                    }}
                    className="linear-input w-full"
                    min="1"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-small mb-2">Stop Loss (%):</label>
                    <input
                      type="number"
                      value={activateForm.stop_loss_percentage || ''}
                      onChange={(e) => {
                        const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0;
                        setActivateForm(prev => ({ ...prev, stop_loss_percentage: value }));
                      }}
                      className="linear-input w-full"
                      min="0.1"
                      step="0.1"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-small mb-2">Take Profit (%):</label>
                    <input
                      type="number"
                      value={activateForm.take_profit_percentage || ''}
                      onChange={(e) => {
                        const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0;
                        setActivateForm(prev => ({ ...prev, take_profit_percentage: value }));
                      }}
                      className="linear-input w-full"
                      min="0.1"
                      step="0.1"
                    />
                  </div>
                </div>
                
                {/* Advanced Risk Management */}
                <div className="border-t border-gray-700 pt-4 mt-4">
                  <h4 className="text-small font-medium text-white mb-3">Risk Management</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-small mb-2">Max Position Size (%):</label>
                      <input
                        type="number"
                        value={activateForm.max_position_size || ''}
                        onChange={(e) => {
                          const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0;
                          setActivateForm(prev => ({ ...prev, max_position_size: value }));
                        }}
                        className="linear-input w-full"
                        min="0.01"
                        max="1"
                        step="0.01"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-small mb-2">Risk Per Trade (%):</label>
                      <input
                        type="number"
                        value={activateForm.risk_per_trade || ''}
                        onChange={(e) => {
                          const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0;
                          setActivateForm(prev => ({ ...prev, risk_per_trade: value }));
                        }}
                        className="linear-input w-full"
                        min="0.1"
                        step="0.1"
                      />
                    </div>
                  </div>
                  
                  <div className="mt-4">
                    <label className="block text-small mb-2">Daily Loss Limit (%):</label>
                    <input
                      type="number"
                      value={activateForm.daily_loss_limit || ''}
                      onChange={(e) => {
                        const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0;
                        setActivateForm(prev => ({ ...prev, daily_loss_limit: value }));
                      }}
                      className="linear-input w-full"
                      min="1"
                      step="0.5"
                    />
                  </div>
                </div>
              </div>
              
              <div className="flex space-x-4 mt-6">
                <button
                  onClick={activateStrategy}
                  disabled={loadingAction}
                  className="linear-button-primary py-3 px-6 flex-1 disabled:opacity-50"
                >
                  {loadingAction ? 'Activating...' : 'Activate Strategy'}
                </button>
                <button
                  onClick={() => setShowActivateForm(false)}
                  className="linear-button-secondary py-3 px-6"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
        
        {/* Create Strategy Modal */}
        {showCreateForm && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="linear-card max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
              <h2 className="text-h3 mb-6">Create New Strategy</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-small mb-2">Strategy Name *:</label>
                  <input
                    type="text"
                    value={createForm.name}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                    className="linear-input w-full"
                    placeholder="e.g., Conservative BTC Strategy"
                  />
                </div>
                
                <div>
                  <label className="block text-small mb-2">Description *:</label>
                  <textarea
                    value={createForm.description}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, description: e.target.value }))}
                    className="linear-input w-full h-20"
                    placeholder="Brief description of your strategy..."
                  />
                </div>
                
                <div>
                  <label className="block text-small mb-2">Strategy Type:</label>
                  <select
                    value={createForm.strategy_type}
                    onChange={(e) => {
                      const newStrategyType = e.target.value;
                      setCreateForm(prev => ({
                        ...prev,
                        strategy_type: newStrategyType,
                        parameters: strategyParameterConfigs[newStrategyType].reduce((acc, param) => ({ ...acc, [param.name]: param.defaultValue }), {}),
                        script: '' // Clear custom script when changing type
                      }));
                    }}
                    className="linear-select w-full"
                  >
                    <option value="custom">Custom Strategy</option>
                    <option value="CCI">CCI Based</option>
                    <option value="MACD">MACD Based</option>
                    <option value="RSI">RSI Based</option>
                    <option value="SMA">Simple Moving Average</option>
                    <option value="Bollinger">Bollinger Bands</option>
                  </select>
                </div>
                
                {/* Strategy Parameters */}
                {createForm.strategy_type !== 'custom' && (
                  <div className="border-t border-gray-700 pt-4">
                    <h4 className="text-small font-medium text-white mb-3">Strategy Parameters</h4>
                    <div className="grid grid-cols-2 gap-4">
                      {strategyParameterConfigs[createForm.strategy_type]?.map(param => (
                        <div key={param.name} className={param.type === 'select' && param.options && param.options.length > 3 ? 'col-span-2' : ''}>
                          <label className="block text-small mb-2">{param.label}:</label>
                          {param.type === 'number' && (
                            <input
                              type="number"
                              value={(createForm.parameters as any)[param.name] || ''}
                              onChange={(e) => {
                                const value = e.target.value === '' ? 0 : parseFloat(e.target.value) || 0;
                                setCreateForm(prev => ({
                                  ...prev,
                                  parameters: { ...prev.parameters, [param.name]: value }
                                }));
                              }}
                              className="linear-input w-full"
                              step="any"
                            />
                          )}
                          {param.type === 'select' && (
                            <select
                              value={(createForm.parameters as any)[param.name] || ''}
                              onChange={(e) => setCreateForm(prev => ({
                                ...prev,
                                parameters: { ...prev.parameters, [param.name]: e.target.value }
                              }))}
                              className="linear-select w-full"
                            >
                              {param.options?.map(option => (
                                <option key={option} value={option}>{option}</option>
                              ))}
                            </select>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Custom Script (Optional) */}
                <div>
                  <label className="block text-small mb-2">Custom Script (Optional):</label>
                  <textarea
                    value={createForm.script}
                    onChange={(e) => setCreateForm(prev => ({ ...prev, script: e.target.value }))}
                    className="linear-input w-full h-32 font-mono text-xs"
                    placeholder="# Advanced users: Write your custom Python strategy here..."
                  />
                  <p className="text-xs text-secondary mt-1">Leave empty to auto-generate based on parameters above</p>
                </div>
              </div>
              
              <div className="flex space-x-4 mt-6">
                <button
                  onClick={createStrategy}
                  disabled={loadingAction}
                  className="linear-button-primary py-3 px-6 flex-1 disabled:opacity-50"
                >
                  {loadingAction ? 'Creating...' : 'Create Strategy'}
                </button>
                <button
                  onClick={() => setShowCreateForm(false)}
                  className="linear-button-secondary py-3 px-6"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Strategy Optimization Modal */}
        {showOptimizeModal && selectedStrategyForOptimization && advancedFeaturesEnabled && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="linear-card max-w-lg w-full mx-4">
              <h2 className="text-h3 mb-6">🧠 AI Strategy Optimization</h2>
              <div className="mb-4">
                <p className="text-body text-white mb-2">Strategy: {selectedStrategyForOptimization.name}</p>
                <p className="text-small text-secondary">
                  AI will optimize parameters using genetic algorithms to maximize Sharpe ratio.
                  This process may take 1-2 minutes.
                </p>
              </div>
              
              {optimizationResults && (
                <div className="glass-light p-4 rounded-lg mb-4">
                  <h4 className="text-small font-medium text-green-400 mb-2">Latest Optimization Results</h4>
                  <div className="space-y-1 text-xs">
                    <p>Best Score: <span className="text-green-400">{optimizationResults.best_score?.toFixed(3)}</span></p>
                    <p>Method: <span className="text-blue-400">{optimizationResults.method_used}</span></p>
                    <p>Parameters: {JSON.stringify(optimizationResults.best_parameters, null, 1)}</p>
                  </div>
                </div>
              )}
              
              <div className="flex space-x-4">
                <button
                  onClick={() => optimizeStrategy(selectedStrategyForOptimization.name)}
                  disabled={loadingAction}
                  className="linear-button-primary py-3 px-6 flex-1 disabled:opacity-50"
                >
                  {loadingAction ? '🔄 Optimizing...' : '🚀 Start Optimization'}
                </button>
                <button
                  onClick={() => {
                    setShowOptimizeModal(false);
                    setSelectedStrategyForOptimization(null);
                  }}
                  className="linear-button-secondary py-3 px-6"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}