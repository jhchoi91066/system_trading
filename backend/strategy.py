import pandas as pd
import numpy as np
from advanced_indicators import AdvancedIndicators, calculate_all_indicators

def calculate_cci(high, low, close, window=20):
    """
    표준 CCI 계산
    CCI = (Typical Price - SMA of TP) / (0.015 * Mean Absolute Deviation)
    """
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(window=window).mean()
    mad_tp = tp.rolling(window=window).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    cci = (tp - sma_tp) / (0.015 * mad_tp)
    return cci

def calculate_cci_talib_style(high, low, close, window=14):
    """
    TA-Lib 스타일 CCI 계산 (더 정확한 MAD 계산)
    """
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(window=window).mean()
    
    # TA-Lib 스타일 MAD 계산
    mad_tp = tp.rolling(window=window).apply(
        lambda x: np.sum(np.abs(x - np.mean(x))) / len(x), raw=True
    )
    cci = (tp - sma_tp) / (0.015 * mad_tp)
    return cci

def calculate_bollinger_bands(df, window=20, num_std_dev=2):
    df['middle_band'] = df['close'].rolling(window=window).mean()
    df['std_dev'] = df['close'].rolling(window=window).std()
    df['upper_band'] = df['middle_band'] + (df['std_dev'] * num_std_dev)
    df['lower_band'] = df['middle_band'] - (df['std_dev'] * num_std_dev)
    return df

def calculate_stochastic_oscillator(df, k_window=14, d_window=3):
    # Calculate %K
    df['lowest_low'] = df['low'].rolling(window=k_window).min()
    df['highest_high'] = df['high'].rolling(window=k_window).max()
    df['%K'] = ((df['close'] - df['lowest_low']) / (df['highest_high'] - df['lowest_high'])) * 100
    
    # Calculate %D (3-period SMA of %K)
    df['%D'] = df['%K'].rolling(window=d_window).mean()
    
    return df

async def generate_cci_signals_external(ohlcv_data, symbol, window=20, buy_threshold=-100, sell_threshold=100):
    """외부 CCI 지표를 사용한 신호 생성 (TAAPI.IO)"""
    from external_cci_client import HybridCCIClient
    
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # 하이브리드 CCI 클라이언트 초기화
    cci_client = HybridCCIClient()
    
    # 외부 CCI 값 가져오기 (실패 시 내부 계산으로 백업)
    current_cci = await cci_client.get_cci_value(
        symbol=symbol,
        ohlcv_data=ohlcv_data,
        exchange="binance",  # BingX보다 Binance가 더 안정적
        interval="5m",
        period=window
    )
    
    if current_cci is None:
        print(f"❌ CCI 값을 가져올 수 없습니다: {symbol}")
        return pd.DataFrame({'signal': [0] * len(df)}, index=df.index)
    
    # 이전 CCI 값을 위해 내부 계산 사용 (크로스오버 감지를 위함)
    df['cci'] = calculate_cci(df['high'], df['low'], df['close'], window)
    
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0
    
    # 최신 캔들에서만 신호 확인 (현재 CCI 값 사용)
    if len(df) >= 2:
        last_idx = len(df) - 1
        prev_cci = df['cci'].iloc[last_idx-1] if not pd.isna(df['cci'].iloc[last_idx-1]) else 0
        
        # 매수 신호: CCI가 -100 아래에서 -100 위로 상향 돌파
        if prev_cci < buy_threshold and current_cci >= buy_threshold:
            signals.iloc[last_idx, signals.columns.get_loc('signal')] = 1
            print(f"📈 CCI 매수 신호: {symbol} (이전: {prev_cci:.2f} → 현재: {current_cci:.2f})")
            
        # 매도 신호: CCI가 +100 위에서 +100 아래로 하향 돌파  
        elif prev_cci > sell_threshold and current_cci <= sell_threshold:
            signals.iloc[last_idx, signals.columns.get_loc('signal')] = -1
            print(f"📉 CCI 매도 신호: {symbol} (이전: {prev_cci:.2f} → 현재: {current_cci:.2f})")
    
    return signals

def generate_cci_signals(ohlcv_data, window=20, buy_threshold=-100, sell_threshold=100):
    """기존 내부 CCI 계산을 사용한 신호 생성 (백업용)"""
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['cci'] = calculate_cci(df['high'], df['low'], df['close'], window)

    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0

    # CCI 크로스오버 전략
    # Buy signal: CCI가 -100 아래에서 -100 위로 상향 돌파
    for i in range(1, len(df)):
        prev_cci = df['cci'].iloc[i-1]
        curr_cci = df['cci'].iloc[i]
        
        # 매수 신호: CCI가 -100 아래에서 -100 위로 상향 돌파
        if prev_cci < buy_threshold and curr_cci >= buy_threshold:
            signals.iloc[i, signals.columns.get_loc('signal')] = 1
            
        # 매도 신호: CCI가 +100 위에서 +100 아래로 하향 돌파  
        elif prev_cci > sell_threshold and curr_cci <= sell_threshold:
            signals.iloc[i, signals.columns.get_loc('signal')] = -1

    return signals

def backtest_strategy(ohlcv_data, window=20, buy_threshold=100, sell_threshold=-100, initial_capital=10000, commission=0.001):
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['cci'] = calculate_cci(df['high'], df['low'], df['close'], window)

    signals = generate_cci_signals(ohlcv_data, window, buy_threshold, sell_threshold)
    df['signal'] = signals['signal']

    capital = initial_capital
    position = 0 # 0: no position, 1: long, -1: short
    buy_price = 0 # Track the price of the last buy order
    buy_amount = 0 # Track the amount of the last buy order
    trades = []
    
    for i in range(len(df)):
        current_price = df['close'].iloc[i]
        signal = df['signal'].iloc[i]

        if signal == 1 and position == 0: # Buy signal and no open position
            # Buy at current price
            buy_amount = capital / current_price # Invest all available capital
            fee = buy_amount * current_price * commission
            capital -= fee
            position = 1
            buy_price = current_price
            trades.append({
                'type': 'buy',
                'price': current_price,
                'amount': buy_amount,
                'capital': capital,
                'timestamp': int(df['timestamp'].iloc[i]),
                'fee': fee,
                'profit_loss': 0.0, # No PnL on buy
                'profit_percent': 0.0 # No PnL on buy
            })

        elif signal == -1 and position == 1: # Sell signal and long position
            # Sell at current price
            fee = buy_amount * current_price * commission
            capital += buy_amount * current_price - fee
            
            profit_loss = (buy_amount * current_price) - (buy_amount * buy_price) - fee # Simple PnL
            profit_percent = (profit_loss / (buy_amount * buy_price)) * 100 if (buy_amount * buy_price) != 0 else 0
            
            position = 0
            trades.append({
                'type': 'sell',
                'price': current_price,
                'amount': buy_amount,
                'capital': capital,
                'timestamp': int(df['timestamp'].iloc[i]),
                'fee': fee,
                'profit_loss': profit_loss,
                'profit_percent': profit_percent
            })

    # If there's an open position at the end, close it
    if position == 1:
        final_price = df['close'].iloc[-1] # Use the last available close price
        fee = buy_amount * final_price * commission
        capital += buy_amount * final_price - fee
        
        profit_loss = (buy_amount * final_price) - (buy_amount * buy_price) - fee
        profit_percent = (profit_loss / (buy_amount * buy_price)) * 100 if (buy_amount * buy_price) != 0 else 0
        
        position = 0
        trades.append({
            'type': 'close',
            'price': final_price,
            'amount': buy_amount,
            'capital': capital,
            'timestamp': int(df['timestamp'].iloc[-1]),
            'fee': fee,
            'profit_loss': profit_loss,
            'profit_percent': profit_percent
        })

    final_capital = float(capital)
    profit_loss_total = float(final_capital - initial_capital)
    
    # Calculate trade statistics
    winning_trades = [t for t in trades if t['type'] != 'buy' and t['profit_loss'] > 0]
    losing_trades = [t for t in trades if t['type'] != 'buy' and t['profit_loss'] < 0]
    total_closed_trades = len(winning_trades) + len(losing_trades)
    win_rate = (len(winning_trades) / total_closed_trades) * 100 if total_closed_trades > 0 else 0

    return {
        "initial_capital": float(initial_capital),
        "final_capital": final_capital,
        "profit_loss": profit_loss_total,
        "total_trades": total_closed_trades,
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": win_rate,
        "trades": trades
    }

# 새로운 고급 전략들

def bollinger_bands_strategy(ohlcv_data, window=20, std_dev=2.0, rsi_period=14):
    """
    볼린저 밴드 + RSI 조합 전략
    - 하단 밴드 근처에서 RSI가 과매도일 때 매수
    - 상단 밴드 근처에서 RSI가 과매수일 때 매도
    """
    if len(ohlcv_data) < max(window, rsi_period) + 10:
        return []
    
    indicators = AdvancedIndicators()
    closes = [candle[4] for candle in ohlcv_data]
    timestamps = [candle[0] for candle in ohlcv_data]
    
    # 지표 계산
    bb_data = indicators.bollinger_bands(closes, window, std_dev)
    rsi_data = indicators.rsi(closes, rsi_period)
    
    signals = []
    
    for i in range(len(closes)):
        if (bb_data['lower_band'][i] is None or 
            bb_data['upper_band'][i] is None or 
            rsi_data[i] is None):
            continue
            
        current_price = closes[i]
        lower_band = bb_data['lower_band'][i]
        upper_band = bb_data['upper_band'][i]
        rsi = rsi_data[i]
        percent_b = bb_data['percent_b'][i]
        
        # 매수 신호: 가격이 하단 밴드 근처 + RSI 과매도
        if (percent_b < 20 and rsi < 30 and 
            current_price <= lower_band * 1.02):
            signals.append({
                'timestamp': timestamps[i],
                'signal': 'buy',
                'price': current_price,
                'reason': f'BB하단돌파+RSI과매도 (RSI:{rsi:.1f}, %B:{percent_b:.1f})'
            })
        
        # 매도 신호: 가격이 상단 밴드 근처 + RSI 과매수
        elif (percent_b > 80 and rsi > 70 and 
              current_price >= upper_band * 0.98):
            signals.append({
                'timestamp': timestamps[i],
                'signal': 'sell',
                'price': current_price,
                'reason': f'BB상단도달+RSI과매수 (RSI:{rsi:.1f}, %B:{percent_b:.1f})'
            })
    
    return signals

def macd_stochastic_strategy(ohlcv_data, fast_ema=12, slow_ema=26, signal_ema=9, 
                           stoch_rsi_period=14, k_period=3, d_period=3):
    """
    MACD + 스토캐스틱 RSI 조합 전략
    - MACD 골든크로스 + 스토캐스틱 RSI 과매도에서 매수
    - MACD 데드크로스 + 스토캐스틱 RSI 과매수에서 매도
    """
    if len(ohlcv_data) < max(slow_ema, stoch_rsi_period) + max(k_period, d_period) + 10:
        return []
    
    indicators = AdvancedIndicators()
    closes = [candle[4] for candle in ohlcv_data]
    timestamps = [candle[0] for candle in ohlcv_data]
    
    # 지표 계산
    macd_data = indicators.macd(closes, fast_ema, slow_ema, signal_ema)
    stoch_rsi_data = indicators.stochastic_rsi(closes, stoch_rsi_period, 
                                             stoch_rsi_period, k_period, d_period)
    
    signals = []
    
    for i in range(1, len(closes)):
        if (macd_data['macd_line'][i] is None or 
            macd_data['signal_line'][i] is None or
            stoch_rsi_data['k_percent'][i] is None or
            stoch_rsi_data['d_percent'][i] is None):
            continue
            
        current_price = closes[i]
        prev_macd = macd_data['macd_line'][i-1]
        curr_macd = macd_data['macd_line'][i]
        prev_signal = macd_data['signal_line'][i-1]
        curr_signal = macd_data['signal_line'][i]
        
        k_percent = stoch_rsi_data['k_percent'][i]
        d_percent = stoch_rsi_data['d_percent'][i]
        
        # MACD 골든크로스 감지
        macd_bullish = (prev_macd <= prev_signal and curr_macd > curr_signal)
        
        # MACD 데드크로스 감지  
        macd_bearish = (prev_macd >= prev_signal and curr_macd < curr_signal)
        
        # 매수 신호: MACD 골든크로스 + 스토캐스틱 RSI 과매도
        if macd_bullish and k_percent < 20 and d_percent < 20:
            signals.append({
                'timestamp': timestamps[i],
                'signal': 'buy',
                'price': current_price,
                'reason': f'MACD골든크로스+StochRSI과매도 (K:{k_percent:.1f}, D:{d_percent:.1f})'
            })
        
        # 매도 신호: MACD 데드크로스 + 스토캐스틱 RSI 과매수
        elif macd_bearish and k_percent > 80 and d_percent > 80:
            signals.append({
                'timestamp': timestamps[i],
                'signal': 'sell',
                'price': current_price,
                'reason': f'MACD데드크로스+StochRSI과매수 (K:{k_percent:.1f}, D:{d_percent:.1f})'
            })
    
    return signals

def williams_r_mean_reversion_strategy(ohlcv_data, williams_period=14, 
                                     oversold=-80, overbought=-20):
    """
    Williams %R 평균회귀 전략
    - Williams %R이 과매도 영역에서 반등할 때 매수
    - Williams %R이 과매수 영역에서 하락할 때 매도
    """
    if len(ohlcv_data) < williams_period + 10:
        return []
    
    indicators = AdvancedIndicators()
    highs = [candle[2] for candle in ohlcv_data]
    lows = [candle[3] for candle in ohlcv_data]
    closes = [candle[4] for candle in ohlcv_data]
    timestamps = [candle[0] for candle in ohlcv_data]
    
    # Williams %R 계산
    williams_r = indicators.williams_percent_r(highs, lows, closes, williams_period)
    
    signals = []
    
    for i in range(2, len(closes)):
        if williams_r[i] is None or williams_r[i-1] is None or williams_r[i-2] is None:
            continue
            
        current_price = closes[i]
        curr_wr = williams_r[i]
        prev_wr = williams_r[i-1]
        prev2_wr = williams_r[i-2]
        
        # 매수 신호: 과매도에서 반등 (상향 전환)
        if (prev2_wr < oversold and prev_wr < oversold and 
            curr_wr > prev_wr and curr_wr > oversold):
            signals.append({
                'timestamp': timestamps[i],
                'signal': 'buy',
                'price': current_price,
                'reason': f'Williams%R 과매도반등 (WR:{curr_wr:.1f})'
            })
        
        # 매도 신호: 과매수에서 하락 (하향 전환)
        elif (prev2_wr > overbought and prev_wr > overbought and 
              curr_wr < prev_wr and curr_wr < overbought):
            signals.append({
                'timestamp': timestamps[i],
                'signal': 'sell',
                'price': current_price,
                'reason': f'Williams%R 과매수하락 (WR:{curr_wr:.1f})'
            })
    
    return signals

def multi_indicator_strategy(ohlcv_data, confirmation_count=2):
    """
    다중 지표 확인 전략
    - 여러 지표가 같은 방향을 가리킬 때만 신호 생성
    - RSI, CCI, Williams %R, 스토캐스틱 RSI 조합
    """
    if len(ohlcv_data) < 30:
        return []
    
    indicators = AdvancedIndicators()
    highs = [candle[2] for candle in ohlcv_data]
    lows = [candle[3] for candle in ohlcv_data]
    closes = [candle[4] for candle in ohlcv_data]
    timestamps = [candle[0] for candle in ohlcv_data]
    
    # 모든 지표 계산
    rsi_data = indicators.rsi(closes, 14)
    cci_data = indicators.cci(highs, lows, closes, 20)
    williams_r = indicators.williams_percent_r(highs, lows, closes, 14)
    stoch_rsi = indicators.stochastic_rsi(closes, 14, 14, 3, 3)
    
    signals = []
    
    for i in range(len(closes)):
        if (rsi_data[i] is None or cci_data[i] is None or 
            williams_r[i] is None or stoch_rsi['k_percent'][i] is None):
            continue
            
        current_price = closes[i]
        rsi = rsi_data[i]
        cci = cci_data[i]
        wr = williams_r[i]
        stoch_k = stoch_rsi['k_percent'][i]
        
        # 매수 신호 카운트
        bullish_signals = 0
        bearish_signals = 0
        
        # RSI 확인
        if rsi < 30:
            bullish_signals += 1
        elif rsi > 70:
            bearish_signals += 1
            
        # CCI 확인
        if cci < -100:
            bullish_signals += 1
        elif cci > 100:
            bearish_signals += 1
            
        # Williams %R 확인
        if wr < -80:
            bullish_signals += 1
        elif wr > -20:
            bearish_signals += 1
            
        # 스토캐스틱 RSI 확인
        if stoch_k < 20:
            bullish_signals += 1
        elif stoch_k > 80:
            bearish_signals += 1
        
        # 충분한 확신 신호가 있을 때만 거래
        if bullish_signals >= confirmation_count:
            signals.append({
                'timestamp': timestamps[i],
                'signal': 'buy',
                'price': current_price,
                'reason': f'다중지표매수확인 ({bullish_signals}개지표) RSI:{rsi:.1f} CCI:{cci:.1f} WR:{wr:.1f} StochK:{stoch_k:.1f}'
            })
        elif bearish_signals >= confirmation_count:
            signals.append({
                'timestamp': timestamps[i],
                'signal': 'sell',
                'price': current_price,
                'reason': f'다중지표매도확인 ({bearish_signals}개지표) RSI:{rsi:.1f} CCI:{cci:.1f} WR:{wr:.1f} StochK:{stoch_k:.1f}'
            })
    
    return signals

def backtest_advanced_strategy(ohlcv_data, strategy_func, initial_capital=10000.0, 
                             commission=0.001, **strategy_params):
    """
    고급 전략용 백테스팅 함수
    
    Args:
        ohlcv_data: OHLCV 데이터
        strategy_func: 전략 함수 (bollinger_bands_strategy, macd_stochastic_strategy 등)
        initial_capital: 초기 자본
        commission: 수수료율  
        **strategy_params: 전략별 파라미터
        
    Returns:
        Dict: 백테스팅 결과
    """
    signals = strategy_func(ohlcv_data, **strategy_params)
    
    if not signals:
        return {
            "initial_capital": float(initial_capital),
            "final_capital": float(initial_capital),
            "profit_loss": 0.0,
            "trades": [],
            "signals": []
        }
    
    capital = initial_capital
    position = 0  # 0: no position, 1: long position
    buy_price = 0
    buy_amount = 0
    trades = []
    
    for signal in signals:
        current_price = signal['price']
        
        if signal['signal'] == 'buy' and position == 0:
            # 매수
            buy_amount = (capital * 0.95) / current_price  # 95% 투자
            capital -= buy_amount * current_price * (1 + commission)
            position = 1
            buy_price = current_price
            trades.append({
                'type': 'buy',
                'price': current_price,
                'amount': buy_amount,
                'capital': capital,
                'timestamp': signal['timestamp'],
                'reason': signal['reason']
            })
            
        elif signal['signal'] == 'sell' and position == 1:
            # 매도
            capital += buy_amount * current_price * (1 - commission)
            position = 0
            profit = (current_price - buy_price) / buy_price * 100
            trades.append({
                'type': 'sell',
                'price': current_price,
                'amount': buy_amount,
                'capital': capital,
                'timestamp': signal['timestamp'],
                'reason': signal['reason'],
                'profit_percent': profit
            })
    
    # 마지막에 포지션이 열려있으면 청산
    if position == 1 and ohlcv_data:
        final_price = ohlcv_data[-1][4]  # 마지막 종가
        capital += buy_amount * final_price * (1 - commission)
        profit = (final_price - buy_price) / buy_price * 100
        trades.append({
            'type': 'close',
            'price': final_price,
            'amount': buy_amount,
            'capital': capital,
            'timestamp': ohlcv_data[-1][0],
            'reason': 'Position close at end',
            'profit_percent': profit
        })
    
    final_capital = float(capital)
    profit_loss = float(final_capital - initial_capital)
    return_rate = (profit_loss / initial_capital) * 100
    
    # 거래 통계 계산
    winning_trades = [t for t in trades if t.get('profit_percent', 0) > 0]
    losing_trades = [t for t in trades if t.get('profit_percent', 0) < 0]
    win_rate = (len(winning_trades) / len([t for t in trades if 'profit_percent' in t])) * 100 if trades else 0
    
    return {
        "initial_capital": float(initial_capital),
        "final_capital": final_capital,
        "profit_loss": profit_loss,
        "return_rate": return_rate,
        "total_trades": len(trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": win_rate,
        "trades": trades,
        "signals": signals
    }