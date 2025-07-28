import pandas as pd
import numpy as np

def calculate_cci(high, low, close, window=20):
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(window=window).mean()
    mad_tp = tp.rolling(window=window).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    cci = (tp - sma_tp) / (0.015 * mad_tp)
    return cci

def generate_cci_signals(ohlcv_data, window=20, buy_threshold=100, sell_threshold=-100):
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['cci'] = calculate_cci(df['high'], df['low'], df['close'], window)

    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0

    # Buy signal: CCI crosses above buy_threshold
    signals.loc[df['cci'] > buy_threshold, 'signal'] = 1

    # Sell signal: CCI crosses below sell_threshold
    signals.loc[df['cci'] < sell_threshold, 'signal'] = -1

    return signals

def backtest_strategy(ohlcv_data, window=20, buy_threshold=100, sell_threshold=-100, initial_capital=10000, commission=0.001):
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['cci'] = calculate_cci(df['high'], df['low'], df['close'], window)

    signals = generate_cci_signals(ohlcv_data, window, buy_threshold, sell_threshold)
    df['signal'] = signals['signal']

    capital = initial_capital
    position = 0 # 0: no position, 1: long, -1: short
    trades = []

    for i in range(len(df)):
        current_price = df['close'].iloc[i]
        signal = df['signal'].iloc[i]

        if signal == 1 and position == 0: # Buy signal and no open position
            # Buy at current price
            buy_amount = capital / current_price
            capital -= buy_amount * current_price * commission
            position = 1
            trades.append({'type': 'buy', 'price': current_price, 'amount': buy_amount, 'capital': capital, 'timestamp': int(df['timestamp'].iloc[i])})

        elif signal == -1 and position == 1: # Sell signal and long position
            # Sell at current price
            capital += buy_amount * current_price * (1 - commission)
            position = 0
            trades.append({'type': 'sell', 'price': current_price, 'amount': buy_amount, 'capital': capital, 'timestamp': int(df['timestamp'].iloc[i])})

    # If there's an open position at the end, close it
    if position == 1:
        capital += buy_amount * current_price * (1 - commission)
        position = 0
        trades.append({'type': 'close', 'price': current_price, 'amount': buy_amount, 'capital': capital, 'timestamp': int(df['timestamp'].iloc[i])})

    final_capital = float(capital)
    profit_loss = float(final_capital - initial_capital)
    return {
        "initial_capital": float(initial_capital),
        "final_capital": final_capital,
        "profit_loss": profit_loss,
        "trades": trades
    }
