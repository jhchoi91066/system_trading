#!/usr/bin/env python3
"""
TP/SL 시스템 테스트 스크립트
"""

import asyncio
import logging
from bingx_vst_client import create_vst_client_from_env

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_tp_sl_system():
    """TP/SL 시스템 테스트"""
    print('🧪 TP/SL 시스템 테스트 시작')
    
    try:
        # VST 클라이언트 초기화
        vst_client = create_vst_client_from_env()
        
        # 1. 작은 테스트 포지션 생성 (0.001 BTC, 10배 레버리지)
        print('\n=== 1단계: 테스트 포지션 생성 ===')
        
        # 시장가 매수 주문
        buy_order = vst_client.place_vst_order(
            symbol="BTC-USDT",
            side="BUY", 
            order_type="MARKET",
            quantity=0.001,
            position_side="LONG"
        )
        print(f'매수 주문 결과: {buy_order}')
        
        if buy_order.get('code') != 0:
            print('❌ 매수 주문 실패')
            return
            
        # 주문 정보 추출
        order_data = buy_order.get('data', {}).get('order', {})
        entry_price = float(order_data.get('avgPrice', 0))
        quantity = float(order_data.get('executedQty', 0))
        
        if entry_price == 0 or quantity == 0:
            print('❌ 주문 정보 추출 실패')
            return
            
        print(f'✅ 포지션 생성 완료: 진입가 ${entry_price}, 수량 {quantity} BTC')
        
        # 2. 레버리지 정보 확인
        print('\n=== 2단계: 레버리지 정보 확인 ===')
        positions = vst_client.get_vst_positions()
        leverage = 1
        
        for pos in positions:
            if pos.get('symbol') == 'BTC-USDT' and float(pos.get('positionAmt', 0)) != 0:
                leverage = pos.get('leverage', 1)
                print(f'현재 BTC 포지션 레버리지: {leverage}배')
                break
        
        # 3. TP/SL 가격 계산 (레버리지 고려)
        print('\n=== 3단계: TP/SL 가격 계산 ===')
        
        # 레버리지 고려한 실제 가격 변동률 계산
        sl_price_change = -5.0 / leverage   # 실제 -5% 손실
        tp1_price_change = 10.0 / leverage  # 실제 +10% 수익
        tp2_price_change = 15.0 / leverage  # 실제 +15% 수익
        
        sl_price = entry_price * (1 + sl_price_change / 100)
        tp1_price = entry_price * (1 + tp1_price_change / 100)  
        tp2_price = entry_price * (1 + tp2_price_change / 100)
        
        tp1_quantity = quantity * 0.5  # 50% 부분 청산
        tp2_quantity = quantity * 0.5  # 나머지 50%
        
        print(f'진입가: ${entry_price:.2f}')
        print(f'손절가: ${sl_price:.2f} (가격변동: {sl_price_change:.3f}%, 실제손익: -5%)')
        print(f'1차 익절: ${tp1_price:.2f} (가격변동: {tp1_price_change:.3f}%, 실제손익: +10%)')
        print(f'2차 익절: ${tp2_price:.2f} (가격변동: {tp2_price_change:.3f}%, 실제손익: +15%)')
        
        # 4. 실제 TP/SL 주문 생성
        print('\n=== 4단계: TP/SL 주문 생성 ===')
        
        # 손절 주문
        print('손절 주문 생성 중...')
        sl_order = vst_client.create_vst_stop_loss_order(
            "BTC-USDT", quantity, sl_price, "LONG"
        )
        print(f'📤 손절 주문 결과: {sl_order}')
        
        # 1차 익절 주문
        print('1차 익절 주문 생성 중...')
        tp1_order = vst_client.create_vst_take_profit_order(
            "BTC-USDT", tp1_quantity, tp1_price, "LONG"
        )
        print(f'📤 1차 익절 주문 결과: {tp1_order}')
        
        # 2차 익절 주문
        print('2차 익절 주문 생성 중...')  
        tp2_order = vst_client.create_vst_take_profit_order(
            "BTC-USDT", tp2_quantity, tp2_price, "LONG"
        )
        print(f'📤 2차 익절 주문 결과: {tp2_order}')
        
        # 5. 결과 확인
        print('\n=== 5단계: 결과 확인 ===')
        
        # 포지션 상태 확인
        await asyncio.sleep(2)  # 주문 처리 대기
        updated_positions = vst_client.get_vst_positions()
        
        for pos in updated_positions:
            if pos.get('symbol') == 'BTC-USDT' and float(pos.get('positionAmt', 0)) != 0:
                print(f'포지션 상태:')
                print(f'  심볼: {pos.get("symbol")}')
                print(f'  수량: {pos.get("positionAmt")}')
                print(f'  진입가: ${pos.get("avgPrice")}')
                print(f'  현재가: ${pos.get("markPrice")}')
                print(f'  손익: ${pos.get("unrealizedProfit")} ({pos.get("pnlRatio", 0):.2%})')
                break
        
        # 최근 주문 확인 
        trades = vst_client.get_vst_trade_history(limit=10)
        pending_orders = [order for order in trades if order.get('status') == 'NEW']
        
        print(f'\n활성 대기 주문: {len(pending_orders)}개')
        for order in pending_orders[-3:]:  # 최근 3개만 표시
            print(f'  - {order.get("type")} {order.get("side")}: ${order.get("stopPrice", order.get("price", 0)):.2f}')
        
        vst_client.close()
        print('\n✅ TP/SL 시스템 테스트 완료')
        
    except Exception as e:
        print(f'❌ TP/SL 시스템 테스트 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_tp_sl_system())