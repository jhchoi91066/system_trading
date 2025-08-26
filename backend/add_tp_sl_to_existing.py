#!/usr/bin/env python3
"""
기존 포지션에 TP/SL 추가 스크립트
"""

import asyncio
from bingx_vst_client import create_vst_client_from_env

async def add_tp_sl_to_existing():
    """기존 포지션에 TP/SL 추가"""
    print('🔧 기존 포지션에 TP/SL 추가 시작')
    
    try:
        vst_client = create_vst_client_from_env()
        
        # 현재 포지션 확인
        positions = vst_client.get_vst_positions()
        
        for pos in positions:
            if pos.get('symbol') == 'BTC-USDT' and float(pos.get('positionAmt', 0)) > 0:
                symbol = pos.get('symbol')
                position_amt = float(pos.get('positionAmt'))
                avg_price = float(pos.get('avgPrice'))
                leverage = pos.get('leverage', 25)
                
                print(f'🔍 포지션 발견: {symbol}')
                print(f'  수량: {position_amt} BTC')
                print(f'  진입가: ${avg_price:.2f}')
                print(f'  레버리지: {leverage}배')
                
                # TP/SL 가격 계산
                sl_price_change = -5.0 / leverage   # 실제 -5% 손실
                tp1_price_change = 10.0 / leverage  # 실제 +10% 수익
                tp2_price_change = 15.0 / leverage  # 실제 +15% 수익
                
                sl_price = avg_price * (1 + sl_price_change / 100)
                tp1_price = avg_price * (1 + tp1_price_change / 100)  
                tp2_price = avg_price * (1 + tp2_price_change / 100)
                
                tp1_quantity = position_amt * 0.5  # 50% 부분 청산
                tp2_quantity = position_amt * 0.5  # 나머지 50%
                
                print(f'📊 TP/SL 가격:')
                print(f'  손절가: ${sl_price:.2f} (실제 -5% 손실)')
                print(f'  1차 익절: ${tp1_price:.2f} (실제 +10% 수익)')
                print(f'  2차 익절: ${tp2_price:.2f} (실제 +15% 수익)')
                
                # TP/SL 주문 생성
                print('\n📤 TP/SL 주문 생성 중...')
                
                try:
                    # 손절 주문
                    sl_order = vst_client.create_vst_stop_loss_order(
                        symbol, position_amt, sl_price, "LONG"
                    )
                    print(f'✅ 손절 주문: {sl_order.get("code") == 0}')
                    
                    # 1차 익절 주문
                    tp1_order = vst_client.create_vst_take_profit_order(
                        symbol, tp1_quantity, tp1_price, "LONG"
                    )
                    print(f'✅ 1차 익절 주문: {tp1_order.get("code") == 0}')
                    
                    # 2차 익절 주문  
                    tp2_order = vst_client.create_vst_take_profit_order(
                        symbol, tp2_quantity, tp2_price, "LONG"
                    )
                    print(f'✅ 2차 익절 주문: {tp2_order.get("code") == 0}')
                    
                    print('\n✅ 모든 TP/SL 주문이 설정되었습니다!')
                    
                except Exception as e:
                    print(f'❌ TP/SL 주문 생성 실패: {e}')
                
                break
        
        vst_client.close()
        
    except Exception as e:
        print(f'❌ 오류 발생: {e}')

if __name__ == '__main__':
    asyncio.run(add_tp_sl_to_existing())