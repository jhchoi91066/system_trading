"""
Bitcoin Trading Bot용 고급 기술적 지표 구현
볼린저 밴드, 스토캐스틱 RSI, MACD, Williams %R 등
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
import math

class AdvancedIndicators:
    @staticmethod
    def bollinger_bands(prices: List[float], window: int = 20, std_dev: float = 2.0) -> Dict:
        """
        볼린저 밴드 계산
        
        Args:
            prices: 종가 리스트
            window: 이동평균 기간 (기본값: 20)
            std_dev: 표준편차 배수 (기본값: 2.0)
            
        Returns:
            Dict: upper_band, middle_band(SMA), lower_band, bandwidth, %b
        """
        if len(prices) < window:
            return {
                "upper_band": [None] * len(prices),
                "middle_band": [None] * len(prices), 
                "lower_band": [None] * len(prices),
                "bandwidth": [None] * len(prices),
                "percent_b": [None] * len(prices)
            }
        
        df = pd.DataFrame({'close': prices})
        
        # 중간선 (20일 단순이동평균)
        df['middle_band'] = df['close'].rolling(window=window).mean()
        
        # 표준편차
        rolling_std = df['close'].rolling(window=window).std()
        
        # 상단선과 하단선
        df['upper_band'] = df['middle_band'] + (rolling_std * std_dev)
        df['lower_band'] = df['middle_band'] - (rolling_std * std_dev)
        
        # 밴드폭 (상단선과 하단선의 차이를 중간선으로 나눈 값)
        df['bandwidth'] = (df['upper_band'] - df['lower_band']) / df['middle_band'] * 100
        
        # %B (현재가가 밴드 내에서 어느 위치에 있는지)
        df['percent_b'] = (df['close'] - df['lower_band']) / (df['upper_band'] - df['lower_band']) * 100
        
        return {
            "upper_band": df['upper_band'].fillna(None).tolist(),
            "middle_band": df['middle_band'].fillna(None).tolist(),
            "lower_band": df['lower_band'].fillna(None).tolist(),
            "bandwidth": df['bandwidth'].fillna(None).tolist(),
            "percent_b": df['percent_b'].fillna(None).tolist()
        }
    
    @staticmethod
    def stochastic_rsi(prices: List[float], rsi_period: int = 14, stoch_period: int = 14, 
                      k_period: int = 3, d_period: int = 3) -> Dict:
        """
        스토캐스틱 RSI 계산
        
        Args:
            prices: 종가 리스트
            rsi_period: RSI 계산 기간 (기본값: 14)
            stoch_period: 스토캐스틱 계산 기간 (기본값: 14)
            k_period: %K 스무딩 기간 (기본값: 3)
            d_period: %D 스무딩 기간 (기본값: 3)
            
        Returns:
            Dict: stoch_rsi, k_percent, d_percent
        """
        if len(prices) < max(rsi_period, stoch_period) + k_period + d_period:
            return {
                "stoch_rsi": [None] * len(prices),
                "k_percent": [None] * len(prices),
                "d_percent": [None] * len(prices)
            }
        
        df = pd.DataFrame({'close': prices})
        
        # RSI 계산
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # 스토캐스틱 RSI 계산
        rsi_min = rsi.rolling(window=stoch_period).min()
        rsi_max = rsi.rolling(window=stoch_period).max()
        stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min) * 100
        
        # %K와 %D 계산 (스무딩)
        k_percent = stoch_rsi.rolling(window=k_period).mean()
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            "stoch_rsi": stoch_rsi.fillna(None).tolist(),
            "k_percent": k_percent.fillna(None).tolist(),
            "d_percent": d_percent.fillna(None).tolist()
        }
    
    @staticmethod
    def macd(prices: List[float], fast_period: int = 12, slow_period: int = 26, 
             signal_period: int = 9) -> Dict:
        """
        MACD (Moving Average Convergence Divergence) 계산
        
        Args:
            prices: 종가 리스트
            fast_period: 빠른 EMA 기간 (기본값: 12)
            slow_period: 느린 EMA 기간 (기본값: 26)
            signal_period: 시그널 라인 EMA 기간 (기본값: 9)
            
        Returns:
            Dict: macd_line, signal_line, histogram
        """
        if len(prices) < slow_period + signal_period:
            return {
                "macd_line": [None] * len(prices),
                "signal_line": [None] * len(prices),
                "histogram": [None] * len(prices)
            }
        
        df = pd.DataFrame({'close': prices})
        
        # EMA 계산
        ema_fast = df['close'].ewm(span=fast_period).mean()
        ema_slow = df['close'].ewm(span=slow_period).mean()
        
        # MACD 라인
        macd_line = ema_fast - ema_slow
        
        # 시그널 라인 (MACD의 EMA)
        signal_line = macd_line.ewm(span=signal_period).mean()
        
        # 히스토그램 (MACD - Signal)
        histogram = macd_line - signal_line
        
        return {
            "macd_line": macd_line.fillna(None).tolist(),
            "signal_line": signal_line.fillna(None).tolist(),
            "histogram": histogram.fillna(None).tolist()
        }
    
    @staticmethod
    def williams_percent_r(highs: List[float], lows: List[float], closes: List[float], 
                          period: int = 14) -> List[Optional[float]]:
        """
        Williams %R 계산
        
        Args:
            highs: 고가 리스트
            lows: 저가 리스트
            closes: 종가 리스트
            period: 계산 기간 (기본값: 14)
            
        Returns:
            List: Williams %R 값들
        """
        if len(closes) < period:
            return [None] * len(closes)
        
        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })
        
        # 주어진 기간 동안의 최고가와 최저가
        highest_high = df['high'].rolling(window=period).max()
        lowest_low = df['low'].rolling(window=period).min()
        
        # Williams %R 계산
        williams_r = -100 * (highest_high - df['close']) / (highest_high - lowest_low)
        
        return williams_r.fillna(None).tolist()
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
        """
        RSI (Relative Strength Index) 계산
        
        Args:
            prices: 종가 리스트
            period: 계산 기간 (기본값: 14)
            
        Returns:
            List: RSI 값들
        """
        if len(prices) < period + 1:
            return [None] * len(prices)
        
        df = pd.DataFrame({'close': prices})
        
        # 가격 변화량 계산
        delta = df['close'].diff()
        
        # 상승분과 하락분 분리
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # RS와 RSI 계산
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.fillna(None).tolist()
    
    @staticmethod
    def cci(highs: List[float], lows: List[float], closes: List[float], 
            period: int = 20) -> List[Optional[float]]:
        """
        CCI (Commodity Channel Index) 계산
        
        Args:
            highs: 고가 리스트
            lows: 저가 리스트
            closes: 종가 리스트
            period: 계산 기간 (기본값: 20)
            
        Returns:
            List: CCI 값들
        """
        if len(closes) < period:
            return [None] * len(closes)
        
        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })
        
        # Typical Price 계산
        tp = (df['high'] + df['low'] + df['close']) / 3
        
        # SMA와 Mean Deviation 계산
        sma = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: np.mean(np.abs(x - x.mean())))
        
        # CCI 계산
        cci = (tp - sma) / (0.015 * mad)
        
        return cci.fillna(None).tolist()
    
    @staticmethod
    def atr(highs: List[float], lows: List[float], closes: List[float], 
            period: int = 14) -> List[Optional[float]]:
        """
        ATR (Average True Range) 계산
        
        Args:
            highs: 고가 리스트
            lows: 저가 리스트
            closes: 종가 리스트
            period: 계산 기간 (기본값: 14)
            
        Returns:
            List: ATR 값들
        """
        if len(closes) < period + 1:
            return [None] * len(closes)
        
        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })
        
        # True Range 계산
        df['prev_close'] = df['close'].shift(1)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['prev_close'])
        df['tr3'] = abs(df['low'] - df['prev_close'])
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # ATR 계산 (True Range의 이동평균)
        atr = df['tr'].rolling(window=period).mean()
        
        return atr.fillna(None).tolist()
    
    @staticmethod
    def fibonacci_retracement(high: float, low: float) -> Dict[str, float]:
        """
        피보나치 되돌림 수준 계산
        
        Args:
            high: 최고가
            low: 최저가
            
        Returns:
            Dict: 각 피보나치 수준별 가격
        """
        diff = high - low
        
        return {
            "level_0": high,
            "level_236": high - (diff * 0.236),
            "level_382": high - (diff * 0.382), 
            "level_500": high - (diff * 0.500),
            "level_618": high - (diff * 0.618),
            "level_786": high - (diff * 0.786),
            "level_100": low
        }
    
    @staticmethod
    def support_resistance_levels(highs: List[float], lows: List[float], 
                                 window: int = 20, min_touches: int = 2) -> Dict:
        """
        지지/저항 수준 감지
        
        Args:
            highs: 고가 리스트
            lows: 저가 리스트
            window: 피크/골 감지 윈도우
            min_touches: 최소 터치 횟수
            
        Returns:
            Dict: 지지선과 저항선 수준들
        """
        if len(highs) < window * 2:
            return {"resistance_levels": [], "support_levels": []}
        
        # 피크와 골 찾기
        highs_array = np.array(highs)
        lows_array = np.array(lows)
        
        peaks = []
        troughs = []
        
        for i in range(window, len(highs) - window):
            # 저항선 (피크)
            if highs_array[i] == max(highs_array[i-window:i+window+1]):
                peaks.append(highs_array[i])
            
            # 지지선 (골)
            if lows_array[i] == min(lows_array[i-window:i+window+1]):
                troughs.append(lows_array[i])
        
        # 비슷한 수준끼리 그룹화
        def group_levels(levels, tolerance=0.02):
            if not levels:
                return []
            
            grouped = []
            levels.sort()
            current_group = [levels[0]]
            
            for level in levels[1:]:
                if abs(level - current_group[0]) / current_group[0] <= tolerance:
                    current_group.append(level)
                else:
                    if len(current_group) >= min_touches:
                        grouped.append(np.mean(current_group))
                    current_group = [level]
            
            if len(current_group) >= min_touches:
                grouped.append(np.mean(current_group))
            
            return grouped
        
        resistance_levels = group_levels(peaks)
        support_levels = group_levels(troughs)
        
        return {
            "resistance_levels": resistance_levels,
            "support_levels": support_levels
        }

# 사용 예시를 위한 헬퍼 함수들
def calculate_all_indicators(ohlcv_data: List[List[float]]) -> Dict:
    """
    OHLCV 데이터로부터 모든 지표를 계산
    
    Args:
        ohlcv_data: [[timestamp, open, high, low, close, volume], ...]
        
    Returns:
        Dict: 모든 계산된 지표들
    """
    if not ohlcv_data or len(ohlcv_data) < 20:
        return {}
    
    # 데이터 분리
    timestamps = [candle[0] for candle in ohlcv_data]
    opens = [candle[1] for candle in ohlcv_data]
    highs = [candle[2] for candle in ohlcv_data]
    lows = [candle[3] for candle in ohlcv_data]
    closes = [candle[4] for candle in ohlcv_data]
    volumes = [candle[5] for candle in ohlcv_data]
    
    indicators = AdvancedIndicators()
    
    # 모든 지표 계산
    bollinger = indicators.bollinger_bands(closes)
    stoch_rsi = indicators.stochastic_rsi(closes)
    macd = indicators.macd(closes)
    williams_r = indicators.williams_percent_r(highs, lows, closes)
    rsi = indicators.rsi(closes)
    cci = indicators.cci(highs, lows, closes)
    atr = indicators.atr(highs, lows, closes)
    
    # 지지/저항 수준
    if len(highs) >= 40:
        sr_levels = indicators.support_resistance_levels(highs, lows)
    else:
        sr_levels = {"resistance_levels": [], "support_levels": []}
    
    # 피보나치 되돌림 (최근 고점과 저점 기준)
    recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    recent_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    fibonacci = indicators.fibonacci_retracement(recent_high, recent_low)
    
    return {
        "timestamps": timestamps,
        "ohlcv": {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes
        },
        "bollinger_bands": bollinger,
        "stochastic_rsi": stoch_rsi,
        "macd": macd,
        "williams_r": williams_r,
        "rsi": rsi,
        "cci": cci,
        "atr": atr,
        "support_resistance": sr_levels,
        "fibonacci": fibonacci,
        "current_price": closes[-1] if closes else None,
        "price_change": ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else 0
    }