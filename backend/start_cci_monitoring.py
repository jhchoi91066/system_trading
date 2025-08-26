#!/usr/bin/env python3
"""
CCI 모니터링 시스템 직접 시작 스크립트
"""

import asyncio
import logging
from realtime_trading_engine import RealtimeTradingEngine
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def start_cci_monitoring():
    print('🚀 CCI 실시간 모니터링 시스템 시작')
    
    try:
        # 거래 엔진 초기화
        engine = RealtimeTradingEngine()
        
        # BingX API 키
        api_key = 'dTwrrGyzx3jzFKSWIyufzjdUso9LwdRO1r1jbgHG2yRTfGS2GWDKxUNBVuyOvn5kSJMfcjSRMdQfqamZOSFA'
        secret_key = 'LITVDtJ8WdQgKpRFlDqAUrW2asU5buvdBrDUkNYro4JlUS5VFgDHEweTK1C4MFomquGRxa1pwXxWTXhQNeg'
        
        # 거래소 초기화
        success = await engine.initialize_exchange('bingx', api_key, secret_key, demo_mode=True)
        if not success:
            print('❌ 거래소 초기화 실패')
            return
            
        print('✅ BingX VST 거래소 초기화 완료')
        
        # CCI 전략 설정
        cci_strategy = {
            'strategy_id': 'cci_crossover_1',
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
        
        # ETH CCI 전략 설정
        eth_cci_strategy = {
            'strategy_id': 'cci_crossover_eth',
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
        
        # 엔진 시작 (중요!)
        await engine.start_engine()
        print('✅ 거래 엔진 시작 완료')
        
        # BTC/USDT 실시간 모니터링 시작
        print('🔄 BTC/USDT CCI 모니터링 시작...')
        await engine.start_monitoring_symbol(
            user_id='test_user',
            exchange_name='bingx',
            symbol='BTC/USDT',
            timeframe='5m',
            strategies=[cci_strategy]
        )
        
        # ETH/USDT 실시간 모니터링 시작
        print('🔄 ETH/USDT CCI 모니터링 시작...')
        await engine.start_monitoring_symbol(
            user_id='test_user',
            exchange_name='bingx',
            symbol='ETH/USDT',
            timeframe='5m',
            strategies=[eth_cci_strategy]
        )
        
        print('✅ CCI 모니터링이 시작되었습니다!')
        print('📊 현재 모니터링 중:')
        print(f'  - 심볼: BTC/USDT, ETH/USDT')
        print(f'  - 타임프레임: 5분')
        print(f'  - 전략: CCI 크로스오버')
        print(f'  - 매수 신호: CCI가 -100 아래서 -100 위로 상향 돌파')
        print(f'  - 매도 신호: CCI가 +100 위에서 +100 아래로 하향 돌파')
        
        # 엔진 상태 확인
        print(f'\n📈 엔진 상태:')
        print(f'  - 실행 중: {engine.running}')
        print(f'  - 활성 모니터: {len(engine.active_monitors)}개')
        
        for monitor_key in engine.active_monitors.keys():
            print(f'    → {monitor_key}')
        
        # 실시간 모니터링 유지 (무한 루프)
        print('\n🔄 실시간 모니터링을 시작합니다... (Ctrl+C로 중단)')
        try:
            while True:
                await asyncio.sleep(10)  # 10초마다 체크
                
                # 상태 정보 출력 (1분마다)
                if hasattr(start_cci_monitoring, 'counter'):
                    start_cci_monitoring.counter += 1
                else:
                    start_cci_monitoring.counter = 1
                
                if start_cci_monitoring.counter % 6 == 0:  # 60초마다
                    print(f'💓 모니터링 활성 상태 - 활성 모니터: {len(engine.active_monitors)}개')
        
        except KeyboardInterrupt:
            print('\n🛑 사용자에 의해 중단됨')
            
    except Exception as e:
        print(f'❌ CCI 모니터링 시작 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(start_cci_monitoring())