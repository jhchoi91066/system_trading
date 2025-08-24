import pandas as pd
import numpy as np
import ccxt

def calculate_cci_standard(high, low, close, window=14):
    """표준 CCI 계산 (0.015 상수 사용)"""
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(window=window).mean()
    mad_tp = tp.rolling(window=window).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    cci = (tp - sma_tp) / (0.015 * mad_tp)
    return cci

def calculate_cci_alternative(high, low, close, window=14):
    """대안 CCI 계산 (다른 상수 사용)"""
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(window=window).mean()
    
    # 표준편차 기반 계산
    std_tp = tp.rolling(window=window).std()
    cci = (tp - sma_tp) / (0.015 * std_tp)
    return cci

def calculate_cci_talib_style(high, low, close, window=14):
    """TA-Lib 스타일 CCI 계산"""
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(window=window).mean()
    
    # Mean Absolute Deviation 계산 (다른 방식)
    mad_tp = tp.rolling(window=window).apply(
        lambda x: np.mean(np.abs(x - x.mean())), raw=False
    )
    cci = (tp - sma_tp) / (0.015 * mad_tp)
    return cci

# BTC/USDT 데이터 가져와서 비교
def test_cci_variations():
    exchange = ccxt.bingx()
    ohlcv = exchange.fetch_ohlcv('BTC/USDT', '5m', limit=50)
    
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # 다양한 CCI 계산
    df['cci_standard'] = calculate_cci_standard(df['high'], df['low'], df['close'], 14)
    df['cci_alternative'] = calculate_cci_alternative(df['high'], df['low'], df['close'], 14)
    df['cci_talib'] = calculate_cci_talib_style(df['high'], df['low'], df['close'], 14)
    
    # 최근 5개 값 출력
    print("최근 5개 CCI 값 비교:")
    print(df[['timestamp', 'close', 'cci_standard', 'cci_alternative', 'cci_talib']].tail(5))

if __name__ == "__main__":
    test_cci_variations()