"use client";

import { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, ColorType, UTCTimestamp } from 'lightweight-charts';

interface TradingChartProps {
  symbol?: string;
  exchange?: string;
  height?: number;
  interval?: string;
  onIntervalChange?: (interval: string) => void;
}

interface OHLCVData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export default function TradingChart({ 
  symbol = 'BTC/USDT', 
  exchange = 'binance',
  height = 500,
  interval = '1h',
  onIntervalChange
}: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const smaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const emaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);
  const [priceChangePercent, setPriceChangePercent] = useState<number>(0);
  const [showSMA, setShowSMA] = useState(false);
  const [showEMA, setShowEMA] = useState(false);
  const [smaPeriod, setSMAPeriod] = useState(20);
  const [emaPeriod, setEMAPeriod] = useState(20);
  const [mounted, setMounted] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>('--:--:--');

  useEffect(() => {
    setMounted(true);
    setLastUpdated(new Date().toLocaleTimeString());
  }, []);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    console.log('Creating chart with container:', chartContainerRef.current);
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#d1d5db',
        fontSize: 12,
        fontFamily: 'Inter, sans-serif',
      },
      grid: {
        vertLines: { color: '#374151', style: 2, visible: true },
        horzLines: { color: '#374151', style: 2, visible: true },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: '#6b7280',
          width: 1,
          style: 2,
          labelBackgroundColor: '#1f2937',
        },
        horzLine: {
          color: '#6b7280',
          width: 1,
          style: 2,
          labelBackgroundColor: '#1f2937',
        },
      },
      rightPriceScale: {
        borderColor: '#374151',
        textColor: '#d1d5db',
        entireTextOnly: true,
      },
      timeScale: {
        borderColor: '#374151',
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: true,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });

    // Create candlestick series
    console.log('Chart object:', chart);
    console.log('Available methods:', Object.getOwnPropertyNames(chart));
    
    let candlestickSeries;
    try {
      if (typeof chart.addCandlestickSeries === 'function') {
        candlestickSeries = chart.addCandlestickSeries({
          upColor: '#10b981',
          downColor: '#ef4444',
          borderDownColor: '#ef4444',
          borderUpColor: '#10b981',
          wickDownColor: '#ef4444',
          wickUpColor: '#10b981',
          priceFormat: {
            type: 'price',
            precision: 2,
            minMove: 0.01,
          },
        });
      } else {
        console.error('addCandlestickSeries method not found on chart object');
        setError('Chart library error: addCandlestickSeries not available');
        return;
      }
    } catch (error) {
      console.error('Error creating candlestick series:', error);
      setError(`Chart error: ${error.message}`);
      return;
    }

    // Create volume series
    const volumeSeries = chart.addHistogramSeries({
      color: '#6b7280',
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: 'volume',
      scaleMargins: {
        top: 0.7,
        bottom: 0,
      },
    });

    // Set up volume price scale
    chart.priceScale('volume').applyOptions({
      scaleMargins: {
        top: 0.7,
        bottom: 0,
      },
    });

    // Create SMA series
    const smaSeries = chart.addLineSeries({
      color: '#3b82f6',
      lineWidth: 2,
      title: `SMA(${smaPeriod})`,
      visible: showSMA,
    });

    // Create EMA series
    const emaSeries = chart.addLineSeries({
      color: '#f59e0b',
      lineWidth: 2,
      title: `EMA(${emaPeriod})`,
      visible: showEMA,
    });

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;
    smaSeriesRef.current = smaSeries;
    emaSeriesRef.current = emaSeries;

    // Load initial data
    loadChartData();

    // Handle resize
    const resizeObserver = new ResizeObserver(() => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    });

    if (chartContainerRef.current) {
      resizeObserver.observe(chartContainerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
      }
    };
  }, [symbol, exchange, interval, height]);

  const loadChartData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch OHLCV data from backend
      const response = await fetch(
        `http://127.0.0.1:8000/ohlcv/${exchange}/${encodeURIComponent(symbol)}?timeframe=${interval}&limit=200`
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch chart data: ${response.statusText}`);
      }

      const ohlcvData: number[][] = await response.json();
      
      if (!ohlcvData || ohlcvData.length === 0) {
        throw new Error('No chart data available');
      }

      // Convert to chart format
      const candlestickData: CandlestickData[] = ohlcvData.map((item) => ({
        time: (item[0] / 1000) as UTCTimestamp, // Convert to seconds
        open: item[1],
        high: item[2],
        low: item[3],
        close: item[4],
      }));

      const volumeData = ohlcvData.map((item) => ({
        time: (item[0] / 1000) as UTCTimestamp,
        value: item[5],
        color: item[4] >= item[1] ? '#10b98160' : '#ef444460', // Green if close >= open
      }));

      // Set data to series
      if (seriesRef.current && volumeSeriesRef.current) {
        seriesRef.current.setData(candlestickData);
        volumeSeriesRef.current.setData(volumeData);

        // Update technical indicators
        updateIndicators(candlestickData);

        // Calculate price change
        if (candlestickData.length >= 2) {
          const current = candlestickData[candlestickData.length - 1];
          const previous = candlestickData[candlestickData.length - 2];
          
          setCurrentPrice(current.close);
          const change = current.close - previous.close;
          const changePercent = (change / previous.close) * 100;
          
          setPriceChange(change);
          setPriceChangePercent(changePercent);
        }

        // Fit content
        chartRef.current?.timeScale().fitContent();
      }

      setLoading(false);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err: any) {
      console.error('Error loading chart data:', err);
      setError(err.message);
      setLoading(false);
    }
  };

  const refreshChart = () => {
    loadChartData();
  };

  // Technical indicator calculations
  const calculateSMA = (data: CandlestickData[], period: number) => {
    const smaData = [];
    for (let i = period - 1; i < data.length; i++) {
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += data[i - j].close;
      }
      const average = sum / period;
      smaData.push({
        time: data[i].time,
        value: average,
      });
    }
    return smaData;
  };

  const calculateEMA = (data: CandlestickData[], period: number) => {
    const emaData = [];
    const multiplier = 2 / (period + 1);
    
    // First EMA is SMA
    if (data.length >= period) {
      let sum = 0;
      for (let i = 0; i < period; i++) {
        sum += data[i].close;
      }
      const firstEMA = sum / period;
      emaData.push({
        time: data[period - 1].time,
        value: firstEMA,
      });

      // Calculate subsequent EMAs
      for (let i = period; i < data.length; i++) {
        const ema = (data[i].close - emaData[emaData.length - 1].value) * multiplier + emaData[emaData.length - 1].value;
        emaData.push({
          time: data[i].time,
          value: ema,
        });
      }
    }
    return emaData;
  };

  const updateIndicators = (candlestickData: CandlestickData[]) => {
    if (showSMA && smaSeriesRef.current) {
      const smaData = calculateSMA(candlestickData, smaPeriod);
      smaSeriesRef.current.setData(smaData);
    }

    if (showEMA && emaSeriesRef.current) {
      const emaData = calculateEMA(candlestickData, emaPeriod);
      emaSeriesRef.current.setData(emaData);
    }
  };

  // Update indicators when settings change
  useEffect(() => {
    if (smaSeriesRef.current) {
      smaSeriesRef.current.applyOptions({ 
        visible: showSMA,
        title: `SMA(${smaPeriod})`,
      });
    }
    if (emaSeriesRef.current) {
      emaSeriesRef.current.applyOptions({ 
        visible: showEMA,
        title: `EMA(${emaPeriod})`,
      });
    }
  }, [showSMA, showEMA, smaPeriod, emaPeriod]);

  return (
    <div className="linear-card p-0 overflow-hidden">
      {/* Chart Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <h3 className="text-h4 font-medium text-white">
              {symbol} Chart
            </h3>
            <div className="flex items-center space-x-2">
              <span className="text-xs px-2 py-1 bg-blue-600 rounded text-white">
                {interval.toUpperCase()}
              </span>
              <span className="text-xs px-2 py-1 bg-gray-600 rounded text-white">
                {exchange.toUpperCase()}
              </span>
            </div>
          </div>
          
          {/* Price Info */}
          <div className="flex items-center space-x-4">
            {currentPrice > 0 && (
              <div className="text-right">
                <div className="text-h4 font-bold text-white">
                  ${currentPrice.toLocaleString()}
                </div>
                <div className={`text-sm ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {priceChange >= 0 ? '+' : ''}${priceChange.toFixed(2)} ({priceChangePercent.toFixed(2)}%)
                </div>
              </div>
            )}
            
            <button
              onClick={refreshChart}
              disabled={loading}
              className="linear-button-secondary py-2 px-3 text-sm disabled:opacity-50"
            >
              {loading ? '⏳' : '🔄'}
            </button>
          </div>
        </div>
      </div>

      {/* Chart Container */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900 bg-opacity-75 z-10">
            <div className="text-center">
              <div className="animate-spin text-2xl mb-2">⏳</div>
              <div className="text-secondary">Loading chart data...</div>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900 bg-opacity-75 z-10">
            <div className="text-center">
              <div className="text-2xl mb-2">⚠️</div>
              <div className="text-red-400 mb-4">{error}</div>
              <button
                onClick={refreshChart}
                className="linear-button-primary py-2 px-4"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        <div 
          ref={chartContainerRef}
          className="w-full"
          style={{ height: `${height}px` }}
        />
      </div>

      {/* Chart Controls */}
      <div className="p-4 border-t border-gray-700 space-y-4">
        {/* Timeframe Controls */}
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-2">
            <span className="text-small text-secondary">Timeframe:</span>
            <div className="flex space-x-1">
              {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
                <button
                  key={tf}
                  onClick={() => {
                    if (onIntervalChange && tf !== interval) {
                      onIntervalChange(tf);
                    }
                  }}
                  className={`px-2 py-1 text-xs rounded transition-colors ${
                    tf === interval
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-xs text-secondary">
              Last updated: {lastUpdated}
            </span>
          </div>
        </div>

        {/* Technical Indicators */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <span className="text-small text-secondary">Indicators:</span>
          </div>
          
          {/* SMA Controls */}
          <div className="flex items-center space-x-2">
            <label className="flex items-center space-x-1">
              <input
                type="checkbox"
                checked={showSMA}
                onChange={(e) => setShowSMA(e.target.checked)}
                className="rounded"
              />
              <span className="text-xs text-secondary">SMA</span>
            </label>
            <input
              type="number"
              value={smaPeriod}
              onChange={(e) => setSMAPeriod(parseInt(e.target.value) || 20)}
              min="1"
              max="200"
              className="w-12 px-1 py-0.5 text-xs bg-gray-700 border border-gray-600 rounded text-white"
            />
          </div>

          {/* EMA Controls */}
          <div className="flex items-center space-x-2">
            <label className="flex items-center space-x-1">
              <input
                type="checkbox"
                checked={showEMA}
                onChange={(e) => setShowEMA(e.target.checked)}
                className="rounded"
              />
              <span className="text-xs text-secondary">EMA</span>
            </label>
            <input
              type="number"
              value={emaPeriod}
              onChange={(e) => setEMAPeriod(parseInt(e.target.value) || 20)}
              min="1"
              max="200"
              className="w-12 px-1 py-0.5 text-xs bg-gray-700 border border-gray-600 rounded text-white"
            />
          </div>

          {/* Indicator Legend */}
          {(showSMA || showEMA) && (
            <div className="flex items-center space-x-3 ml-4">
              {showSMA && (
                <div className="flex items-center space-x-1">
                  <div className="w-3 h-0.5 bg-blue-500"></div>
                  <span className="text-xs text-secondary">SMA({smaPeriod})</span>
                </div>
              )}
              {showEMA && (
                <div className="flex items-center space-x-1">
                  <div className="w-3 h-0.5 bg-yellow-500"></div>
                  <span className="text-xs text-secondary">EMA({emaPeriod})</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}