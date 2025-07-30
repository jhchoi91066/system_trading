#!/usr/bin/env python3
"""
BingX VST 주문 테스트 스크립트
- 소량의 VST 주문으로 실제 연동 검증
"""

from bingx_vst_client import create_vst_client_from_env
import time

def test_vst_order():
    """VST 주문 테스트"""
    try:
        # VST 클라이언트 생성
        vst_client = create_vst_client_from_env()
        
        print("=== BingX VST Order Test ===")
        
        # 연결 및 잔고 확인
        if not vst_client.test_vst_connection():
            print("❌ VST connection failed")
            return
        
        account_info = vst_client.get_vst_account_info()
        print(f"💰 Current VST Balance: {account_info['vst_balance']}")
        
        if account_info['vst_balance'] < 100:
            print("❌ Insufficient VST balance for test order")
            return
        
        # 소량 BTC-USDT 시장가 매수 테스트 (0.001 BTC)
        print("\n🔄 Placing small test order...")
        test_order = vst_client.create_vst_market_buy_order("BTC-USDT", 0.001)
        
        if 'error' in test_order:
            print(f"❌ Order failed: {test_order['error']}")
        elif test_order.get('code') == 0:
            print("✅ VST Order placed successfully!")
            print(f"📝 Order ID: {test_order.get('data', {}).get('orderId', 'N/A')}")
            
            # 잠시 대기 후 포지션 확인
            time.sleep(2)
            positions = vst_client.get_vst_positions("BTC-USDT")
            print(f"📊 Updated positions: {len(positions)} positions")
            
            if positions:
                for pos in positions:
                    if float(pos.get('positionAmt', 0)) != 0:
                        print(f"   Position: {pos.get('symbol')} {pos.get('positionAmt')} @ {pos.get('avgPrice')}")
        else:
            print(f"❌ Order failed with code: {test_order.get('code')}")
            print(f"   Message: {test_order.get('msg', 'Unknown error')}")
        
        # 최종 계정 상태
        final_account = vst_client.get_vst_account_info()
        print(f"\n💰 Final VST Balance: {final_account['vst_balance']}")
        print(f"📊 Open Positions: {final_account['open_positions']}")
        
        vst_client.close()
        print("\n=== VST Test Complete ===")
        
    except Exception as e:
        print(f"❌ VST Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("⚠️  This will place a REAL order on BingX VST demo account!")
    print("   Order: 0.001 BTC market buy (~$100 VST)")
    print("   Continue? (y/N): ", end="")
    
    try:
        user_input = input().strip().lower()
        if user_input == 'y':
            test_vst_order()
        else:
            print("Test cancelled.")
    except KeyboardInterrupt:
        print("\nTest cancelled.")