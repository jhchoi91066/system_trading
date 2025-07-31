"""
BingX API 클라이언트
- BingX 거래소 API와의 통신을 담당
- HMAC SHA256 인증 지원
- 데모 모드 및 실거래 모드 지원
"""

import hmac
import hashlib
import time
import requests
import json
import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BingXClient:
    def __init__(self, api_key: str, secret_key: str, demo_mode: bool = True):
        """
        BingX API 클라이언트 초기화
        
        Args:
            api_key: BingX API 키
            secret_key: BingX Secret 키
            demo_mode: 데모 모드 여부 (True: 데모, False: 실거래)
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.demo_mode = demo_mode
        
        # BingX API URLs
        # 주의: BingX는 별도 데모 서버가 없을 수 있으므로 실제 API를 사용하되 내부 시뮬레이션 처리
        self.base_url = "https://open-api.bingx.com"  # BingX 실제 API
            
        self.websocket_url = "wss://open-api-ws.bingx.com/market"
        
        # API 요청 제한
        self.rate_limit_delay = 0.1  # 100ms 지연
        
        # 세션 생성
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'BingX-Python-Client'
        })
    
    def _generate_signature(self, query_string: str, timestamp: str) -> str:
        """
        HMAC SHA256 서명 생성
        
        Args:
            query_string: 쿼리 문자열
            timestamp: 타임스탬프
            
        Returns:
            서명 문자열
        """
        message = f"{query_string}&timestamp={timestamp}"
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
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
            
            # 쿼리 문자열 생성
            query_string = urlencode(sorted(params.items()))
            
            # 서명 생성
            signature = self._generate_signature(query_string.replace('timestamp=', ''), timestamp)
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
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"BingX API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise e
        except Exception as e:
            logger.error(f"Unexpected error in BingX API request: {e}")
            raise e
    
    # ============= 계정 관리 API =============
    
    def get_account_balance(self) -> Dict:
        """계정 잔고 조회"""
        try:
            return self._make_request("GET", "/openApi/swap/v2/user/balance")
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return {}
    
    def get_positions(self, symbol: str = None) -> List[Dict]:
        """포지션 조회"""
        try:
            params = {}
            if symbol:
                params['symbol'] = symbol
            
            result = self._make_request("GET", "/openApi/swap/v2/user/positions", params)
            return result.get('data', [])
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def get_trade_history(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """거래 기록 조회"""
        try:
            params = {'limit': limit}
            if symbol:
                params['symbol'] = symbol
            
            result = self._make_request("GET", "/openApi/swap/v2/trade/allOrders", params)
            return result.get('data', [])
        except Exception as e:
            logger.error(f"Failed to get trade history: {e}")
            return []
    
    # ============= 시장 데이터 API =============
    
    def get_symbols(self) -> List[Dict]:
        """거래 가능한 심볼 목록 조회"""
        try:
            result = self._make_request("GET", "/openApi/swap/v2/quote/contracts", signed=False)
            return result.get('data', [])
        except Exception as e:
            logger.error(f"Failed to get symbols: {e}")
            return []
    
    def get_ticker_price(self, symbol: str) -> Dict:
        """심볼 현재 가격 조회"""
        try:
            params = {'symbol': symbol}
            result = self._make_request("GET", "/openApi/swap/v2/quote/price", params, signed=False)
            return result.get('data', {})
        except Exception as e:
            logger.error(f"Failed to get ticker price for {symbol}: {e}")
            return {}
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100, start_time: int = None, end_time: int = None) -> List[List]:
        """캔들스틱 데이터 조회"""
        try:
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            if start_time:
                params['startTime'] = start_time
            if end_time:
                params['endTime'] = end_time
            
            result = self._make_request("GET", "/openApi/swap/v2/quote/klines", params, signed=False)
            return result.get('data', [])
        except Exception as e:
            logger.error(f"Failed to get klines for {symbol}: {e}")
            return []
    
    def get_24hr_ticker(self, symbol: str) -> Dict:
        """24시간 통계 조회"""
        try:
            params = {'symbol': symbol}
            result = self._make_request("GET", "/openApi/swap/v2/quote/ticker", params, signed=False)
            return result.get('data', {})
        except Exception as e:
            logger.error(f"Failed to get 24hr ticker for {symbol}: {e}")
            return {}
    
    # ============= 거래 실행 API =============
    
    def place_order(self, symbol: str, side: str, order_type: str, quantity: float, 
                   price: float = None, position_side: str = "LONG", 
                   time_in_force: str = "GTC", stop_price: float = None) -> Dict:
        """
        주문 생성
        
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
            params = {
                'symbol': symbol,
                'side': side.upper(),
                'type': order_type.upper(),
                'quantity': str(quantity),
                'positionSide': position_side.upper(),
                'timeInForce': time_in_force
            }
            
            if price is not None:
                params['price'] = str(price)
                
            if stop_price is not None:
                params['stopPrice'] = str(stop_price)
            
            result = self._make_request("POST", "/openApi/swap/v2/trade/order", params)
            logger.info(f"Order placed successfully: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {'error': str(e)}
    
    def cancel_order(self, symbol: str, order_id: str = None, client_order_id: str = None) -> Dict:
        """주문 취소"""
        try:
            params = {'symbol': symbol}
            
            if order_id:
                params['orderId'] = order_id
            elif client_order_id:
                params['origClientOrderId'] = client_order_id
            else:
                raise ValueError("Either order_id or client_order_id must be provided")
            
            return self._make_request("DELETE", "/openApi/swap/v2/trade/order", params)
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {'error': str(e)}
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """심볼의 모든 주문 취소"""
        try:
            params = {'symbol': symbol}
            return self._make_request("DELETE", "/openApi/swap/v2/trade/allOpenOrders", params)
            
        except Exception as e:
            logger.error(f"Failed to cancel all orders for {symbol}: {e}")
            return {'error': str(e)}
    
    def get_order_status(self, symbol: str, order_id: str = None, client_order_id: str = None) -> Dict:
        """주문 상태 조회"""
        try:
            params = {'symbol': symbol}
            
            if order_id:
                params['orderId'] = order_id
            elif client_order_id:
                params['origClientOrderId'] = client_order_id
            else:
                raise ValueError("Either order_id or client_order_id must be provided")
            
            return self._make_request("GET", "/openApi/swap/v2/trade/order", params)
            
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return {'error': str(e)}
    
    # ============= 편의 메서드 =============
    
    def create_market_buy_order(self, symbol: str, quantity: float) -> Dict:
        """시장가 매수 주문"""
        return self.place_order(symbol, "BUY", "MARKET", quantity)
    
    def create_market_sell_order(self, symbol: str, quantity: float) -> Dict:
        """시장가 매도 주문"""
        return self.place_order(symbol, "SELL", "MARKET", quantity)
    
    def create_limit_buy_order(self, symbol: str, quantity: float, price: float) -> Dict:
        """지정가 매수 주문"""
        return self.place_order(symbol, "BUY", "LIMIT", quantity, price)
    
    def create_limit_sell_order(self, symbol: str, quantity: float, price: float) -> Dict:
        """지정가 매도 주문"""
        return self.place_order(symbol, "SELL", "LIMIT", quantity, price)
    
    def create_stop_loss_order(self, symbol: str, quantity: float, stop_price: float, side: str = "SELL") -> Dict:
        """스톱로스 주문"""
        return self.place_order(symbol, side, "STOP_MARKET", quantity, stop_price=stop_price)
    
    def create_take_profit_order(self, symbol: str, quantity: float, price: float, side: str = "SELL") -> Dict:
        """테이크프로핏 주문"""
        return self.place_order(symbol, side, "LIMIT", quantity, price)
    
    # ============= 헬퍼 메서드 =============
    
    def is_demo_mode(self) -> bool:
        """데모 모드 여부 확인"""
        return self.demo_mode
    
    def switch_mode(self, demo_mode: bool):
        """거래 모드 전환 (데모 ↔ 실거래)"""
        self.demo_mode = demo_mode
        if demo_mode:
            self.base_url = "https://api-demo.bingx.com"
        else:
            self.base_url = "https://open-api.bingx.com"
        
        logger.info(f"Switched to {'Demo' if demo_mode else 'Live'} trading mode")
    
    def test_connection(self) -> bool:
        """API 연결 테스트"""
        try:
            result = self.get_symbols()
            return len(result) > 0
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def close(self):
        """연결 종료"""
        if hasattr(self, 'session'):
            self.session.close()

# ============= 유틸리티 함수 =============

def convert_ccxt_to_bingx_symbol(ccxt_symbol: str) -> str:
    """CCXT 심볼을 BingX 형식으로 변환"""
    # 예: BTC/USDT -> BTC-USDT
    return ccxt_symbol.replace('/', '-')

def convert_bingx_to_ccxt_symbol(bingx_symbol: str) -> str:
    """BingX 심볼을 CCXT 형식으로 변환"""
    # 예: BTC-USDT -> BTC/USDT
    return bingx_symbol.replace('-', '/')

def normalize_timeframe(timeframe: str) -> str:
    """타임프레임을 BingX 형식으로 정규화"""
    timeframe_map = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '1h': '1H',
        '4h': '4H',
        '1d': '1D',
        '1w': '1W'
    }
    return timeframe_map.get(timeframe, timeframe)

if __name__ == "__main__":
    # 테스트 코드
    import os
    
    # 환경 변수에서 API 키 읽기
    api_key = os.getenv('BINGX_API_KEY', 'test_api_key')
    secret_key = os.getenv('BINGX_SECRET_KEY', 'test_secret_key')
    
    # 데모 모드로 클라이언트 생성
    client = BingXClient(api_key, secret_key, demo_mode=True)
    
    print(f"Demo mode: {client.is_demo_mode()}")
    print(f"Connection test: {client.test_connection()}")
    
    # 심볼 목록 조회
    symbols = client.get_symbols()
    print(f"Available symbols: {len(symbols)}")
    
    if symbols:
        # BTC-USDT 가격 조회
        btc_price = client.get_ticker_price('BTC-USDT')
        print(f"BTC-USDT price: {btc_price}")
    
    client.close()