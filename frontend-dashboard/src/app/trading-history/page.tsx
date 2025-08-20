"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@clerk/nextjs';

interface Trade {
  id: number;
  user_id: string;
  strategy_name: string;
  exchange_name: string;
  symbol: string;
  side: 'buy' | 'sell';
  amount: number;
  price: number;
  fee: number;
  profit_loss: number;
  profit_loss_percentage: number;
  status: string;
  created_at: string;
  closed_at: string;
}

interface TradingStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  total_profit_loss: number;
  total_fees: number;
  win_rate: number;
  average_profit: number;
  average_loss: number;
  largest_win: number;
  largest_loss: number;
}

export default function TradingHistoryPage() {
  const { getToken } = useAuth();
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<TradingStats | null>(null);
  const [filter, setFilter] = useState({
    strategy: 'all',
    symbol: 'all',
    side: 'all',
    status: 'all'
  });

  const fetchWithAuth = async (url: string, options?: RequestInit) => {
    const token = await getToken();
    const headers = {
      ...(options?.headers || {}),
      'Authorization': `Bearer ${token}`,
    };
    return fetch(url, { ...options, headers });
  };

  useEffect(() => {
    fetchTradingHistory();
  }, []);

  useEffect(() => {
    if (trades.length > 0) {
      calculateStats();
    }
  }, [trades]);

  const fetchTradingHistory = async () => {
    setLoading(true);
    try {
      // Fetch real BingX VST trading data
      const response = await fetchWithAuth('http://127.0.0.1:8000/vst/trades?limit=100');
      if (response.ok) {
        const vstData = await response.json();
        
        // Transform VST data to match our Trade interface
        const transformedTrades = vstData.map((trade: any, index: number) => ({
          id: index + 1,
          user_id: 'vst_user',
          strategy_name: 'BingX VST Trading',
          exchange_name: 'BingX',
          symbol: trade.symbol || 'BTC/USDT',
          side: trade.side?.toLowerCase() || 'buy',
          amount: parseFloat(trade.quantity || trade.amount || '0'),
          price: parseFloat(trade.price || '0'),
          fee: parseFloat(trade.fee || '0'),
          profit_loss: parseFloat(trade.realizedPnl || trade.pnl || '0'),
          profit_loss_percentage: trade.realizedPnl ? (parseFloat(trade.realizedPnl) / parseFloat(trade.price || '1')) * 100 : 0,
          status: trade.status || 'completed',
          created_at: trade.time || trade.timestamp || new Date().toISOString(),
          closed_at: trade.time || trade.timestamp || new Date().toISOString()
        }));
        
        setTrades(transformedTrades);
      } else {
        // Fallback to simulated data if VST data is not available
        const fallbackResponse = await fetchWithAuth('http://127.0.0.1:8000/trading/history');
        if (fallbackResponse.ok) {
          const data = await fallbackResponse.json();
          setTrades(data);
        } else {
          setError('Failed to fetch trading history from both VST and database');
        }
      }
    } catch (e: any) {
      setError(`Error fetching trading history: ${e.message}`);
      
      // Try fallback to simulated data
      try {
        const fallbackResponse = await fetchWithAuth('http://127.0.0.1:8000/trading/history');
        if (fallbackResponse.ok) {
          const data = await fallbackResponse.json();
          setTrades(data);
          setError('VST data unavailable, showing simulated trades');
        }
      } catch (fallbackError) {
        console.error('Fallback also failed:', fallbackError);
      }
    } finally {
      setLoading(false);
    }
  };

  const calculateStats = () => {
    const winning_trades = trades.filter(t => t.profit_loss > 0).length;
    const losing_trades = trades.filter(t => t.profit_loss < 0).length;
    const total_profit_loss = trades.reduce((sum, t) => sum + t.profit_loss, 0);
    const total_fees = trades.reduce((sum, t) => sum + t.fee, 0);
    const win_rate = trades.length > 0 ? (winning_trades / trades.length) * 100 : 0;
    
    const profits = trades.filter(t => t.profit_loss > 0).map(t => t.profit_loss);
    const losses = trades.filter(t => t.profit_loss < 0).map(t => t.profit_loss);
    
    const average_profit = profits.length > 0 ? profits.reduce((sum, p) => sum + p, 0) / profits.length : 0;
    const average_loss = losses.length > 0 ? losses.reduce((sum, l) => sum + l, 0) / losses.length : 0;
    const largest_win = profits.length > 0 ? Math.max(...profits) : 0;
    const largest_loss = losses.length > 0 ? Math.min(...losses) : 0;

    setStats({
      total_trades: trades.length,
      winning_trades,
      losing_trades,
      total_profit_loss,
      total_fees,
      win_rate,
      average_profit,
      average_loss,
      largest_win,
      largest_loss
    });
  };

  const filteredTrades = trades.filter(trade => {
    return (
      (filter.strategy === 'all' || trade.strategy_name === filter.strategy) &&
      (filter.symbol === 'all' || trade.symbol === filter.symbol) &&
      (filter.side === 'all' || trade.side === filter.side) &&
      (filter.status === 'all' || trade.status === filter.status)
    );
  });

  const uniqueStrategies = [...new Set(trades.map(t => t.strategy_name))];
  const uniqueSymbols = [...new Set(trades.map(t => t.symbol))];

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getProfitColor = (profit: number) => {
    if (profit > 0) return 'text-green-400';
    if (profit < 0) return 'text-red-400';
    return 'text-gray-400';
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card text-center">
          <p className="text-body">Loading trading history...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-h1 text-center mb-12">BingX VST Trading History</h1>

        {error && (
          <div className="linear-card bg-red-900/20 border-red-500/20 mb-6">
            <p className="text-red-400">{error}</p>
            <button onClick={() => setError(null)} className="linear-button-secondary mt-2">
              Dismiss
            </button>
          </div>
        )}

        {/* Trading Statistics */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Total Trades</p>
              <p className="text-h3 font-medium text-white">{stats.total_trades}</p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Win Rate</p>
              <p className="text-h3 font-medium text-green-400">{stats.win_rate.toFixed(1)}%</p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Total P&L</p>
              <p className={`text-h3 font-medium ${getProfitColor(stats.total_profit_loss)}`}>
                {formatCurrency(stats.total_profit_loss)}
              </p>
            </div>
            <div className="linear-card text-center">
              <p className="text-small text-secondary mb-1">Total Fees</p>
              <p className="text-h3 font-medium text-yellow-400">{formatCurrency(stats.total_fees)}</p>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="linear-card mb-6">
          <h2 className="text-h3 mb-4">Filters</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-small mb-2">Strategy</label>
              <select
                value={filter.strategy}
                onChange={(e) => setFilter(prev => ({ ...prev, strategy: e.target.value }))}
                className="linear-select w-full"
              >
                <option value="all">All Strategies</option>
                {uniqueStrategies.map(strategy => (
                  <option key={strategy} value={strategy}>{strategy}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-small mb-2">Symbol</label>
              <select
                value={filter.symbol}
                onChange={(e) => setFilter(prev => ({ ...prev, symbol: e.target.value }))}
                className="linear-select w-full"
              >
                <option value="all">All Symbols</option>
                {uniqueSymbols.map(symbol => (
                  <option key={symbol} value={symbol}>{symbol}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-small mb-2">Side</label>
              <select
                value={filter.side}
                onChange={(e) => setFilter(prev => ({ ...prev, side: e.target.value }))}
                className="linear-select w-full"
              >
                <option value="all">All Sides</option>
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </div>
            <div>
              <label className="block text-small mb-2">Status</label>
              <select
                value={filter.status}
                onChange={(e) => setFilter(prev => ({ ...prev, status: e.target.value }))}
                className="linear-select w-full"
              >
                <option value="all">All Status</option>
                <option value="completed">Completed</option>
                <option value="pending">Pending</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
          </div>
        </div>

        {/* Trading History Table */}
        <div className="linear-card">
          <h2 className="text-h3 mb-6">Recent Trades ({filteredTrades.length})</h2>
          
          {filteredTrades.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-body text-secondary">No trades found matching your filters.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left p-4 text-small font-medium text-secondary">Date</th>
                    <th className="text-left p-4 text-small font-medium text-secondary">Strategy</th>
                    <th className="text-left p-4 text-small font-medium text-secondary">Symbol</th>
                    <th className="text-left p-4 text-small font-medium text-secondary">Side</th>
                    <th className="text-right p-4 text-small font-medium text-secondary">Amount</th>
                    <th className="text-right p-4 text-small font-medium text-secondary">Price</th>
                    <th className="text-right p-4 text-small font-medium text-secondary">Fee</th>
                    <th className="text-right p-4 text-small font-medium text-secondary">P&L</th>
                    <th className="text-right p-4 text-small font-medium text-secondary">P&L %</th>
                    <th className="text-center p-4 text-small font-medium text-secondary">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTrades.map((trade) => (
                    <tr key={trade.id} className="border-b border-white/5 hover:bg-white/5">
                      <td className="p-4 text-small">{formatDate(trade.created_at)}</td>
                      <td className="p-4 text-small">{trade.strategy_name}</td>
                      <td className="p-4 text-small font-medium">{trade.symbol}</td>
                      <td className="p-4">
                        <span className={`text-small px-2 py-1 rounded ${
                          trade.side === 'buy' ? 'bg-green-900/20 text-green-400' : 'bg-red-900/20 text-red-400'
                        }`}>
                          {trade.side.toUpperCase()}
                        </span>
                      </td>
                      <td className="p-4 text-small text-right">{trade.amount.toFixed(4)}</td>
                      <td className="p-4 text-small text-right">{formatCurrency(trade.price)}</td>
                      <td className="p-4 text-small text-right">{formatCurrency(trade.fee)}</td>
                      <td className={`p-4 text-small text-right font-medium ${getProfitColor(trade.profit_loss)}`}>
                        {formatCurrency(trade.profit_loss)}
                      </td>
                      <td className={`p-4 text-small text-right font-medium ${getProfitColor(trade.profit_loss)}`}>
                        {trade.profit_loss_percentage.toFixed(2)}%
                      </td>
                      <td className="p-4 text-center">
                        <span className={`text-xs px-2 py-1 rounded ${
                          trade.status === 'completed' ? 'bg-blue-900/20 text-blue-400' :
                          trade.status === 'pending' ? 'bg-yellow-900/20 text-yellow-400' :
                          'bg-gray-900/20 text-gray-400'
                        }`}>
                          {trade.status.toUpperCase()}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}