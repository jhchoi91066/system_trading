"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@clerk/nextjs';
import TradingChart from '@/components/TradingChart'; // TradingChart 컴포넌트 임포트
import { useWebSocket } from '@/contexts/WebSocketProvider';
import MonitoringButton from '@/components/MonitoringButton';
import NoSSR from '@/components/NoSSR';

export default function Home() {
  const { getToken } = useAuth();
  const { data: websocketData } = useWebSocket();
  const [portfolioStats, setPortfolioStats] = useState<any>(null);
  const [exchanges, setExchanges] = useState<string[]>([]);
  const [symbols, setSymbols] = useState<string[]>([]);
  const [ticker, setTicker] = useState<any>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [loadingSymbols, setLoadingSymbols] = useState(false);
  const [loadingExchanges, setLoadingExchanges] = useState(false);
  const [loadingTicker, setLoadingTicker] = useState(false);

  // Backtesting state
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [backtestParams, setBacktestParams] = useState({
    exchange_id: 'bingx',
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
  
  // CCI 지표 상태 관리
  const [cciData, setCciData] = useState<any>(null);
  const [loadingCci, setLoadingCci] = useState(false);
  const [cciPeriod, setCciPeriod] = useState(14);
  const [cciMethod, setCciMethod] = useState('standard');

  const fetchWithAuth = async (url: string, options?: RequestInit) => {
    const token = await getToken();
    const headers = {
      ...(options?.headers || {}),
      'Authorization': `Bearer ${token}`,
    };
    return fetch(url, { ...options, headers });
  };

  const fetchPortfolioStats = async () => {
    try {
      // Use new combined VST portfolio endpoint for better performance
      const portfolioResponse = await fetchWithAuth('http://127.0.0.1:8000/vst/portfolio');
      
      if (portfolioResponse.ok) {
        const portfolioData = await portfolioResponse.json();
        
        // Handle error case from backend
        if (portfolioData.error) {
          console.warn('VST API issue:', portfolioData.error);
        }
        
        // Calculate portfolio stats from actual VST data
        const balance = portfolioData.balance?.data?.balance || {};
        const totalCapital = parseFloat(balance.balance || '0');
        const equity = parseFloat(balance.equity || '0');
        const usedMargin = parseFloat(balance.usedMargin || '0');
        const availableMargin = parseFloat(balance.availableMargin || '0');
        const unrealizedPnl = parseFloat(balance.unrealizedProfit || '0');
        
        // Count active positions and get strategy count from active strategies
        const activePositions = Array.isArray(portfolioData.positions) ? portfolioData.positions.length : 0;
        const recentTrades = Array.isArray(portfolioData.recent_trades?.orders) ? portfolioData.recent_trades.orders.length : 0;
        
        const portfolioStats = {
          total_capital: totalCapital,
          available_capital: availableMargin,
          total_allocated: usedMargin,
          active_positions: activePositions,
          active_strategies: activeStrategies.length, // Use actual active strategies count
          unrealized_pnl: unrealizedPnl,
          equity: equity,
          recent_trades_count: recentTrades,
          is_vst_data: true
        };
        
        setPortfolioStats(portfolioStats);
      } else {
        // Fallback to original portfolio stats if VST is not available
        const fallbackResponse = await fetchWithAuth('http://127.0.0.1:8000/portfolio/stats');
        if (fallbackResponse.ok) {
          const fallbackData = await fallbackResponse.json();
          setPortfolioStats({...fallbackData, is_vst_data: false});
        } else {
          console.error('Failed to fetch both VST and fallback portfolio stats');
          setFetchError('Failed to fetch portfolio data');
        }
      }
    } catch (error: any) {
      console.error('Portfolio stats fetch error:', error);
      setFetchError(`Portfolio stats fetch error: ${error.message}`);
    }
  };

  // Button handlers
  const handleDemoTrading = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/demo/initialize', { method: 'POST' });
      if (response.ok) {
        alert('🚀 Demo Trading Started! Virtual trading has started in BingX VST mode.');
      } else {
        alert('Demo trading start failed.');
      }
    } catch (error) {
      alert('Error occurred while starting demo trading.');
    }
  };

  const handleTestOrder = async () => {
    try {
      // BingX VST 실제 데모 주문 API 사용
      const response = await fetchWithAuth('http://127.0.0.1:8000/vst/orders?symbol=BTC-USDT&side=BUY&order_type=MARKET&quantity=0.001', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        const result = await response.json();
        alert('🎮 BingX VST Demo Order Executed! Small BTC-USDT buy order created in VST account.');
        console.log('VST Order Result:', result);
      } else {
        const error = await response.json();
        alert(`VST 주문 실행 실패: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('VST Order Error:', error);
      alert('Error occurred while executing VST order. Please check API key settings.');
    }
  };

  const handleVSTStatus = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/vst/status');
      if (response.ok) {
        const data = await response.json();
        const status = data.connected ? 'Connected' : 'Disconnected';
        const balance = data.account_info?.vst_balance || 0;
        alert(`⚙️ BingX VST Status: ${status}\n💰 VST Balance: ${balance.toFixed(2)} USDT`);
      } else {
        alert('⚙️ Unable to check BingX VST status.');
      }
    } catch (error) {
      alert('⚙️ Error occurred while checking BingX VST status.');
    }
  };

  const handleVSTBalance = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/vst/balance');
      if (response.ok) {
        const data = await response.json();
        const balance = data.account_info?.vst_balance || 0;
        const positions = data.account_info?.open_positions || 0;
        alert(`💰 BingX VST Balance: ${balance.toFixed(2)} USDT\n📊 Active Positions: ${positions}`);
      } else {
        alert('💰 Unable to check VST balance.');
      }
    } catch (error) {
      alert('💰 Error occurred while checking VST balance.');
    }
  };

  

  const handleTimeframeChange = (timeframe: string) => {
    setChartTimeframe(timeframe);
    fetchCCIData();
  };

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
        if (key !== 'exchange_id' && key !== 'symbol') {
          params.append(key, (backtestParams as any)[key].toString());
        }
      }
      const response = await fetchWithAuth(`http://127.0.0.1:8000/backtest/${backtestParams.exchange_id}/${backtestParams.symbol}?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setBacktestResults(data);
      alert('Backtest completed! Check the results.');
    } catch (e: any) {
      setFetchError(`Failed to run backtest: ${e.message}`);
      alert(`Error occurred during backtest execution: ${e.message}`);
    } finally {
      setLoadingBacktest(false);
    }
  };

  const handleActivateStrategy = async (strategyId: number, exchangeName: string, symbol: string, allocatedCapital: number) => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/trading/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: strategyId,
          exchange_name: exchangeName,
          symbol: symbol,
          allocated_capital: allocatedCapital,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        alert(`Strategy activation successful: ${data.message}`);
        fetchActiveStrategies(); // Refresh active strategies list
      } else {
        const errorData = await response.json();
        alert(`Strategy activation failed: ${errorData.detail || response.statusText}`);
      }
    } catch (error: any) {
      alert(`Error occurred during strategy activation: ${error.message}`);
    }
  };

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
      if (data.length > 0 && !data.includes(backtestParams.symbol)) {
        setBacktestParams(prevParams => ({ ...prevParams, symbol: data[0] }));
      }
    } catch (e: any) {
      setFetchError(`Failed to fetch symbols for ${backtestParams.exchange_id}: ${e.message}`);
    } finally {
      setLoadingSymbols(false);
    }
  };

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

  const fetchActiveStrategies = async () => {
    setLoadingStrategies(true);
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/trading/active');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setActiveStrategies(data);
    } catch (e: any) {
      console.error('Failed to fetch active strategies:', e);
      setFetchError(`Failed to fetch active strategies: ${e.message}`);
    } finally {
      setLoadingStrategies(false);
    }
  };

  const fetchCCIData = async () => {
    setLoadingCci(true);
    try {
      const response = await fetchWithAuth(`http://127.0.0.1:8000/indicators/cci/BTC-USDT?timeframe=${chartTimeframe}&limit=50&window=${cciPeriod}&method=${cciMethod}`);
      if (response.ok) {
        const data = await response.json();
        setCciData(data);
      }
    } catch (error) {
      console.error('Failed to fetch CCI data:', error);
    } finally {
      setLoadingCci(false);
    }
  };

  useEffect(() => {
    fetchPortfolioStats();
    fetchExchanges();
    fetchActiveStrategies();
    fetchCCIData();
    
    // Set up auto-refresh for portfolio stats every 60 seconds to reduce API load
    const portfolioInterval = setInterval(fetchPortfolioStats, 60000);
    
    return () => {
      clearInterval(portfolioInterval);
    };
  }, []);

  useEffect(() => {
    fetchSymbols();
  }, [backtestParams.exchange_id]);

  useEffect(() => {
    fetchTicker();
  }, [backtestParams.exchange_id, backtestParams.symbol]);

  useEffect(() => {
    fetchCCIData();
  }, [cciPeriod]);

  if (fetchError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-white border border-gray-300 rounded-lg p-6 max-w-md mx-auto text-center">
          <h2 className="text-lg font-semibold text-red-600 mb-4">Error</h2>
          <p className="text-gray-700 mb-6">{fetchError}</p>
          <button 
            onClick={() => setFetchError(null)}
            className="bg-blue-500 hover:bg-blue-600 text-black px-4 py-2 rounded-md"
          >
            Dismiss
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="yw-main-content">
      <div className="max-w-7xl mx-auto">
        <h1 className="yw-h1">Bitcoin Trading</h1>

        {/* Portfolio Overview */}
        <div className="yw-card mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="yw-h2">Portfolio Overview</h2>
            {portfolioStats?.is_vst_data && (
              <span className="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded-full">
                🎮 Live BingX VST Data
              </span>
            )}
          </div>
          <div className="yw-metrics-grid">
            <div className="yw-metric-card">
              <span className="yw-metric-value">
                ${portfolioStats ? portfolioStats.total_capital?.toFixed(2) || '0.00' : '0.00'}
              </span>
              <p className="yw-metric-label">Total Balance</p>
            </div>
            <div className="yw-metric-card">
              <span className="yw-metric-value">
                ${portfolioStats ? portfolioStats.available_capital?.toFixed(2) || '0.00' : '0.00'}
              </span>
              <p className="yw-metric-label">Available Margin</p>
            </div>
            <div className="yw-metric-card">
              <span className="yw-metric-value">
                ${portfolioStats ? portfolioStats.total_allocated?.toFixed(2) || '0.00' : '0.00'}
              </span>
              <p className="yw-metric-label">Used Margin</p>
            </div>
            <div className="yw-metric-card">
              <span className="yw-metric-value">
                {portfolioStats ? portfolioStats.active_strategies || 0 : 0}
              </span>
              <p className="yw-metric-label">Active Strategies</p>
            </div>
            <div className="yw-metric-card">
              <span className="yw-metric-value">
                {portfolioStats ? portfolioStats.active_positions || 0 : 0}
              </span>
              <p className="yw-metric-label">Open Positions</p>
            </div>
            {portfolioStats?.is_vst_data && (
              <>
                <div className="yw-metric-card">
                  <span className={`yw-metric-value ${portfolioStats.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    ${portfolioStats.unrealized_pnl?.toFixed(2) || '0.00'}
                  </span>
                  <p className="yw-metric-label">Unrealized P&L</p>
                </div>
                <div className="yw-metric-card">
                  <span className="yw-metric-value">
                    ${portfolioStats.equity?.toFixed(2) || '0.00'}
                  </span>
                  <p className="yw-metric-label">Total Equity</p>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Demo Trading Controls */}
        <div className="yw-card mb-8">
          <h2 className="yw-h2">Demo Trading Controls</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            <button className="bg-blue-600 hover:bg-blue-700 text-black font-medium py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center" onClick={handleDemoTrading}>
              🚀 Start Demo Trading
            </button>
            <button className="bg-green-600 hover:bg-green-700 text-black font-medium py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center" onClick={handleTestOrder}>
              📈 Place Test Order
            </button>
            <button className="bg-gray-600 hover:bg-gray-700 text-black font-medium py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center" onClick={handleVSTStatus}>
              ⚙️ Check VST Status
            </button>
            <button className="bg-purple-600 hover:bg-purple-700 text-black font-medium py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center" onClick={handleVSTBalance}>
              💰 View VST Balance
            </button>
          </div>
          <div className="yw-card" style={{backgroundColor: 'var(--yw-info)', color: 'var(--yw-white)', border: 'none'}}>
            <p className="yw-body" style={{color: 'var(--yw-white)', fontWeight: 'var(--yw-font-weight-semibold)'}}>
              🧪 Demo Trading Mode
            </p>
            <p className="yw-small" style={{color: 'var(--yw-white)'}}>
              Using BingX VST (Virtual Simulated Trading) with virtual funds.
            </p>
          </div>
        </div>

        {/* CCI Indicator Display */}
        <div className="yw-card mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="yw-h2">CCI Indicator & Trading Signals</h2>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-black">Period:</label>
                <select 
                  value={cciPeriod}
                  onChange={(e) => setCciPeriod(Number(e.target.value))}
                  className="bg-white border border-gray-300 text-black text-sm rounded-lg p-2"
                >
                  <option value={14}>14</option>
                  <option value={20}>20</option>
                  <option value={30}>30</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm font-medium text-black">Calculation Method:</label>
                <select 
                  value={cciMethod}
                  onChange={(e) => setCciMethod(e.target.value)}
                  className="bg-white border border-gray-300 text-black text-sm rounded-lg p-2"
                >
                  <option value="standard">Standard</option>
                  <option value="talib">TA-Lib</option>
                </select>
              </div>
              <button 
                onClick={fetchCCIData}
                disabled={loadingCci}
                className="bg-purple-600 hover:bg-purple-700 text-black font-medium py-2 px-4 rounded-lg transition-colors duration-200"
              >
                {loadingCci ? 'Loading...' : '🔄 Update CCI'}
              </button>
            </div>
          </div>
          
          {cciData && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-semibold text-sm mb-2">Current CCI Value</h3>
                <div className="text-2xl font-bold mb-1">
                  {cciData.cci.current_value?.toFixed(2) || 'N/A'}
                </div>
                <div className={`text-sm ${
                  cciData.cci.current_value > cciData.cci.sell_threshold ? 'text-red-600' :
                  cciData.cci.current_value < cciData.cci.buy_threshold ? 'text-green-600' : 'text-gray-600'
                }`}>
                  {cciData.cci.interpretation}
                </div>
              </div>
              
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-semibold text-sm mb-2">Trading Signal</h3>
                <div className={`text-2xl font-bold mb-1 ${
                  cciData.signal.current === 1 ? 'text-green-600' :
                  cciData.signal.current === -1 ? 'text-red-600' : 'text-gray-600'
                }`}>
                  {cciData.signal.interpretation}
                </div>
                <div className="text-sm text-gray-500">
                  Current Price: ${cciData.current_price?.toFixed(2)}
                </div>
              </div>
              
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-semibold text-sm mb-2">Threshold Settings</h3>
                <div className="text-sm space-y-1">
                  <div>Buy Threshold: {cciData.cci.buy_threshold}</div>
                  <div>Sell Threshold: {cciData.cci.sell_threshold}</div>
                  <div>Window: {cciData.cci.window} periods</div>
                </div>
              </div>
            </div>
          )}
          
          {!cciData && !loadingCci && (
            <div className="text-center py-8 text-gray-500">
              Click the update button above to load CCI indicator data.
            </div>
          )}
        </div>

        {/* BTC/USDT Chart */}
        <div className="yw-card mb-8">
          <h2 className="yw-h2">BTC/USDT Chart</h2>
          <div className="mt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-sm">Select Timeframe</h3>
              <MonitoringButton />
            </div>
            <div className="flex flex-wrap gap-2">
              {['1m', '5m', '15m', '1h', '4h', '1d'].map((timeframe) => (
                <button 
                  key={timeframe}
                  onClick={() => handleTimeframeChange(timeframe)}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    chartTimeframe === timeframe
                      ? 'bg-blue-500 text-black shadow-md'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {timeframe}
                </button>
              ))}
            </div>
            <NoSSR>
              <TradingChart symbol={backtestParams.symbol} timeframe={chartTimeframe} exchange={backtestParams.exchange_id} />
            </NoSSR>
          </div>
        </div>

        {/* Backtest Settings */}
        <div className="yw-card mb-8">
          <h2 className="yw-h2">Backtest Settings</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Exchange</label>
              <select name="exchange_id" className="w-full p-2 border border-gray-300 rounded-md" value={backtestParams.exchange_id} onChange={handleBacktestChange}>
                {loadingExchanges ? (
                  <option>Loading exchanges...</option>
                ) : (
                  exchanges.map((exchange) => (
                    <option key={exchange} value={exchange}>{exchange}</option>
                  ))
                )}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Symbol</label>
              <select name="symbol" className="w-full p-2 border border-gray-300 rounded-md" value={backtestParams.symbol} onChange={handleBacktestChange}>
                {loadingSymbols ? (
                  <option>Loading symbols...</option>
                ) : (
                  symbols.map((symbol) => (
                    <option key={symbol} value={symbol}>{symbol}</option>
                  ))
                )}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Timeframe</label>
              <select name="timeframe" className="w-full p-2 border border-gray-300 rounded-md" value={backtestParams.timeframe} onChange={handleBacktestChange}>
                <option value="1m">1 minute</option>
                <option value="5m">5 minutes</option>
                <option value="15m">15 minutes</option>
                <option value="1h">1 hour</option>
                <option value="4h">4 hours</option>
                <option value="1d">1 day</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Data Count</label>
              <input type="number" name="limit" className="w-full p-2 border border-gray-300 rounded-md" min="50" max="1000" value={backtestParams.limit} onChange={handleBacktestChange} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">CCI Period</label>
              <input type="number" name="window" className="w-full p-2 border border-gray-300 rounded-md" min="5" max="50" value={backtestParams.window} onChange={handleBacktestChange} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Initial Capital</label>
              <input type="number" name="initial_capital" className="w-full p-2 border border-gray-300 rounded-md" min="1000" value={backtestParams.initial_capital} onChange={handleBacktestChange} />
            </div>
          </div>
          <button 
            onClick={runBacktest}
            disabled={loadingBacktest}
            className="w-full bg-blue-500 hover:bg-blue-600 text-black py-2 px-4 rounded-md disabled:opacity-50"
          >
            {loadingBacktest ? 'Running Backtest...' : 'Run Backtest'}
          </button>
          {backtestResults && (
            <div className="mt-4 p-4 bg-gray-100 rounded-md">
              <h3 className="text-lg font-semibold mb-2">Backtest Results</h3>
              <p>Final Capital: ${backtestResults.final_capital?.toFixed(2)}</p>
              <p>Total Return: {backtestResults.return_rate?.toFixed(2)}%</p>
              <p>Total Trades: {backtestResults.total_trades}</p>
              <p>Win Rate: {backtestResults.win_rate?.toFixed(2)}%</p>
            </div>
          )}
        </div>

        {/* Available Strategies */}
        <div className="yw-card mb-8">
          <h2 className="yw-h2">Available Strategies</h2>
          <div className="space-y-4">
            {loadingStrategies ? (
              <p>Loading strategies...</p>
            ) : activeStrategies.length === 0 ? (
              <p>No active strategies found.</p>
            ) : (
              activeStrategies.map((strategy, index) => (
                <div key={`strategy-${strategy.id || index}`} className="border border-gray-200 rounded-lg p-4">
                  <h3 className="font-medium mb-2">{strategy.name}</h3>
                  <p className="text-sm text-gray-600 mb-2">{strategy.description}</p>
                  <p className="text-xs text-gray-500 mb-3">Created: {new Date(strategy.created_at).toLocaleDateString()}</p>
                  <button 
                    onClick={() => handleActivateStrategy(strategy.id, strategy.exchange_name || 'bingx', strategy.symbol || 'BTC/USDT', strategy.allocated_capital || 1000)}
                    className="bg-green-500 hover:bg-green-600 text-black px-4 py-2 rounded-md text-sm"
                  >
                    Activate for Trading
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
}
