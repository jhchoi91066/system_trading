#!/usr/bin/env python3
"""
새로운 테스트 포지션 생성 및 레버리지 고려한 TP/SL 설정 테스트
"""

import asyncio
from bingx_vst_client import BingXVSTClient

async def create_test_position():
    api_key = 'dTwrrGyzx3jzFKSWIyufzjdUso9LwdRO1r1jbgHG2yRTfGS2GWDKxUNBVuyOvn5kSJMfcjSRMdQfqamZOSFA'
    secret_key = 'LITVDtJ8WdQgKpRFlDqAUrW2asU5buvdBrDUkNYro4JlUS5VFgDHEweTK1C4MFomquGRxa1pwXxWTXhQNeg'
    
    print('🚀 새 테스트 포지션 생성 및 TP/SL 설정')
    client = BingXVSTClient(api_key, secret_key)
    
    # 1. 작은 BTC 포지션 생성
    test_symbol = 'BTC-USDT'
    test_quantity = 0.001
    
    print(f'테스트 포지션: {test_symbol} {test_quantity} BTC')
    
    # 2. 마켓 매수 주문
    print('\n=== 1단계: 매수 주문 실행 ===')
    try:
        buy_result = client.create_vst_market_buy_order(test_symbol, test_quantity)
        
        if buy_result and buy_result.get('code') == 0:
            print('✅ 포지션 생성 성공!')
            order_data = buy_result.get('data', {}).get('order', {})
            print(f'주문 ID: {order_data.get("orderId", "N/A")}')
            
            # 포지션 생성 대기
            print('포지션 생성 대기 중...')
            await asyncio.sleep(3)
            
            # 3. 포지션 확인
            print('\n=== 2단계: 포지션 확인 ===')
            positions = client.get_vst_positions()
            
            btc_position = None
            for pos in positions:
                if pos.get('symbol') == test_symbol:
                    position_amt = float(pos.get('positionAmt', '0'))
                    if position_amt > 0:
                        btc_position = pos
                        break
            
            if btc_position:
                symbol = btc_position.get('symbol')
                position_amt = float(btc_position.get('positionAmt', '0'))
                avg_price = float(btc_position.get('avgPrice', '0'))
                leverage = btc_position.get('leverage', 1)
                
                print('✅ 포지션 확인됨:')
                print(f'  심볼: {symbol}')
                print(f'  수량: {position_amt}')
                print(f'  진입가: ${avg_price:.2f}')
                print(f'  레버리지: {leverage}배')
                
                # 4. 레버리지 고려한 TP/SL 계산
                print('\n=== 3단계: 레버리지 고려한 TP/SL 계산 ===')
                sl_change = -5.0 / leverage  # 실제 -5% 손익
                tp_change = 10.0 / leverage  # 실제 +10% 손익
                
                sl_price = avg_price * (1 + sl_change / 100)
                tp_price = avg_price * (1 + tp_change / 100)
                
                print(f'레버리지 {leverage}배 고려한 계산:')
                print(f'  손절: {sl_change:.3f}% 가격변동 → -5% 실제손익')
                print(f'  익절: {tp_change:.3f}% 가격변동 → +10% 실제손익')
                print(f'  손절가: ${sl_price:.6f}')
                print(f'  익절가: ${tp_price:.6f}')
                
                # 5. TP/SL 주문 생성
                print('\n=== 4단계: TP/SL 주문 생성 ===')
                
                # 손절 주문
                print('🛡️ 손절 주문 생성 중...')
                try:
                    sl_result = client.create_vst_stop_loss_order(
                        test_symbol, position_amt, sl_price, 'LONG'
                    )
                    if sl_result and sl_result.get('code') == 0:
                        print('✅ 손절 주문 생성 성공')
                        sl_order_data = sl_result.get('data', {}).get('order', {})
                        print(f'   주문 ID: {sl_order_data.get("orderId", "N/A")}')
                    else:
                        print(f'❌ 손절 주문 실패: {sl_result.get("msg", "Unknown error")}')
                        print(f'   전체 응답: {sl_result}')
                except Exception as e:
                    print(f'❌ 손절 주문 예외: {e}')
                
                await asyncio.sleep(0.5)
                
                # 익절 주문 (50% 수량)
                print('📈 익절 주문 생성 중...')
                try:
                    tp_quantity = position_amt / 2
                    tp_result = client.create_vst_take_profit_order(
                        test_symbol, tp_quantity, tp_price, 'LONG'
                    )
                    if tp_result and tp_result.get('code') == 0:
                        print('✅ 익절 주문 생성 성공')
                        tp_order_data = tp_result.get('data', {}).get('order', {})
                        print(f'   주문 ID: {tp_order_data.get("orderId", "N/A")}')
                    else:
                        print(f'❌ 익절 주문 실패: {tp_result.get("msg", "Unknown error")}')
                        print(f'   전체 응답: {tp_result}')
                except Exception as e:
                    print(f'❌ 익절 주문 예외: {e}')
                    
            else:
                print('❌ 생성된 포지션을 찾을 수 없습니다')
                print('현재 포지션 목록:')
                for pos in positions:
                    symbol = pos.get('symbol')
                    amt = pos.get('positionAmt', '0')
                    print(f'  {symbol}: {amt}')
                
        else:
            print(f'❌ 포지션 생성 실패: {buy_result}')
            
    except Exception as e:
        print(f'❌ 전체 프로세스 실패: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(create_test_position())