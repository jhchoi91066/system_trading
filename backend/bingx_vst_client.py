"""
BingX VST (Virtual Simulated Trading) 클라이언트
- 실제 BingX VST 계정을 사용한 데모 트레이딩
- open-api-vst.bingx.com 도메인 사용
- 200,000 VST 가상 자금으로 실제 포지션 생성
"""

import hmac
import hashlib
import time
import requests
import json
import asyncio
import aiohttp
import logging
import uuid
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BingXVSTClient:
    """BingX VST (Virtual Simulated Trading) API 클라이언트"""
    
    def __init__(self, api_key: str, secret_key: str):
        """
        BingX VST API 클라이언트 초기화
        
        Args:
            api_key: BingX API 키
            secret_key: BingX Secret 키
        """
        self.api_key = api_key
        self.secret_key = secret_key
        
        # BingX VST API URLs
        self.base_url = "https://open-api-vst.bingx.com"  # VST 전용 도메인
        self.websocket_url = "wss://open-api-ws.bingx.com/market"
        
        # API 요청 제한
        self.rate_limit_delay = 0.1  # 100ms 지연
        
        # 세션 생성
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'BingX-VST-Python-Client'
        })
        
        logger.info("BingX VST Client initialized")
    
    def _generate_signature(self, query_string: str) -> str:
        """
        HMAC SHA256 서명 생성 (BingX 방식)
        
        Args:
            query_string: 완전한 쿼리 문자열 (timestamp 포함)
            
        Returns:
            서명 문자열
        """
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_timestamp(self) -> str:
        """현재 타임스탬프 반환 (밀리초)"""
        return str(int(time.time() * 1000))
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, signed: bool = True) -> Dict:
        """
        API 요청 실행
        
        Args:
            method: HTTP 메서드 (GET, POST, DELETE)
            endpoint: API 엔드포인트
            params: 요청 파라미터
            signed: 서명 필요 여부
            
        Returns:
            API 응답 데이터
        """
        if params is None:
            params = {}
        
        url = f"{self.base_url}{endpoint}"
        
        # 서명이 필요한 경우
        if signed:
            timestamp = self._get_timestamp()
            params['timestamp'] = timestamp
            
            # 쿼리 문자열 생성 (알파벳 순 정렬)
            query_string = urlencode(sorted(params.items()))
            
            # 서명 생성 (전체 쿼리 문자열 사용)
            signature = self._generate_signature(query_string)
            params['signature'] = signature
            
            # 헤더에 API 키 추가
            headers = {
                'X-BX-APIKEY': self.api_key
            }
        else:
            headers = {}
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, headers=headers)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=params, headers=headers)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, params=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Rate limiting
            time.sleep(self.rate_limit_delay)
            
            response.raise_for_status()
            result = response.json()
            
            # VST API 응답 로깅
            logger.info(f"VST API {method} {endpoint}: {result.get('code', 'N/A')}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"BingX VST API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in BingX VST API request: {e}")
            raise e
    
    # ============= VST 계정 관리 API =============
    
    def get_vst_balance(self) -> Dict:
        """VST 계정 잔고 조회"""
        try:
            result = self._make_request("GET", "/openApi/swap/v2/user/balance")
            logger.info(f"VST Balance retrieved: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to get VST balance: {e}")
            return {}
    
    def get_vst_positions(self, symbol: str = None) -> List[Dict]:
        """VST 포지션 조회"""
        try:
            params = {}
            if symbol:
                params['symbol'] = symbol
            
            result = self._make_request("GET", "/openApi/swap/v2/user/positions", params)
            positions = result.get('data', [])
            logger.info(f"VST Positions retrieved: {len(positions)} positions")
            return positions
        except Exception as e:
            logger.error(f"Failed to get VST positions: {e}")
            return []
    
    def get_vst_trade_history(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """VST 거래 기록 조회"""
        try:
            params = {'limit': limit}
            if symbol:
                params['symbol'] = symbol
            
            result = self._make_request("GET", "/openApi/swap/v2/trade/allOrders", params)
            trades = result.get('data', [])
            logger.info(f"VST Trade history retrieved: {len(trades)} trades")
            return trades
        except Exception as e:
            logger.error(f"Failed to get VST trade history: {e}")
            return []
    
    # ============= VST 거래 실행 API =============
    
    def place_vst_order(self, symbol: str, side: str, order_type: str, quantity: float, 
                       price: float = None, position_side: str = "LONG", 
                       time_in_force: str = "GTC", stop_price: float = None) -> Dict:
        """
        VST 주문 생성 (실제 BingX VST 계정에 주문)
        
        Args:
            symbol: 거래 심볼 (예: BTC-USDT)
            side: 거래 방향 ("BUY" or "SELL")
            order_type: 주문 타입 ("MARKET", "LIMIT", "STOP", "STOP_MARKET")
            quantity: 주문 수량
            price: 주문 가격 (LIMIT 주문 시 필수)
            position_side: 포지션 방향 ("LONG" or "SHORT")
            time_in_force: 주문 유효 시간 ("GTC", "IOC", "FOK")
            stop_price: 스톱 가격 (STOP 주문 시 필수)
            
        Returns:
            주문 결과
        """
        try:
            # 고유한 클라이언트 주문 ID 생성 (GitHub 이슈에서 권장)
            client_order_id = str(uuid.uuid4())
            
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': order_type.upper(),
                'quantity': str(quantity),
                'positionSide': position_side.upper(),
                'timeInForce': time_in_force,
                'clientOrderID': client_order_id  # 필수 파라미터
            }
            
            if price is not None:
                params['price'] = str(price)
                
            if stop_price is not None:
                params['stopPrice'] = str(stop_price)
            
            result = self._make_request("POST", "/openApi/swap/v2/trade/order", params)
            
            # 성공 로깅
            if result.get('code') == 0:
                logger.info(f"VST Order placed successfully: {client_order_id}")
                logger.info(f"Order details: {symbol} {side} {quantity} @ {price}")
            else:
                logger.error(f"VST Order failed: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to place VST order: {e}")
            return {'error': str(e)}
    
    def cancel_vst_order(self, symbol: str, order_id: str = None, client_order_id: str = None) -> Dict:
        """VST 주문 취소"""
        try:
            params = {'symbol': symbol}
            
            if order_id:
                params['orderId'] = order_id
            elif client_order_id:
                params['origClientOrderId'] = client_order_id
            else:
                raise ValueError("Either order_id or client_order_id must be provided")
            
            result = self._make_request("DELETE", "/openApi/swap/v2/trade/order", params)
            logger.info(f"VST Order cancelled: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to cancel VST order: {e}")
            return {'error': str(e)}
    
    def get_vst_order_status(self, symbol: str, order_id: str = None, client_order_id: str = None) -> Dict:
        """VST 주문 상태 조회"""
        try:
            params = {'symbol': symbol}
            
            if order_id:
                params['orderId'] = order_id
            elif client_order_id:
                params['origClientOrderId'] = client_order_id
            else:
                raise ValueError("Either order_id or client_order_id must be provided")
            
            result = self._make_request("GET", "/openApi/swap/v2/trade/order", params)
            return result
            
        except Exception as e:
            logger.error(f"Failed to get VST order status: {e}")
            return {'error': str(e)}
    
    # ============= 편의 메서드 =============
    
    def create_vst_market_buy_order(self, symbol: str, quantity: float) -> Dict:
        """VST 시장가 매수 주문"""
        return self.place_vst_order(symbol, "BUY", "MARKET", quantity)
    
    def create_vst_market_sell_order(self, symbol: str, quantity: float) -> Dict:
        """VST 시장가 매도 주문"""
        return self.place_vst_order(symbol, "SELL", "MARKET", quantity)
    
    def create_vst_limit_buy_order(self, symbol: str, quantity: float, price: float) -> Dict:
        """VST 지정가 매수 주문"""
        return self.place_vst_order(symbol, "BUY", "LIMIT", quantity, price)
    
    def create_vst_limit_sell_order(self, symbol: str, quantity: float, price: float) -> Dict:
        """VST 지정가 매도 주문"""
        return self.place_vst_order(symbol, "SELL", "LIMIT", quantity, price)
    
    # ============= 헬퍼 메서드 =============
    
    def test_vst_connection(self) -> bool:
        """VST API 연결 테스트"""
        try:
            result = self.get_vst_balance()
            return 'code' in result and result['code'] == 0
        except Exception as e:
            logger.error(f"VST connection test failed: {e}")
            return False
    
    def get_vst_account_info(self) -> Dict:
        """VST 계정 종합 정보"""
        try:
            balance = self.get_vst_balance()
            positions = self.get_vst_positions()
            
            # VST 잔고 정보 추출
            vst_balance = 0.0
            if balance.get('code') == 0 and balance.get('data'):
                balance_data = balance['data']
                
                # 단일 balance 객체인 경우
                if isinstance(balance_data, dict) and 'balance' in balance_data:
                    balance_info = balance_data['balance']
                    if balance_info.get('asset') in ['VST', 'USDT']:
                        vst_balance = float(balance_info.get('availableMargin', 0))
                
                # 리스트 형태인 경우
                elif isinstance(balance_data, list):
                    for item in balance_data:
                        if item.get('asset') in ['VST', 'USDT']:
                            vst_balance = float(item.get('availableMargin', 0))
                            break
            
            return {
                'vst_balance': vst_balance,
                'open_positions': len([p for p in positions if float(p.get('positionAmt', 0)) != 0]),
                'total_positions': len(positions),
                'account_status': 'active' if balance.get('code') == 0 else 'error'
            }
            
        except Exception as e:
            logger.error(f"Failed to get VST account info: {e}")
            return {
                'vst_balance': 0.0,
                'open_positions': 0,
                'total_positions': 0,
                'account_status': 'error'
            }
    
    def close(self):
        """연결 종료"""
        if hasattr(self, 'session'):
            self.session.close()

# ============= 유틸리티 함수 =============

def create_vst_client_from_env() -> BingXVSTClient:
    """환경 변수에서 VST 클라이언트 생성"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    api_key = os.getenv('BINGX_API_KEY')
    secret_key = os.getenv('BINGX_SECRET_KEY')
    
    if not api_key or not secret_key:
        raise ValueError("BINGX_API_KEY and BINGX_SECRET_KEY must be set in environment variables")
    
    return BingXVSTClient(api_key, secret_key)

if __name__ == "__main__":
    # VST 클라이언트 테스트
    try:
        vst_client = create_vst_client_from_env()
        
        print("=== BingX VST Client Test ===")
        
        # 연결 테스트
        if vst_client.test_vst_connection():
            print("✅ VST Connection: SUCCESS")
            
            # 계정 정보
            account_info = vst_client.get_vst_account_info()
            print(f"💰 VST Balance: {account_info['vst_balance']}")
            print(f"📊 Open Positions: {account_info['open_positions']}")
            
            # 시장가 매수 주문 테스트 (소량)
            # 주의: 실제 VST 계정에 주문이 생성됩니다!
            print("\n🚨 VST 주문 테스트를 진행하시겠습니까? (y/N)")
            user_input = input().strip().lower()
            
            if user_input == 'y':
                test_order = vst_client.create_vst_market_buy_order("BTC-USDT", 0.001)
                print(f"📝 Test Order Result: {test_order}")
        else:
            print("❌ VST Connection: FAILED")
        
        vst_client.close()
        print("=== VST Test Complete ===")
        
    except Exception as e:
        print(f"❌ VST Test Error: {e}")
        import traceback
        traceback.print_exc()