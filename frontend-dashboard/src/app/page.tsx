"use client";

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@clerk/nextjs';
import TradingChart from '@/components/TradingChart'; // TradingChart 컴포넌트 임포트
import { useWebSocket } from '@/contexts/WebSocketProvider';
import { LocalizedPageTitle, LocalizedSectionTitle, LocalizedSelectLabel, LocalizedButton, LocalizedTableHeader } from '@/components/LocalizedPage';
import MonitoringButton from '@/components/MonitoringButton';
import NoSSR from '@/components/NoSSR';

export default function Home() {
  const { t } = useTranslation();
  const { getToken } = useAuth();
  const { data: websocketData } = useWebSocket();
  const [portfolioStats, setPortfolioStats] = useState<any>(null);
  const [exchanges, setExchanges] = useState<string>([]);
  const [symbols, setSymbols] = useState<string>([]);
  const [ticker, setTicker] = useState<any>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [loadingSymbols, setLoadingSymbols] = useState(false);
  const [loadingExchanges, setLoadingExchanges] = useState(false);
  const [loadingTicker, setLoadingTicker] = useState(false);

  // Backtesting state
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [backtestParams, setBacktestParams] = useState({
    exchange_id: 'bingx_vst',
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
      const response = await fetchWithAuth('http://127.0.0.1:8000/portfolio/stats');
      if (response.ok) {
        const data = await response.json();
        setPortfolioStats(data);
      } else {
        console.error('Failed to fetch portfolio stats:', response.status, response.statusText);
        setFetchError(`Failed to fetch portfolio stats: ${response.statusText}`);
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
        alert('🚀 Demo Trading 시작! BingX VST 모드로 가상 거래를 시작합니다.');
      } else {
        alert('데모 트레이딩 시작 실패.');
      }
    } catch (error) {
      alert('데모 트레이딩 시작 중 오류가 발생했습니다.');
    }
  };

  const handleTestOrder = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/demo/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exchange: 'bingx_vst',
          symbol: 'BTC/USDT',
          side: 'buy',
          order_type: 'market',
          amount: 0.001,
          current_price: ticker?.last || 0 // Use current ticker price if available
        }),
      });
      if (response.ok) {
        alert('📈 테스트 주문 실행! BTC/USDT 소량 매수 주문을 생성합니다.');
      } else {
        alert('테스트 주문 실행 실패.');
      }
    } catch (error) {
      alert('테스트 주문 실행 중 오류가 발생했습니다.');
    }
  };

  const handleVSTStatus = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/ws/connection-status');
      if (response.ok) {
        const data = await response.json();
        alert(`⚙️ VST 상태: ${data.is_connected ? '연결됨' : '연결 끊김'}`);
      } else {
        alert('⚙️ VST 상태를 확인할 수 없습니다.');
      }
    } catch (error) {
      alert('⚙️ VST 상태 확인 중 오류가 발생했습니다.');
    }
  };

  const handleVSTBalance = async () => {
    try {
      const response = await fetchWithAuth('http://127.0.0.1:8000/demo/balance');
      if (response.ok) {
        const data = await response.json();
        alert(`💰 VST 잔고: ${data.balance?.USDT?.total?.toFixed(2) || '0.00'} USDT`);
      } else {
        alert('💰 VST 잔고를 확인할 수 없습니다.');
      }
    } catch (error) {
      alert('💰 VST 잔고 확인 중 오류가 발생했습니다.');
    }
  };

  

  const handleTimeframeChange = (timeframe: string) => {
    setChartTimeframe(timeframe);
  };

  const handleBacktestChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setBacktestParams((prevParams) => ({
      ...prevParams,
      [name]: name === 'limit' || name === 'window' || name === 'buy_threshold' || name === 'sell_threshold' || name === 'initial_capital' || name === 'commission' ? parseFloat(value) : value,
    }));
  };

  const runBacktest = async () => {
    setBacktestLoading(true);
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
      alert('백테스트가 완료되었습니다! 결과를 확인하세요.');
    } catch (e: any) {
      setFetchError(`Failed to run backtest: ${e.message}`);
      alert(`백테스트 실행 중 오류가 발생했습니다: ${e.message}`);
    } finally {
      setBacktestLoading(false);
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
        alert(`전략 활성화 성공: ${data.message}`);
        fetchActiveStrategies(); // 활성화된 전략 목록 새로고침
      } else {
        const errorData = await response.json();
        alert(`전략 활성화 실패: ${errorData.detail || response.statusText}`);
      }
    } catch (error: any) {
      alert(`전략 활성화 중 오류가 발생했습니다: ${error.message}`);
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

  useEffect(() => {
    fetchPortfolioStats();
    fetchExchanges();
    fetchActiveStrategies();
  }, []);

  useEffect(() => {
    fetchSymbols();
  }, [backtestParams.exchange_id]);

  useEffect(() => {
    fetchTicker();
  }, [backtestParams.exchange_id, backtestParams.symbol]);

  if (fetchError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="bg-white border border-gray-300 rounded-lg p-6 max-w-md mx-auto text-center">
          <h2 className="text-lg font-semibold text-red-600 mb-4">Error</h2>
          <p className="text-gray-700 mb-6">{fetchError}</p>
          <button 
            onClick={() => setFetchError(null)}
            className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-md"
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
        <h1 className="yw-h1">비트코인 트레이딩</h1>

        {/* Portfolio Overview */}
        <div className="yw-card mb-8">
          <h2 className="yw-h2">Portfolio Overview</h2>
          <div className="yw-metrics-grid">
            <div className="yw-metric-card">
              <span className="yw-metric-value">
                ${portfolioStats ? portfolioStats.total_capital?.toFixed(2) || '0.00' : '0.00'}
              </span>
              <p className="yw-metric-label">Total Capital</p>
            </div>
            <div className="yw-metric-card">
              <span className="yw-metric-value">
                ${portfolioStats ? portfolioStats.available_capital?.toFixed(2) || '0.00' : '0.00'}
              </span>
              <p className="yw-metric-label">Available</p>
            </div>
            <div className="yw-metric-card">
              <span className="yw-metric-value">
                ${portfolioStats ? portfolioStats.total_allocated?.toFixed(2) || '0.00' : '0.00'}
              </span>
              <p className="yw-metric-label">Allocated</p>
            </div>
            <div className="yw-metric-card">
              <span className="yw-metric-value">
                {portfolioStats ? portfolioStats.active_strategies || 0 : 0}
              </span>
              <p className="yw-metric-label">Active Strategies</p>
            </div>
          </div>
        </div>

        {/* Demo Trading Controls */}
        <div className="yw-card mb-8">
          <h2 className="yw-h2">Demo Trading Controls</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            <button className="yw-button-primary" onClick={handleDemoTrading}>🚀 Start Demo Trading</button>
            <button className="yw-button-primary" onClick={handleTestOrder}>📈 Place Test Order</button>
            <button className="yw-button-outline" onClick={handleVSTStatus}>⚙️ Check VST Status</button>
            <button className="yw-button-outline" onClick={handleVSTBalance}>💰 View VST Balance</button>
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

        {/* BTC/USDT Chart */}
        <div className="yw-card mb-8">
          <h2 className="yw-h2">BTC/USDT Chart</h2>
          <div className="mt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-sm">시간프레임 선택</h3>
              <MonitoringButton />
            </div>
            <div className="flex flex-wrap gap-2">
              {['1m', '5m', '15m', '1h', '4h', '1d'].map((timeframe) => (
                <button 
                  key={timeframe}
                  onClick={() => handleTimeframeChange(timeframe)}
                  className={`px-3 py-1 rounded text-sm transition-colors ${
                    chartTimeframe === timeframe
                      ? 'bg-blue-500 text-white shadow-md'
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
          <h2 className="yw-h2">백테스트 설정</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">거래소</label>
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
              <label className="block text-sm font-medium text-gray-700 mb-2">심볼</label>
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
              <label className="block text-sm font-medium text-gray-700 mb-2">시간프레임</label>
              <select name="timeframe" className="w-full p-2 border border-gray-300 rounded-md" value={backtestParams.timeframe} onChange={handleBacktestChange}>
                <option value="1m">1분</option>
                <option value="5m">5분</option>
                <option value="15m">15분</option>
                <option value="1h">1시간</option>
                <option value="4h">4시간</option>
                <option value="1d">1일</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">데이터 개수</label>
              <input type="number" name="limit" className="w-full p-2 border border-gray-300 rounded-md" min="50" max="1000" value={backtestParams.limit} onChange={handleBacktestChange} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">CCI 기간</label>
              <input type="number" name="window" className="w-full p-2 border border-gray-300 rounded-md" min="5" max="50" value={backtestParams.window} onChange={handleBacktestChange} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">초기 자본</label>
              <input type="number" name="initial_capital" className="w-full p-2 border border-gray-300 rounded-md" min="1000" value={backtestParams.initial_capital} onChange={handleBacktestChange} />
            </div>
          </div>
          <button 
            onClick={runBacktest}
            disabled={loadingBacktest}
            className="w-full bg-blue-500 hover:bg-blue-600 text-white py-2 px-4 rounded-md disabled:opacity-50"
          >
            {loadingBacktest ? '백테스트 실행 중...' : '백테스트 실행'}
          </button>
          {backtestResults && (
            <div className="mt-4 p-4 bg-gray-100 rounded-md">
              <h3 className="text-lg font-semibold mb-2">백테스트 결과</h3>
              <p>최종 자본: ${backtestResults.final_capital?.toFixed(2)}</p>
              <p>총 수익률: {backtestResults.return_rate?.toFixed(2)}%</p>
              <p>총 거래 수: {backtestResults.total_trades}</p>
              <p>승률: {backtestResults.win_rate?.toFixed(2)}%</p>
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
                    onClick={() => handleActivateStrategy(strategy.id, strategy.exchange_name || 'bingx_vst', strategy.symbol || 'BTC/USDT', strategy.allocated_capital || 1000)}
                    className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-md text-sm"
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
