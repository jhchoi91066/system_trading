#!/usr/bin/env python3
"""
실시간 CCI 모니터링 시스템 테스트
"""

import asyncio
import logging
from datetime import datetime, timedelta
from strategy import generate_cci_signals
from realtime_trading_engine import RealtimeTradingEngine
from bingx_vst_client import BingXVSTClient
import pandas as pd

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_cci_monitoring():
    print('🔍 실시간 CCI 모니터링 시스템 상태 확인')
    
    # 1. CCI 신호 생성 함수 테스트
    print('\n=== 1단계: CCI 신호 생성 테스트 ===')
    
    try:
        # 샘플 OHLCV 데이터 생성
        dates = pd.date_range(start='2024-01-01', periods=100, freq='5T')
        base_price = 50000
        
        price_data = []
        for i in range(100):
            # 변동이 있는 가격 패턴 생성
            if i < 30:
                price = base_price - (i * 100)  # 하락
            elif i < 70:
                price = base_price - (30 * 100) + ((i - 30) * 200)  # 반등
            else:
                price = base_price + ((i - 70) * 50)  # 상승
            
            high = price * 1.01
            low = price * 0.99
            close = price
            open_price = price
            volume = 1000
            
            price_data.append([open_price, high, low, close, volume])
        
        df = pd.DataFrame(price_data, columns=['open', 'high', 'low', 'close', 'volume'])
        df.index = dates
        
        print(f'테스트 데이터: {len(df)}개 캔들')
        print(f'가격 범위: ${df["close"].min():.0f} - ${df["close"].max():.0f}')
        
        # CCI 신호 생성 테스트 (DataFrame이 아닌 numpy 배열로 변환)
        df_reset = df.reset_index()
        df_reset.columns = ['timestamp'] + list(df.columns)
        df_reset['timestamp'] = df_reset['timestamp'].astype('int64') // 10**6  # 밀리초로 변환
        ohlcv_array = df_reset[['timestamp', 'open', 'high', 'low', 'close', 'volume']].values
        
        signals_df = generate_cci_signals(
            ohlcv_array, 
            window=14, 
            buy_threshold=-100, 
            sell_threshold=100
        )
        
        buy_signals = (signals_df['signal'] == 1).sum()
        sell_signals = (signals_df['signal'] == -1).sum()
        
        print(f'✅ CCI 신호 생성 성공!')
        print(f'  매수 신호: {buy_signals}개')
        print(f'  매도 신호: {sell_signals}개')
        
        if buy_signals > 0 or sell_signals > 0:
            print('✅ CCI 신호 생성 기능 정상 작동')
        else:
            print('⚠️ 신호가 생성되지 않음')
            
    except Exception as e:
        print(f'❌ CCI 신호 생성 실패: {e}')
        return
    
    # 2. 실시간 거래 엔진 상태 확인
    print('\n=== 2단계: 실시간 거래 엔진 확인 ===')
    
    try:
        engine = RealtimeTradingEngine()
        print('✅ 거래 엔진 인스턴스 생성 성공')
        
        # BingX VST 클라이언트 초기화 테스트
        api_key = 'dTwrrGyzx3jzFKSWIyufzjdUso9LwdRO1r1jbgHG2yRTfGS2GWDKxUNBVuyOvn5kSJMfcjSRMdQfqamZOSFA'
        secret_key = 'LITVDtJ8WdQgKpRFlDqAUrW2asU5buvdBrDUkNYro4JlUS5VFgDHEweTK1C4MFomquGRxa1pwXxWTXhQNeg'
        
        success = await engine.initialize_exchange('bingx', api_key, secret_key, demo_mode=True)
        if success:
            print('✅ BingX VST 거래소 초기화 성공')
        else:
            print('❌ BingX VST 거래소 초기화 실패')
            
    except Exception as e:
        print(f'❌ 거래 엔진 초기화 실패: {e}')
        return
    
    # 3. 실시간 모니터링 상태 확인
    print('\n=== 3단계: 모니터링 상태 확인 ===')
    
    try:
        # 현재 활성 모니터링 확인
        active_monitors = engine.active_monitors
        print(f'활성 모니터: {len(active_monitors)}개')
        
        if active_monitors:
            for monitor_key in active_monitors.keys():
                print(f'  - {monitor_key}')
        else:
            print('⚠️ 활성 모니터가 없습니다')
            
        # 현재 실행 상태 확인
        print(f'엔진 실행 상태: {engine.running}')
        
    except Exception as e:
        print(f'모니터링 상태 확인 오류: {e}')
    
    # 4. 실제 시장 데이터로 CCI 신호 확인
    print('\n=== 4단계: 실제 시장 데이터 CCI 신호 확인 ===')
    
    try:
        # BTC/USDT 최근 데이터 가져오기
        ohlcv = await engine.get_recent_candles('bingx', 'BTC/USDT', '5m', 100)
        
        if ohlcv and len(ohlcv) > 0:
            print(f'✅ 실제 시장 데이터 수집: {len(ohlcv)}개 캔들')
            
            # DataFrame으로 변환
            df_real = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_real['timestamp'] = pd.to_datetime(df_real['timestamp'], unit='ms')
            df_real.set_index('timestamp', inplace=True)
            
            # 최근 가격 정보
            latest_price = df_real['close'].iloc[-1]
            price_change = ((latest_price - df_real['close'].iloc[-2]) / df_real['close'].iloc[-2]) * 100
            
            print(f'  최신 BTC 가격: ${latest_price:.2f}')
            print(f'  전 캔들 대비: {price_change:+.2f}%')
            
            # 실제 데이터로 CCI 신호 생성
            # DataFrame을 numpy array로 변환 (timestamp 컬럼 추가)
            df_for_signals = df_real.reset_index()
            df_for_signals['timestamp'] = df_for_signals['timestamp'].astype('int64') // 10**6  # 밀리초로 변환
            ohlcv_array = df_for_signals[['timestamp', 'open', 'high', 'low', 'close', 'volume']].values
            
            real_signals = generate_cci_signals(
                ohlcv_array, 
                window=14, 
                buy_threshold=-100, 
                sell_threshold=100
            )
            
            # CCI 값을 별도로 계산
            from strategy import calculate_cci
            df_real['cci'] = calculate_cci(df_real['high'], df_real['low'], df_real['close'], 14)
            
            # 최신 CCI 값과 신호
            latest_cci = df_real['cci'].iloc[-1]
            latest_signal = real_signals['signal'].iloc[-1]
            
            print(f'  현재 CCI 값: {latest_cci:.2f}')
            
            if latest_signal == 1:
                print('  🟢 매수 신호 발생!')
            elif latest_signal == -1:
                print('  🔴 매도 신호 발생!')
            else:
                print('  ⚫ 신호 없음')
                
            # 최근 10개 캔들의 신호 확인
            recent_signals = real_signals['signal'].tail(10)
            signal_count = (recent_signals != 0).sum()
            print(f'  최근 10개 캔들 중 신호: {signal_count}개')
            
        else:
            print('❌ 실제 시장 데이터 수집 실패')
            
    except Exception as e:
        print(f'❌ 실제 데이터 CCI 확인 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_cci_monitoring())