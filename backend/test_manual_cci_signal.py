#!/usr/bin/env python3
"""
CCI 신호 수동 테스트 및 자동 주문 확인
"""

import asyncio
import logging
from realtime_trading_engine import RealtimeTradingEngine
from strategy import generate_cci_signals, calculate_cci
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_manual_cci_execution():
    print('🧪 CCI 신호 수동 테스트 및 자동 주문 확인')
    
    try:
        # 거래 엔진 초기화
        engine = RealtimeTradingEngine()
        api_key = 'dTwrrGyzx3jzFKSWIyufzjdUso9LwdRO1r1jbgHG2yRTfGS2GWDKxUNBVuyOvn5kSJMfcjSRMdQfqamZOSFA'
        secret_key = 'LITVDtJ8WdQgKpRFlDqAUrW2asU5buvdBrDUkNYro4JlUS5VFgDHEweTK1C4MFomquGRxa1pwXxWTXhQNeg'
        
        success = await engine.initialize_exchange('bingx', api_key, secret_key, demo_mode=True)
        if not success:
            print('❌ 거래소 초기화 실패')
            return
            
        print('✅ BingX VST 거래소 초기화 완료')
        
        # 1. 실제 시장 데이터 가져오기
        print('\n=== 1단계: 실제 시장 데이터 수집 ===')
        ohlcv = await engine.get_recent_candles('bingx', 'BTC/USDT', '5m', 200)
        
        if not ohlcv or len(ohlcv) < 50:
            print('❌ 시장 데이터 수집 실패')
            return
            
        print(f'✅ 시장 데이터 수집: {len(ohlcv)}개 캔들')
        
        # DataFrame 변환
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        latest_price = df['close'].iloc[-1]
        print(f'  최신 BTC 가격: ${latest_price:.2f}')
        
        # 2. CCI 계산 및 신호 확인
        print('\n=== 2단계: CCI 신호 분석 ===')
        df['cci'] = calculate_cci(df['high'], df['low'], df['close'], 14)
        
        # 최근 20개 캔들의 CCI 값과 신호 확인
        print('최근 20개 캔들의 CCI 값:')
        recent_data = df[['timestamp', 'close', 'cci']].tail(20)
        
        # CCI 신호 생성
        ohlcv_for_signals = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].values
        signals = generate_cci_signals(ohlcv_for_signals, window=14, buy_threshold=-100, sell_threshold=100)
        
        # 최근 신호 확인
        recent_signals = signals.tail(20)
        signal_indices = recent_signals[recent_signals['signal'] != 0].index
        
        print(f'  현재 CCI: {df["cci"].iloc[-1]:.2f}')
        print(f'  최근 20개 캔들 중 신호: {len(signal_indices)}개')
        
        if len(signal_indices) > 0:
            for idx in signal_indices:
                signal_type = '매수' if recent_signals.loc[idx, 'signal'] == 1 else '매도'
                timestamp = df.loc[idx, 'timestamp']
                price = df.loc[idx, 'close']
                cci_value = df.loc[idx, 'cci']
                print(f'  📊 {signal_type} 신호 - {timestamp}: ${price:.2f} (CCI: {cci_value:.2f})')
        else:
            print('  ⚫ 최근 신호 없음')
        
        # 3. 수동으로 신호 실행 테스트
        print('\n=== 3단계: 수동 신호 실행 테스트 ===')
        
        # CCI 전략 설정
        strategy_config = {
            'strategy_id': 'manual_test_cci',
            'strategy_type': 'CCI',
            'parameters': {
                'window': 14,
                'buy_threshold': -100,
                'sell_threshold': 100
            },
            'allocated_capital': 100.0,
            'stop_loss_percentage': 5.0,
            'take_profit_percentage': 10.0,
            'risk_per_trade': 2.0,
            'is_active': True
        }
        
        # 가장 최근 신호가 있다면 실행
        if len(signal_indices) > 0:
            latest_signal_idx = signal_indices[-1]
            signal_value = recent_signals.loc[latest_signal_idx, 'signal']
            signal_price = df.loc[latest_signal_idx, 'close']
            
            signal_type = '매수' if signal_value == 1 else '매도'
            print(f'🎯 최근 {signal_type} 신호를 수동 실행')
            print(f'  신호 가격: ${signal_price:.2f}')
            print(f'  현재 가격: ${latest_price:.2f}')
            
            try:
                # execute_signal 메소드 호출
                if hasattr(engine, 'execute_signal'):
                    await engine.execute_signal(
                        user_id='manual_test',
                        exchange_name='bingx',
                        symbol='BTC/USDT',
                        signal_type='buy' if signal_value == 1 else 'sell',
                        current_price=latest_price,
                        strategy=strategy_config
                    )
                    print('✅ 신호 실행 명령 완료')
                else:
                    print('❌ execute_signal 메소드를 찾을 수 없음')
                    
            except Exception as e:
                print(f'❌ 신호 실행 실패: {e}')
        else:
            print('⚠️ 실행할 최근 신호가 없음')
        
        # 4. 현재 포지션 확인
        print('\n=== 4단계: 포지션 상태 확인 ===')
        try:
            positions = engine.exchanges['bingx'].client.get_vst_positions()
            active_positions = [pos for pos in positions if float(pos.get('positionAmt', '0')) != 0]
            
            if active_positions:
                print(f'✅ 활성 포지션: {len(active_positions)}개')
                for pos in active_positions:
                    symbol = pos.get('symbol')
                    amt = float(pos.get('positionAmt', '0'))
                    avg_price = float(pos.get('avgPrice', '0'))
                    pnl = float(pos.get('unrealizedPnl', '0'))
                    print(f'  📍 {symbol}: {amt} @ ${avg_price:.2f} (PnL: ${pnl:.2f})')
            else:
                print('⚫ 활성 포지션 없음')
                
        except Exception as e:
            print(f'❌ 포지션 확인 실패: {e}')
            
    except Exception as e:
        print(f'❌ 전체 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_manual_cci_execution())