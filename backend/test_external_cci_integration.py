#!/usr/bin/env python3
"""
외부 CCI 통합 테스트 스크립트
"""

import asyncio
import logging
from datetime import datetime
from realtime_trading_engine import RealtimeTradingEngine
from external_cci_client import HybridCCIClient

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_external_cci_integration():
    """외부 CCI와 거래 엔진 통합 테스트"""
    print("🧪 외부 CCI 통합 테스트 시작")
    
    try:
        # 실시간 거래 엔진 초기화
        engine = RealtimeTradingEngine()
        
        # BingX 거래소 초기화 (데모 모드)
        success = await engine.initialize_exchange(
            'bingx', 
            'dummy_api_key',  # 테스트용 더미 키
            'dummy_secret',   # 테스트용 더미 시크릿  
            demo_mode=True
        )
        
        if not success:
            print("❌ 거래소 초기화 실패")
            return
        
        print("✅ 거래소 초기화 완료")
        
        # 최근 캔들 데이터 가져오기
        print("📊 BTC/USDT 캔들 데이터 가져오는 중...")
        candles = await engine.get_recent_candles('bingx', 'BTC/USDT', '5m', 50)
        
        if not candles or len(candles) == 0:
            print("❌ 캔들 데이터 가져오기 실패")
            return
            
        print(f"✅ 캔들 데이터 {len(candles)}개 가져오기 완료")
        
        # 외부 CCI 클라이언트 테스트
        print("🔍 외부 CCI 값 계산 중...")
        cci_client = HybridCCIClient()
        
        cci_value = await cci_client.get_cci_value(
            symbol="BTC/USDT",
            ohlcv_data=candles,
            exchange="binance",  # TAAPI.IO에서 지원
            interval="5m",
            period=20
        )
        
        if cci_value is not None:
            print(f"✅ CCI 값: {cci_value:.2f}")
            
            # CCI 신호 해석
            if cci_value < -100:
                print(f"📈 과매도 신호! (CCI: {cci_value:.2f}) - 매수 타점")
            elif cci_value > 100:
                print(f"📉 과매수 신호! (CCI: {cci_value:.2f}) - 매도 타점")
            else:
                print(f"⚖️ 중립 범위 (CCI: {cci_value:.2f})")
        else:
            print("❌ CCI 값 가져오기 실패")
            
        # 외부 CCI를 이용한 신호 생성 테스트
        print("🎯 외부 CCI 신호 생성 테스트...")
        signals = await engine._cci_strategy_wrapper_external(
            candles, 
            "BTC/USDT",
            window=20,
            buy_threshold=-100,
            sell_threshold=100
        )
        
        print(f"🔍 생성된 신호 개수: {len(signals)}")
        
        if signals:
            for signal in signals:
                print(f"📢 신호: {signal['signal']} @ ${signal['price']:.2f} - {signal['reason']}")
        else:
            print("📭 현재 활성화된 거래 신호가 없습니다")
        
        # 엔진 종료
        await engine.stop_engine()
        print("✅ 외부 CCI 통합 테스트 완료")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_external_cci_integration())